"""Cache Service."""
import time
from typing import Optional, Any

class CacheService:
    def __init__(self):
        self._store: dict[str, Any] = {}
        self._ttl: dict[str, float] = {}

    async def get(self, key: str) -> Optional[Any]:
        if key in self._store and time.time() < self._ttl.get(key, 0):
            return self._store[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        self._store[key] = value
        self._ttl[key] = time.time() + ttl

    async def delete(self, key: str):
        self._store.pop(key, None)
        self._ttl.pop(key, None)
