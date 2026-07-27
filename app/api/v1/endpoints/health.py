"""Health check с проверкой БД."""
from fastapi import APIRouter, Depends
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.api.deps import get_db

router = APIRouter()


@router.get("/")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.2.0",
        "agent": settings.AGENT_NAME,
        "environment": settings.APP_ENV,
        "orchestrator": "GPT",
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ready" if db_status == "connected" else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": db_status,
            "llm_orchestrator": "active",
            "cache": "pending",
        },
    }
