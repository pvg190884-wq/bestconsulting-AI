"""Knowledge Service — сохранение знаний в коде с верификацией."""
import hashlib
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.knowledge import KnowledgeItem, KnowledgeSourceEnum, KnowledgeTypeEnum
from app.db.models.client import Client
from app.utils.security import generate_id
from app.utils.logger import setup_logging

logger = setup_logging()

# ID основателя (мультиканальные)
FOUNDER_IDS = {
    "telegram": "5718678440",
    "max": "348856410",
    "email": "thebestconsulting@mail.ru",
    "kimi": "founder",  # Основной чат Kimi
}


def _is_founder(client_id: str, channel: str) -> bool:
    """Проверка: является ли пользователь основателем."""
    # Нормализация ID
    cid = str(client_id).strip().lower()
    
    # Telegram
    if channel == "telegram" and cid == FOUNDER_IDS["telegram"]:
        return True
    # MAX
    if channel == "max" and cid == FOUNDER_IDS["max"]:
        return True
    # Email
    if channel == "email" and cid == FOUNDER_IDS["email"]:
        return True
    # Kimi (внутренний)
    if channel == "kimi" and "founder" in cid:
        return True
    
    return False


def _verify_document(document_data: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Верификация подписанного документа/скана.
    
    Возвращает: (верифицирован, хеш_документа)
    
    Для v2.3: заглушка — проверяем наличие данных.
    В v3.0: можно добавить OCR подписи, проверку факсимиле, сравнение с образцом.
    """
    if not document_data:
        return False, None
    
    # Создаём хеш от данных документа (base64 скана или текст)
    doc_hash = hashlib.sha256(document_data.encode()).hexdigest()[:32]
    
    # TODO: v3.0 — OCR проверка подписи, сравнение с факсимиле в БД
    # Пока считаем, что если документ предоставлен — верифицирован
    return True, doc_hash


async def save_knowledge(
    db: AsyncSession,
    client_id: str,
    channel: str,
    title: str,
    content: str,
    knowledge_type: str = "instruction",
    document_data: Optional[str] = None,
    original_format: str = "txt",
    tags: Optional[list] = None,
) -> dict:
    """
    Сохранение знаний в базу.
    
    Правила:
    - Основатель: сохраняет без документа, source="founder", verified=true
    - Другие: требуется подписанный документ/скан, source="document", verified=true
    - Без документа от обычного пользователя: отказ
    """
    is_f = _is_founder(client_id, channel)
    
    # Основатель — сохраняем сразу
    if is_f:
        source = KnowledgeSourceEnum.FOUNDER
        verified = True
        verifier_id = client_id
        doc_hash = None
        logger.info(f"[Knowledge] Основатель сохраняет знание: {title}")
    
    # Обычный пользователь — проверяем документ
    else:
        doc_verified, doc_hash = _verify_document(document_data)
        
        if not doc_verified:
            logger.warning(f"[Knowledge] Отказ: пользователь {client_id} без подписанного документа")
            return {
                "success": False,
                "error": "Для сохранения в базу знаний требуется подписанный документ или скан с факсимиле.",
                "required": "signed_document",
            }
        
        source = KnowledgeSourceEnum.DOCUMENT
        verified = True
        verifier_id = client_id
        logger.info(f"[Knowledge] Пользователь {client_id} сохраняет с документом: {title}")
    
    # Конвертация контента в "код" — структурированный JSON
    code_data = _content_to_code(title, content, knowledge_type, tags or [])
    
    item = KnowledgeItem(
        id=generate_id(),
        type=KnowledgeTypeEnum(knowledge_type),
        title=title,
        code_data=code_data,
        original_content=content,
        original_format=original_format,
        source=source,
        verified=verified,
        verifier_id=verifier_id,
        document_hash=doc_hash,
        tags=tags or [],
    )
    
    db.add(item)
    await db.commit()
    
    return {
        "success": True,
        "id": item.id,
        "title": title,
        "source": source.value,
        "verified": verified,
        "message": "Знание сохранено в базу." if is_f else "Знание сохранено после верификации документа.",
    }


def _content_to_code(title: str, content: str, ktype: str, tags: list) -> dict:
    """
    Конвертация текста в структурированный код (JSON).
    Экономит место и позволяет программно обращаться к данным.
    """
    # Разбиваем контент на секции (если есть заголовки)
    sections = []
    current_section = {"heading": "Основное", "lines": []}
    
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('==='):
            if current_section["lines"]:
                sections.append(current_section)
            heading = stripped.lstrip('#= ').strip()
            current_section = {"heading": heading, "lines": []}
        else:
            current_section["lines"].append(stripped)
    
    if current_section["lines"]:
        sections.append(current_section)
    
    return {
        "schema_version": "1.0",
        "title": title,
        "type": ktype,
        "tags": tags,
        "sections": sections,
        "stats": {
            "total_lines": len(content.split('\n')),
            "total_chars": len(content),
            "section_count": len(sections),
        },
        "export_formats": ["md", "html", "txt", "json"],
    }


async def convert_knowledge(
    db: AsyncSession,
    knowledge_id: str,
    output_format: str,
) -> dict:
    """
    Конвертация знания из кода обратно в исходный формат.
    
    Форматы: md, html, txt, json, csv
    """
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == knowledge_id))
    item = result.scalar_one_or_none()
    
    if not item:
        return {"success": False, "error": "Знание не найдено"}
    
    code = item.code_data or {}
    
    if output_format == "json":
        return {"success": True, "format": "json", "data": code}
    
    elif output_format == "md":
        md = _code_to_markdown(code, item)
        return {"success": True, "format": "md", "content": md}
    
    elif output_format == "html":
        html = _code_to_html(code, item)
        return {"success": True, "format": "html", "content": html}
    
    elif output_format == "txt":
        txt = _code_to_text(code, item)
        return {"success": True, "format": "txt", "content": txt}
    
    elif output_format == "csv":
        csv = _code_to_csv(code, item)
        return {"success": True, "format": "csv", "content": csv}
    
    else:
        return {"success": False, "error": f"Формат {output_format} не поддерживается. Доступные: md, html, txt, json, csv"}


def _code_to_markdown(code: dict, item: KnowledgeItem) -> str:
    """Конвертация кода в Markdown."""
    lines = [f"# {code.get('title', item.title)}\n"]
    lines.append(f"**Тип:** {code.get('type', 'unknown')}  ")
    lines.append(f"**Теги:** {', '.join(code.get('tags', []))}  ")
    lines.append(f"**Источник:** {item.source.value}  ")
    lines.append(f"**Дата:** {item.created_at.isoformat() if item.created_at else '-'}  \n")
    
    for sec in code.get("sections", []):
        lines.append(f"## {sec['heading']}")
        for l in sec["lines"]:
            if l.strip():
                lines.append(l)
        lines.append("")
    
    return "\n".join(lines)


def _code_to_html(code: dict, item: KnowledgeItem) -> str:
    """Конвертация кода в HTML."""
    md = _code_to_markdown(code, item)
    # Простая конвертация MD → HTML
    html = md.replace('# ', '<h1>').replace('\n', '</h1>\n', 1)
    html = html.replace('## ', '<h2>').replace('\n', '</h2>\n', 1)
    html = html.replace('**', '<b>').replace('**', '</b>')
    html = f"<html><body>{html}</body></html>"
    return html


def _code_to_text(code: dict, item: KnowledgeItem) -> str:
    """Конвертация кода в плоский текст."""
    lines = [code.get('title', item.title), "=" * 50, ""]
    for sec in code.get("sections", []):
        lines.append(f"[{sec['heading']}]")
        for l in sec["lines"]:
            lines.append(l)
        lines.append("")
    return "\n".join(lines)


def _code_to_csv(code: dict, item: KnowledgeItem) -> str:
    """Конвертация секций в CSV."""
    lines = ["section,line\n"]
    for sec in code.get("sections", []):
        for l in sec["lines"]:
            escaped = l.replace('"', '""')
            lines.append(f'"{sec["heading"]}","{escaped}"\n')
    return "".join(lines)


async def search_knowledge(db: AsyncSession, query: str, limit: int = 10) -> list:
    """Поиск по базе знаний (простой, через original_content)."""
    # TODO: v2.4 — векторный поиск через pgvector
    from sqlalchemy import text
    sql = text("""
        SELECT id, title, type, source, verified, created_at
        FROM knowledge_items
        WHERE verified = true
          AND (title ILIKE :q OR original_content ILIKE :q)
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    result = await db.execute(sql, {"q": f"%{query}%", "limit": limit})
    rows = result.mappings().all()
    return [dict(r) for r in rows]
