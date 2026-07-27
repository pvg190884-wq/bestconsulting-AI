"""AI Router — GPT анализирует запрос и выбирает модель.

Fallback-цепочка:
GPT (оркестратор) → DeepSeek → Claude → Qwen → "Техобслуживание"
"""
from enum import Enum
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()


class TaskType(str, Enum):
    CHAT = "chat"
    ANALYTICS = "analytics"
    DOCUMENTS = "documents"
    CODE = "code"
    MEDIA = "media"
    KNOWLEDGE = "knowledge"


class ModelRouter:
    """Маршрутизатор на основе GPT-анализа."""

    def __init__(self):
        self.fallback_chain = ["openai", "deepseek", "claude", "qwen"]

    async def route(self, task_type: TaskType, message: str) -> str:
        """Определяет модель для задачи.

        В v2.2 — простая эвристика.
        В v2.3+ — GPT сам анализирует запрос и выбирает модель.
        """
        mapping = {
            TaskType.CHAT: "openai",
            TaskType.ANALYTICS: "deepseek",
            TaskType.DOCUMENTS: "openai",
            TaskType.CODE: "qwen",
            TaskType.MEDIA: "openai",
            TaskType.KNOWLEDGE: "openai",
        }
        model = mapping.get(task_type, "openai")
        logger.info(f"[Router] Задача {task_type.value} → модель {model}")
        return model

    async def get_fallback(self, failed_model: str) -> str | None:
        """Возвращает следующую модель в цепочке fallback."""
        try:
            idx = self.fallback_chain.index(failed_model)
            if idx + 1 < len(self.fallback_chain):
                return self.fallback_chain[idx + 1]
        except ValueError:
            pass
        return None
