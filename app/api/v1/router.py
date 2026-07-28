"""Главный роутер API v1."""
from fastapi import APIRouter
from app.api.v1.endpoints import health, chat, admin, knowledge, escalation, telegram, max

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(escalation.router, prefix="/escalations", tags=["escalations"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(max.router, prefix="/max", tags=["max"])
