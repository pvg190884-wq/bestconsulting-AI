"""MAX Service — получение webhook и отправка сообщений в МАХ."""
import httpx
import traceback
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.chat_service import ChatService
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()
router = APIRouter()

# Синглтон ChatService — не создаём на каждый запрос
_chat_service = None

def _get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


# URL отправки сообщений в МАХ (при необходимости замените на актуальный из документации)
MAX_SEND_URL = "https://api.max.ru/v1/messages/send"


async def send_max_message(user_id: str, text: str) -> bool:
    """Отправляет текстовое сообщение пользователю в МАХ."""
    if not text or not user_id:
        return False
    try:
        headers = {
            "Authorization": f"Bearer {settings.MAX_API_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "user_id": user_id,
            "text": text[:4000],  # ограничение МАХ
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(MAX_SEND_URL, headers=headers, json=payload)
            if r.status_code == 200:
                logger.info(f"[MAX] Сообщение отправлено {user_id}")
                return True
            else:
                logger.error(f"[MAX] Ошибка {r.status_code}: {r.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка отправки: {e}")
        return False


@router.post("/webhook")
async def max_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Обрабатывает входящие сообщения от МАХ."""
    try:
        data = await request.json()
        logger.debug(f"[MAX] Raw webhook: {data}")

        # --- Извлечение ID пользователя ---
        user_id = str(
            data.get("user_id")
            or data.get("from", {}).get("id")
            or data.get("sender", {}).get("id")
            or data.get("chat", {}).get("id")
            or ""
        ).strip()

        # --- Извлечение текста ---
        message_text = (
            data.get("text")
            or data.get("message", {}).get("text")
            or data.get("body")
            or ""
        ).strip()

        if not user_id:
            logger.warning("[MAX] Нет user_id в webhook")
            return {"ok": True}

        if not message_text:
            return {"ok": True}

        logger.info(f"[MAX] Входящее от {user_id}: {message_text[:100]}...")

        # --- Обработка через единый мозг ---
        service = _get_chat_service()
        result = await service.process_message(db, user_id, "max", message_text)

        # --- Отправка ответа обратно в МАХ ---
        if isinstance(result, dict) and result.get("response"):
            await send_max_message(user_id, result["response"])

        return {"ok": True}

    except Exception as e:
        err = traceback.format_exc()
        logger.error(f"[MAX] Критическая ошибка webhook: {err}")
        return {"ok": True}


@router.get("/health")
async def max_health():
    """Health-check для МАХ модуля."""
    return {"status": "ok", "service": "max"}
