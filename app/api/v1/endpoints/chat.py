"""Chat API — живой диалог с GPT-оркестратором."""
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.chat_service import ChatService
from app.utils.security import generate_id

router = APIRouter()
chat_service = ChatService()


class ChatRequest(BaseModel):
    message: str
    user_id: str
    channel: str = "web"
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    model_used: str
    processing_time: float
    session_id: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    start = time.time()

    result = await chat_service.process_message(
        message=request.message,
        user_id=request.user_id,
        channel=request.channel,
        session_id=request.session_id or generate_id(),
        db=db,
    )

    return ChatResponse(
        response=result["response"],
        model_used=result["model_used"],
        processing_time=round(time.time() - start, 3),
        session_id=result["session_id"],
    )
