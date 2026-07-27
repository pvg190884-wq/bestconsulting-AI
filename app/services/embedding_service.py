"""Embedding Service — векторизация текста через OpenAI."""
from app.services.llm_service import LLMService

class EmbeddingService:
    def __init__(self):
        self.llm = LLMService()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Преобразует тексты в векторы."""
        if not texts:
            return []
        return await self.llm.embed(texts)

    async def embed_single(self, text: str) -> list[float]:
        """Преобразует один текст в вектор."""
        results = await self.embed([text])
        return results[0] if results else [0.0] * 3072

    async def similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Косинусное сходство между векторами."""
        import math
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)
