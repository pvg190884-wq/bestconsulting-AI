"""Chat API endpoints — заготовка для v2.2 AI."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    user_id: str
    channel: str = "web"  # web, telegram, max, email
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    model_used: str
    processing_time: float
    session_id: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Основной endpoint диалога с агентом.

    В Foundation v2.0 возвращает заглушку.
    Полная реализация — в v2.2 AI Integration.
    """
    return ChatResponse(
        response=f"Привет! Я {request.user_id}, пока в режиме Foundation. Полная версия скоро.",
        model_used="foundation-stub",
        processing_time=0.0,
        session_id=request.session_id or "new-session",
    )
