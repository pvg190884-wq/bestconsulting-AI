"""Chat API — заготовка."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db

router = APIRouter()


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
    return ChatResponse(
        response=f"Привет! Я {request.user_id}, пока в режиме v2.1 Database. Полная версия скоро.",
        model_used="foundation-stub",
        processing_time=0.0,
        session_id=request.session_id or "new-session",
    )
