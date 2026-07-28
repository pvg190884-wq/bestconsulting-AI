"""Telegram Webhook — получение сообщений от Telegram."""
from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.api.deps import get_db
from app.services.telegram_service import send_message
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Принимает webhook от Telegram."""
    data = await request.json()
    
    # Пропускаем не-сообщения
    if "message" not in data:
        return {"ok": True}
    
    msg = data["message"]
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")
    
    if not chat_id or not text:
        return {"ok": True}
    
    # Игнорируем служебные сообщения
    if text.startswith("/"):
        if text == "/start":
            await send_message(chat_id, 
                "Здравствуйте! Я высокотехнологичный сотрудник Bestconsulting. "
                "Уточните, из какой вы организации и представьтесь?"
            )
            return {"ok": True}
    
    # Обрабатываем через ChatService
    user_id = str(chat_id)
    service = ChatService()
    result = await service.process_message(db, user_id, "telegram", text)
    
    # Отправляем ответ обратно в Telegram
    response_text = result.get("response", "Ошибка обработки")
    await send_message(chat_id, response_text)
    
    return {"ok": True}
