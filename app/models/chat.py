"""Pydantic модели для чата и диалогов."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Сообщение в диалоге."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None


class ChatSession(BaseModel):
    """Сессия диалога."""
    session_id: str
    client_id: str
    channel: str  # web, telegram, max, email
    messages: List[ChatMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = {}
