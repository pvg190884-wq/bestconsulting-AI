"""Embedding Service — векторизация текста.

Полная реализация — в v2.3 Memory (pgvector).
"""


class EmbeddingService:
    """Сервис векторизации. Заготовка."""

    async def embed(self, text: str) -> list[float]:
        """Преобразует текст в вектор."""
        # Заглушка: возвращает псевдо-вектор
        return [0.0] * 1536

    async def similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Косинусное сходство между векторами."""
        # Заглушка
        return 0.95
