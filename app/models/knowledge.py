"""Pydantic модели для базы знаний."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class KnowledgeType(str, Enum):
    DOCUMENT = "document"
    FAQ = "faq"
    SCENARIO = "scenario"
    INSTRUCTION = "instruction"
    CLIENT_PREFERENCE = "client_preference"
    LEARNED = "learned"


class KnowledgeItem(BaseModel):
    """Единица знания."""
    id: str
    type: KnowledgeType
    title: str
    content: str
    tags: List[str] = []
    source: str  # откуда добавлено
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = None
