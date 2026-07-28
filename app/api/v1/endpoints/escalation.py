"""Endpoints для управления эскалациями (админка)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.deps import get_db
from app.db.models.escalation import Escalation, EscalationStatus

router = APIRouter()


@router.get("/")
async def list_escalations(
    status: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Список эскалаций (для админа)."""
    query = select(Escalation).order_by(desc(Escalation.created_at))
    if status:
        query = query.where(Escalation.status == status)
    query = query.limit(limit)
    
    result = await db.execute(query)
    rows = result.scalars().all()
    
    return {
        "count": len(rows),
        "escalations": [
            {
                "id": r.id,
                "client_id": r.client_id,
                "channel": r.channel,
                "reason": r.trigger_reason,
                "priority": r.priority.value,
                "status": r.status.value,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Закрыть эскалацию."""
    result = await db.execute(select(Escalation).where(Escalation.id == escalation_id))
    esc = result.scalar_one_or_none()
    
    if not esc:
        return {"success": False, "error": "Не найдено"}
    
    esc.status = EscalationStatus.RESOLVED
    from sqlalchemy.sql import func
    esc.resolved_at = func.now()
    await db.commit()
    
    return {"success": True, "id": escalation_id, "status": "resolved"}
