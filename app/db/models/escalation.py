"""SQLAlchemy модель: Эскалации."""
from sqlalchemy import Column, String, DateTime, Text, Enum as SAEnum, Boolean
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class EscalationStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class EscalationPriority(str, enum.Enum):
    HIGH = "высокая"
    MEDIUM = "средняя"
    LOW = "низкая"


class Escalation(Base):
    __tablename__ = "escalations"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    client_id = Column(String(255), nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    
    trigger_reason = Column(Text, nullable=False)
    trigger_message = Column(Text, nullable=False)
    
    context_summary = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    
    priority = Column(SAEnum(EscalationPriority), default=EscalationPriority.MEDIUM)
    status = Column(SAEnum(EscalationStatus), default=EscalationStatus.NEW)
    
    assigned_to = Column(String(255), nullable=True)
    
    extra_data = Column("metadata", Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
