"""Admin API — заготовка для панели администратора."""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/stats")
async def get_stats():
    """Статистика использования. Заготовка для v3.0."""
    return {
        "total_messages": 0,
        "total_sessions": 0,
        "avg_latency_ms": 0,
        "cost_today_usd": 0.0,
        "active_users": 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/knowledge")
async def get_knowledge_items():
    """Список знаний. Заготовка для v2.4."""
    return {"items": [], "total": 0}
