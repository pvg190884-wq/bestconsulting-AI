"""Memory Base — абстракция долговременной памяти.

Уровни памяти:
1. Глобальная — база знаний компании
2. Проектная — контекст проекта
3. Клиентская — история общения с клиентом
4. Диалоговая — текущий разговор

Полная реализация — в v2.3 Memory (PostgreSQL + pgvector).
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class MemoryItem(BaseModel):
    """Единица памяти."""
    id: str
    content: str
    source: str  # dialog, document, knowledge, learning
    client_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime
    embedding: Optional[List[float]] = None


class MemoryManager:
    """Менеджер памяти. Заготовка для v2.3."""

    async def add(self, item: MemoryItem) -> str:
        """Добавляет запись в память."""
        return item.id

    async def search(self, query: str, client_id: Optional[str] = None, limit: int = 5) -> List[MemoryItem]:
        """Поиск релевантных записей."""
        return []

    async def get_client_history(self, client_id: str, limit: int = 20) -> List[MemoryItem]:
        """История диалогов клиента."""
        return []
