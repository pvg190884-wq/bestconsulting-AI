"""Founder Service — поручения, медиа, отчёты для руководителя."""
import httpx
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

FOUNDER_TELEGRAM_ID = "5718678440"
FOUNDER_MAX_ID = ""  # Заполнить при появлении

MEDIA_API_IMAGE = "https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1080&nologo=true"


class FounderService:
    """Сервис для работы с поручениями и задачами основателя."""

    def __init__(self):
        self.founder_id = FOUNDER_TELEGRAM_ID

    def is_founder(self, client_id: str, channel: str) -> bool:
        """Проверяет, является ли клиент основателем."""
        if channel == "telegram" and client_id == self.founder_id:
            return True
        if channel == "max" and client_id == FOUNDER_MAX_ID:
            return True
        return False

    async def create_task(self, db: AsyncSession, title: str, description: str) -> dict:
        """Создаёт поручение от основателя."""
        try:
            sql = text("""
                INSERT INTO founder_tasks (id, title, description, status, created_at, updated_at)
                VALUES (gen_random_uuid(), :title, :description, 'active', NOW(), NOW())
                RETURNING id
            """)
            result = await db.execute(sql, {"title": title, "description": description})
            await db.commit()
            task_id = result.scalar()
            logger.info(f"[FOUNDER] Поручение создано: {title} ({task_id})")
            return {"success": True, "id": str(task_id), "title": title}
        except Exception as e:
            await db.rollback()
            logger.error(f"[FOUNDER] Ошибка создания поручения: {e}")
            return {"success": False, "error": str(e)}

    async def list_tasks(self, db: AsyncSession, status: str = None) -> list:
        """Список поручений."""
        try:
            if status:
                sql = text("SELECT * FROM founder_tasks WHERE status = :status ORDER BY created_at DESC")
                result = await db.execute(sql, {"status": status})
            else:
                sql = text("SELECT * FROM founder_tasks ORDER BY created_at DESC")
                result = await db.execute(sql)
            rows = result.mappings().all()
            return [{"id": str(r["id"]), "title": r["title"], "status": r["status"], "created_at": str(r["created_at"])} for r in rows]
        except Exception as e:
            logger.error(f"[FOUNDER] Ошибка списка: {e}")
            return []

    async def get_stats(self, db: AsyncSession) -> dict:
        """Статистика по каналам и контактам."""
        try:
            r1 = await db.execute(text("SELECT COUNT(*) FROM clients"))
            total_clients = r1.scalar()

            r2 = await db.execute(text("SELECT client_group, COUNT(*) FROM clients GROUP BY client_group"))
            by_group = {row[0] or "unknown": row[1] for row in r2.fetchall()}

            r3 = await db.execute(text("SELECT channel, COUNT(*) FROM clients GROUP BY channel"))
            by_channel = {row[0] or "unknown": row[1] for row in r3.fetchall()}

            r4 = await db.execute(text("SELECT COUNT(*) FROM escalations WHERE created_at > NOW() - INTERVAL '7 days'"))
            escalations_week = r4.scalar()

            r5 = await db.execute(text("SELECT COUNT(*) FROM knowledge_items"))
            kb_count = r5.scalar()

            return {
                "total_clients": total_clients,
                "by_group": by_group,
                "by_channel": by_channel,
                "escalations_week": escalations_week,
                "knowledge_items": kb_count,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[FOUNDER] Ошибка статистики: {e}")
            return {}

    async def save_founder_knowledge(self, db: AsyncSession, content: str, title: str = None) -> dict:
        """Сохраняет факт от основателя без верификации."""
        try:
            sql = text("""
                INSERT INTO knowledge_items (id, title, original_content, tags, verified, type, created_at)
                VALUES (gen_random_uuid(), :title, :content, :tags, true, 'text', NOW())
                RETURNING id
            """)
            result = await db.execute(sql, {
                "title": title or f"Поручение основателя {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "content": content,
                "tags": json.dumps(["основатель", "поручение", "верифицировано"]),
            })
            await db.commit()
            kid = result.scalar()
            logger.info(f"[FOUNDER] Факт сохранён: {kid}")
            return {"success": True, "id": str(kid)}
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}

    async def generate_media(self, prompt: str, width: int = 1080, height: int = 1080) -> dict:
        """Генерирует изображение через Pollinations.ai (бесплатно)."""
        try:
            safe_prompt = prompt.replace(" ", "%20")
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={width}&height={height}&nologo=true&seed=42&enhance=true"
            
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return {
                        "success": True,
                        "url": url,
                        "prompt": prompt,
                        "note": "Изображение сгенерировано. Скачайте по ссылке."
                    }
                else:
                    return {"success": False, "error": f"API вернул {r.status_code}"}
        except Exception as e:
            logger.error(f"[FOUNDER] Ошибка генерации медиа: {e}")
            return {"success": False, "error": str(e)}

    def parse_command(self, text: str) -> tuple[str, str]:
        """Парсит команду руководителя. Возвращает (команда, аргумент)."""
        t = text.strip()
        if not t.startswith("/"):
            return ("", t)
        
        parts = t.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        return (cmd, arg)
