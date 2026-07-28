"""MAX Webhook — получение сообщений от MAX."""
from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.api.deps import get_db
from app.services.max_service import send_max_message
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("/webhook")
async def max_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Принимает webhook от MAX."""
    data = await request.json()
    
    # MAX формат: {"message": {"chat": {"id": "..."}, "text": "...", "from": {"id": "..."}}}
    if "message" not in data:
        return {"ok": True}
    
    msg = data["message"]
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = msg.get("text", "")
    user_id = str(msg.get("from", {}).get("id", chat_id))
    
    if not chat_id or not text:
        return {"ok": True}
    
    # Обрабатываем через ChatService
    service = ChatService()
    result = await service.process_message(db, user_id, "max", text)
    
    # Отправляем ответ обратно в MAX
    response_text = result.get("response", "Ошибка обработки")
    await send_max_message(chat_id, response_text)
    
    return {"ok": True}
