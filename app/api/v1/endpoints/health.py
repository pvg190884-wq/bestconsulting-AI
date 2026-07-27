"""Health check endpoints."""
from fastapi import APIRouter, Depends
from datetime import datetime

from app.config import settings
from app.api.deps import get_settings

router = APIRouter()


@router.get("/")
async def health_check():
    """Проверка работоспособности сервиса."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "agent": settings.AGENT_NAME,
        "environment": settings.APP_ENV,
    }


@router.get("/ready")
async def readiness_check():
    """Проверка готовности к приему трафика."""
    # TODO: проверка подключения к БД, Redis и т.д.
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "pending",
            "llm_orchestrator": "pending",
            "cache": "pending",
        },
    }
