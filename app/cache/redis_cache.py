"""Cache Service — семантический и стандартный кэш.

Полная реализация — в v2.3+ с Redis.
"""
import time
from typing import Optional, Any


class CacheService:
    """Сервис кэширования. Заготовка (in-memory для Foundation)."""

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._ttl: dict[str, float] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша."""
        if key in self._store and time.time() < self._ttl.get(key, 0):
            return self._store[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        """Сохраняет значение в кэш."""
        self._store[key] = value
        self._ttl[key] = time.time() + ttl

    async def delete(self, key: str):
        """Удаляет значение из кэша."""
        self._store.pop(key, None)
        self._ttl.pop(key, None)
