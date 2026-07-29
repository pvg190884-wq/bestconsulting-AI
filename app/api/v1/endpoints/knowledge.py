"""Knowledge Base API — управление базой знаний."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List
from pydantic import BaseModel

from app.api.deps import get_db
from app.utils.logger import setup_logging

router = APIRouter()
logger = setup_logging()


class KnowledgeItemCreate(BaseModel):
    title: str
    content: str
    tags: list[str] = []
    verified: bool = True


class KnowledgeBatchUpload(BaseModel):
    items: List[KnowledgeItemCreate]


@router.post("/save")
async def save_knowledge(item: KnowledgeItemCreate, db: AsyncSession = Depends(get_db)):
    """Сохранить одну запись в базу знаний."""
    try:
        sql = text("""
            INSERT INTO knowledge_items (id, title, original_content, tags, verified, created_at)
            VALUES (gen_random_uuid(), :title, :content, :tags, :verified, NOW())
            RETURNING id
        """)
        result = await db.execute(sql, {
            "title": item.title,
            "content": item.content,
            "tags": item.tags,
            "verified": item.verified,
        })
        await db.commit()
        new_id = result.scalar()
        logger.info(f"[KB] Сохранена запись: {item.title} ({new_id})")
        return {"success": True, "id": str(new_id), "title": item.title}
    except Exception as e:
        await db.rollback()
        logger.error(f"[KB] Ошибка сохранения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def upload_batch(data: KnowledgeBatchUpload, db: AsyncSession = Depends(get_db)):
    """Массовая загрузка записей в базу знаний."""
    imported = 0
    errors = []
    
    for idx, item in enumerate(data.items):
        try:
            sql = text("""
                INSERT INTO knowledge_items (id, title, original_content, tags, verified, created_at)
                VALUES (gen_random_uuid(), :title, :content, :tags, :verified, NOW())
                ON CONFLICT (title) DO UPDATE SET
                    original_content = EXCLUDED.original_content,
                    tags = EXCLUDED.tags,
                    verified = EXCLUDED.verified,
                    created_at = NOW()
            """)
            await db.execute(sql, {
                "title": item.title,
                "content": item.content,
                "tags": item.tags,
                "verified": item.verified,
            })
            imported += 1
        except Exception as e:
            errors.append({"index": idx, "title": item.title, "error": str(e)[:100]})
            logger.error(f"[KB] Ошибка в batch [{idx}] {item.title}: {e}")
    
    await db.commit()
    logger.info(f"[KB] Batch загружено: {imported}/{len(data.items)}")
    
    return {
        "success": True,
        "imported": imported,
        "total": len(data.items),
        "errors": errors,
    }


@router.get("/search")
async def search_knowledge(q: str, group: str = "", limit: int = 3, db: AsyncSession = Depends(get_db)):
    """Поиск по базе знаний."""
    try:
        if group:
            group_tag = f"группа_{group.lower()}"
            sql = text("""
                SELECT title, original_content, tags 
                FROM knowledge_items 
                WHERE verified = true 
                  AND (title ILIKE :q OR original_content ILIKE :q)
                ORDER BY 
                    CASE WHEN :group_tag = ANY(tags) THEN 0 ELSE 1 END,
                    created_at DESC 
                LIMIT :limit
            """)
            result = await db.execute(sql, {
                "q": f"%{q}%",
                "group_tag": group_tag,
                "limit": limit,
            })
        else:
            sql = text("""
                SELECT title, original_content, tags 
                FROM knowledge_items 
                WHERE verified = true 
                  AND (title ILIKE :q OR original_content ILIKE :q)
                ORDER BY created_at DESC 
                LIMIT :limit
            """)
            result = await db.execute(sql, {"q": f"%{q}%", "limit": limit})
        
        rows = result.mappings().all()
        items = []
        for r in rows:
            items.append({
                "title": r["title"],
                "content": r["original_content"][:500],
                "tags": r["tags"],
            })
        
        return {"query": q, "group": group, "count": len(items), "items": items}
    except Exception as e:
        logger.error(f"[KB] Ошибка поиска: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_knowledge(group: str = "", limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Список всех записей базы знаний (с фильтром по группе)."""
    try:
        if group:
            sql = text("""
                SELECT id, title, tags, verified, created_at 
                FROM knowledge_items 
                WHERE :group_tag = ANY(tags)
                ORDER BY created_at DESC 
                LIMIT :limit
            """)
            result = await db.execute(sql, {
                "group_tag": f"группа_{group.lower()}",
                "limit": limit,
            })
        else:
            sql = text("""
                SELECT id, title, tags, verified, created_at 
                FROM knowledge_items 
                ORDER BY created_at DESC 
                LIMIT :limit
            """)
            result = await db.execute(sql, {"limit": limit})
        
        rows = result.mappings().all()
        return {
            "count": len(rows),
            "items": [{"id": str(r["id"]), "title": r["title"], "tags": r["tags"], "verified": r["verified"]} for r in rows]
        }
    except Exception as e:
        logger.error(f"[KB] Ошибка списка: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_knowledge(db: AsyncSession = Depends(get_db)):
    """Очистить всю базу знаний (осторожно!)."""
    try:
        await db.execute(text("DELETE FROM knowledge_items"))
        await db.commit()
        logger.warning("[KB] База знаний очищена")
        return {"success": True, "message": "База знаний очищена"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
