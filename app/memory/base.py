"""Memory Base — абстракция долговременной памяти.

Заготовка для v2.3 (RAG + pgvector).
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class MemoryItem(BaseModel):
    id: str
    content: str
    source: str
    client_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime
    embedding: Optional[List[float]] = None

class MemoryManager:
    async def add(self, item: MemoryItem) -> str:
        return item.id

    async def search(self, query: str, client_id: Optional[str] = None, limit: int = 5) -> List[MemoryItem]:
        return []

    async def get_client_history(self, client_id: str, limit: int = 20) -> List[MemoryItem]:
        return []
