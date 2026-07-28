"""Endpoints для работы с базой знаний."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.knowledge_service import save_knowledge, convert_knowledge, search_knowledge
from app.utils.security import generate_id

router = APIRouter()


@router.post("/save")
async def knowledge_save(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Сохранить знание в базу.
    
    Тело запроса:
    {
        "client_id": "5718678440",
        "channel": "telegram",
        "title": "Новое правило",
        "content": "Текст знания...",
        "type": "instruction",
        "document_data": "base64_scan_or_text",  # Опционально
        "original_format": "txt",
        "tags": ["правило", "группа_а"]
    }
    """
    result = await save_knowledge(
        db=db,
        client_id=request.get("client_id", ""),
        channel=request.get("channel", "web"),
        title=request.get("title", "Без названия"),
        content=request.get("content", ""),
        knowledge_type=request.get("type", "instruction"),
        document_data=request.get("document_data"),
        original_format=request.get("original_format", "txt"),
        tags=request.get("tags", []),
    )
    
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result)
    
    return result


@router.get("/{knowledge_id}/convert")
async def knowledge_convert(
    knowledge_id: str,
    format: str = "md",
    db: AsyncSession = Depends(get_db),
):
    """Конвертировать знание в указанный формат."""
    result = await convert_knowledge(db, knowledge_id, format)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result)
    
    return result


@router.get("/search")
async def knowledge_search(
    q: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Поиск по базе знаний."""
    results = await search_knowledge(db, q, limit)
    return {
        "query": q,
        "count": len(results),
        "results": results,
    }
