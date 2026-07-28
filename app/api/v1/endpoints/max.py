"""MAX Webhook — получение сообщений от @MasterBot."""
from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.api.deps import get_db
from app.services.max_service import send_max_message
from app.services.chat_service import ChatService
from app.utils.logger import setup_logging

router = APIRouter()
logger = setup_logging()


@router.post("/webhook")
async def max_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Принимает webhook от @MasterBot."""
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"[MAX] JSON parse error: {e}")
        return {"ok": False}

    logger.info(f"[MAX] Webhook: {str(data)[:500]}")

    # Формат @MasterBot: {"update_type": "message_created", "message": {...}}
    if data.get("update_type") != "message_created":
        return {"ok": True}

    message = data.get("message", {})
    
    # Не отвечаем ботам — защита от зацикливания
    if message.get("sender", {}).get("is_bot"):
        return {"ok": True, "skipped": "bot"}

    # Извлекаем данные
    chat_id = message.get("recipient", {}).get("chat_id")
    text = message.get("body", {}).get("text") or message.get("text", "")
    user_id = str(message.get("sender", {}).get("id") or chat_id)

    if not chat_id or not text:
        logger.warning("[MAX] Нет chat_id или text")
        return {"ok": True}

    logger.info(f"[MAX] Сообщение от {user_id} в чат {chat_id}: {text[:100]}")

    # Обрабатываем через ChatService
    service = ChatService()
    result = await service.process_message(db, user_id, "max", text)
    
    # Отправляем ответ обратно в MAX
    response_text = result.get("response", "Ошибка обработки")
    ok = await send_max_message(chat_id, response_text)
    
    if not ok:
        logger.error(f"[MAX] Не удалось отправить ответ в чат {chat_id}")

    return {"ok": True}


@router.get("/test")
async def max_test():
    return {
        "status": "MAX endpoint works",
        "webhook_url": "POST /api/v1/max/webhook",
        "note": "Настрой через @MasterBot"
    }
