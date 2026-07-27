"""AI Router — маршрутизатор запросов между LLM.

Определяет, какая модель лучше справится с задачей:
- KIMI — основной оркестратор, общение, сценарии
- OpenAI/GPT — документы, универсальные задачи
- DeepSeek — аналитика, логика, сложные рассуждения
- Claude — длинные документы, юридический текст
- Qwen — программирование, код, скрипты

Полная реализация — в v2.2 AI Integration.
"""
from enum import Enum


class TaskType(str, Enum):
    """Типы задач для маршрутизации."""
    CHAT = "chat"
    ANALYTICS = "analytics"
    DOCUMENTS = "documents"
    CODE = "code"
    MEDIA = "media"
    KNOWLEDGE = "knowledge"


class ModelRouter:
    """Маршрутизатор моделей. Заготовка для v2.2."""

    def __init__(self):
        self.fallback_chain = [
            "kimi",
            "openai",
            "deepseek",
            "claude",
            "qwen",
        ]

    async def route(self, task_type: TaskType, message: str) -> str:
        """Определяет модель для задачи."""
        mapping = {
            TaskType.CHAT: "kimi",
            TaskType.ANALYTICS: "deepseek",
            TaskType.DOCUMENTS: "openai",
            TaskType.CODE: "qwen",
            TaskType.MEDIA: "openai",
            TaskType.KNOWLEDGE: "kimi",
        }
        return mapping.get(task_type, "kimi")

    async def get_fallback(self, failed_model: str) -> str | None:
        """Возвращает следующую модель в цепочке fallback."""
        try:
            idx = self.fallback_chain.index(failed_model)
            if idx + 1 < len(self.fallback_chain):
                return self.fallback_chain[idx + 1]
        except ValueError:
            pass
        return None
