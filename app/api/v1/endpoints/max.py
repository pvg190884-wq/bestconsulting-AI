"""MAX Webhook — получение сообщений от MAX."""
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
    """Принимает webhook от MAX."""
    raw_body = await request.body()
    logger.info(f"[MAX] Raw body: {raw_body.decode()[:800]}")
    
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"[MAX] JSON parse error: {e}")
        return {"ok": False, "error": "invalid json"}
    
    logger.info(f"[MAX] Parsed: {str(data)[:500]}")
    
    # MAX формат: {"message": {"chat_id": 123, "text": "...", "from": {"id": ...}}}
    message = data.get("message") or data.get("data", {}).get("message") or data
    
    if not isinstance(message, dict):
        logger.warning(f"[MAX] No message found in: {str(data)[:300]}")
        return {"ok": True}
    
    # Извлекаем chat_id (число) и текст
    chat_id = message.get("chat_id") or message.get("chat", {}).get("id") or ""
    text = message.get("text") or message.get("body") or ""
    user_id = str(message.get("from_id") or message.get("from", {}).get("id") or chat_id)
    
    logger.info(f"[MAX] chat_id={chat_id}, user_id={user_id}, text={text[:100]}")
    
    if not chat_id or not text:
        logger.warning("[MAX] Missing chat_id or text")
        return {"ok": True}
    
    # Обрабатываем через ChatService
    service = ChatService()
    result = await service.process_message(db, user_id, "max", text)
    
    # Отправляем ответ обратно в MAX
    response_text = result.get("response", "Ошибка обработки")
    ok = await send_max_message(chat_id, response_text)
    
    if not ok:
        logger.error(f"[MAX] Failed to send response to {chat_id}")
    
    return {"ok": True}


@router.get("/test")
async def max_test():
    """Тестовый endpoint."""
    return {
        "status": "MAX endpoint works",
        "webhook_url": "POST /api/v1/max/webhook",
        "note": "MAX должен отправлять сюда webhook-сообщения"
    }
