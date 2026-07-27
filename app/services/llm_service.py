"""LLM Service — унифицированный интерфейс к провайдерам.

Поддерживает:
- KIMI (Moonshot AI)
- OpenAI
- DeepSeek
- Anthropic Claude
- Qwen (Alibaba)

Полная реализация — в v2.2 AI Integration.
"""
from app.config import settings
from app.core.exceptions import LLMUnavailableException


class LLMService:
    """Унифицированный сервис для работы с LLM."""

    def __init__(self):
        self.providers = {
            "kimi": settings.KIMI_API_KEY,
            "openai": settings.OPENAI_API_KEY,
            "deepseek": settings.DEEPSEEK_API_KEY,
            "claude": settings.ANTHROPIC_API_KEY,
            "qwen": settings.QWEN_API_KEY,
        }

    def is_available(self, provider: str) -> bool:
        """Проверяет, настроен ли провайдер."""
        return bool(self.providers.get(provider))

    async def generate(self, provider: str, prompt: str, **kwargs) -> str:
        """Генерация ответа через указанного провайдера.

        Заглушка для Foundation v2.0.
        """
        if not self.is_available(provider):
            raise LLMUnavailableException(provider)
        return f"[ЗАГЛУШКА {provider.upper()}] Ответ на: {prompt[:50]}..."
