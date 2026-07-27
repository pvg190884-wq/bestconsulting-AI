"""AI Router — заготовка."""
from enum import Enum

class TaskType(str, Enum):
    CHAT = "chat"
    ANALYTICS = "analytics"
    DOCUMENTS = "documents"
    CODE = "code"
    MEDIA = "media"
    KNOWLEDGE = "knowledge"

class ModelRouter:
    def __init__(self):
        self.fallback_chain = ["kimi", "openai", "deepseek", "claude", "qwen"]

    async def route(self, task_type: TaskType, message: str) -> str:
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
        try:
            idx = self.fallback_chain.index(failed_model)
            if idx + 1 < len(self.fallback_chain):
                return self.fallback_chain[idx + 1]
        except ValueError:
            pass
        return None
