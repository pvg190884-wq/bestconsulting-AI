"""Импортирует все модели, чтобы SQLAlchemy знал о них при создании таблиц."""
from app.db.models.client import Client
from app.db.models.chat import ChatSession, ChatMessage, MessageRoleEnum
from app.db.models.knowledge import KnowledgeItem, KnowledgeTypeEnum
from app.db.models.escalation import Escalation
