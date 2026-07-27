"""Embedding Service — заготовка."""
class EmbeddingService:
    async def embed(self, text: str) -> list[float]:
        return [0.0] * 1536

    async def similarity(self, vec1: list[float], vec2: list[float]) -> float:
        return 0.95
