"""SQLAlchemy модель: Клиенты."""
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func
from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"
    id = Column(String(36), primary_key=True)
    external_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    channel = Column(String(50), nullable=False, default="web")
    preferences = Column(JSON, default=dict)
    extra_data = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
