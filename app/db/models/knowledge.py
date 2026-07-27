"""SQLAlchemy модель: База знаний (заготовка под pgvector v2.3)."""
from sqlalchemy import Column, String, DateTime, Text, Float, Boolean, JSON, Enum as SAEnum, Index
from sqlalchemy.sql import func
import enum
from app.db.base import Base

class KnowledgeTypeEnum(str, enum.Enum):
    DOCUMENT = "document"
    FAQ = "faq"
    SCENARIO = "scenario"
    INSTRUCTION = "instruction"
    CLIENT_PREFERENCE = "client_preference"
    LEARNED = "learned"

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(String(36), primary_key=True)
    type = Column(SAEnum(KnowledgeTypeEnum), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    source = Column(String(255), nullable=False)
    confidence = Column(Float, default=1.0)
    verified = Column(Boolean, default=False)
    embedding = Column(JSON, nullable=True)  # Заготовка под pgvector
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_knowledge_type_verified", "type", "verified"),
    )
