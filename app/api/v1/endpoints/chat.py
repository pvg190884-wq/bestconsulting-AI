"""Chat API — живой диалог с GPT-оркестратором."""
import time
import traceback
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    user_id: str
    channel: str = "web"


@router.post("/")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    start = time.time()
    
    try:
        from app.services.chat_service import ChatService
        service = ChatService()
        
        result = await service.process_message(
            db=db,
            client_id=request.user_id,
            channel=request.channel,
            message=request.message,
        )
        
        return {
            "response": result["response"],
            "model_used": result["model_used"],
            "processing_time": round(time.time() - start, 3),
            "session_id": result["session_id"],
            "group": result.get("group"),
            "requires_identification": result.get("requires_identification", False),
        }
        
    except Exception as e:
        err = traceback.format_exc()
        return {
            "response": f"Ошибка сервера: {str(e)[:200]}",
            "model_used": "error",
            "processing_time": round(time.time() - start, 3),
            "session_id": f"{request.user_id}_{request.channel}",
            "error_detail": err[:500],
        }
