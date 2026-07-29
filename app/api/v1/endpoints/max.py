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

_chat_service = None
def _get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


MAX_API_HOST = "https://platform-api2.max.ru"


async def send_max_message(chat_id, text: str) -> bool:
    """Отправляет текстовое сообщение в чат МАХ по chat_id."""
    if not text or not chat_id:
        return False
    try:
        cid = int(chat_id)
    except (ValueError, TypeError):
        logger.error(f"[MAX] Неверный chat_id: {chat_id}")
        return False

    url = f"{MAX_API_HOST}/messages?chat_id={cid}"
    payload = {"text": text[:4000]}
    headers = {
        "Authorization": settings.MAX_API_TOKEN,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code == 200:
                logger.info(f"[MAX] Сообщение отправлено в чат {cid}")
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

        message = data.get("message", {}) if isinstance(data, dict) else {}

        if message.get("sender", {}).get("is_bot"):
            return {"ok": True, "skipped": "bot"}

        sender_id = str(
            message.get("sender", {}).get("user_id")
            or data.get("user_id")
            or data.get("from", {}).get("id")
            or ""
        ).strip()

        chat_id = (
            message.get("recipient", {}).get("chat_id")
            or data.get("chat", {}).get("id")
            or sender_id
        )

        message_text = (
            message.get("body", {}).get("text")
            or data.get("text")
            or data.get("body")
            or ""
        ).strip()

        if not sender_id or not chat_id:
            logger.warning(f"[MAX] Нет sender_id/chat_id в webhook: {data}")
            return {"ok": True}

        if not message_text:
            return {"ok": True}

        logger.info(f"[MAX] Входящее от {sender_id} (chat {chat_id}): {message_text[:100]}...")

        service = _get_chat_service()
        result = await service.process_message(db, sender_id, "max", message_text)

        if isinstance(result, dict) and result.get("response"):
            await send_max_message(chat_id, result["response"])

        return {"ok": True}
    except Exception as e:
        err = traceback.format_exc()
        logger.error(f"[MAX] Критическая ошибка webhook: {err}")
        return {"ok": True}


@router.get("/health")
async def max_health():
    """Health-check для МАХ модуля."""
    return {"status": "ok", "service": "max"}
