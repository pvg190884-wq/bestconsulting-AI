"""SQLAlchemy модель: База знаний (хранение в коде/JSON)."""
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


class KnowledgeSourceEnum(str, enum.Enum):
    FOUNDER = "founder"      # Основатель — без документа
    DOCUMENT = "document"    # Подписанный документ/скан
    USER = "user"            # Обычный пользователь (требует документ)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    
    id = Column(String(36), primary_key=True)
    type = Column(SAEnum(KnowledgeTypeEnum), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    
    # Хранение в "коде" — структурированный JSON (как group_a_knowledge.js)
    code_data = Column(JSON, nullable=False, default=dict)
    
    # Исходный текст (для поиска и конвертации обратно)
    original_content = Column(Text, nullable=True)
    
    # Формат исходника: txt, md, docx, pdf, scan, jpg, png
    original_format = Column(String(50), default="txt")
    
    # Верификация
    source = Column(SAEnum(KnowledgeSourceEnum), nullable=False, default="user")
    verified = Column(Boolean, default=False)
    verifier_id = Column(String(255), nullable=True)  # Кто верифицировал
    document_hash = Column(String(255), nullable=True)  # Хеш скана/документа
    
    # Метаданные
    tags = Column(JSON, default=list)
    confidence = Column(Float, default=1.0)
    extra_data = Column("metadata", JSON, default=dict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index("ix_knowledge_type_verified", "type", "verified"),
        Index("ix_knowledge_source_verified", "source", "verified"),
    )
