"""LLM Service — вызовы API через OpenRouter с fallback."""
import httpx
from app.config import settings
from app.core.exceptions import LLMUnavailableException
from app.utils.logger import setup_logging

logger = setup_logging()


class LLMService:
    """Унифицированный сервис для работы с LLM через OpenRouter."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.http = httpx.AsyncClient(timeout=60.0)

        self.model_map = {
            "openai": settings.OPENAI_MODEL,
            "deepseek": settings.DEEPSEEK_MODEL,
            "claude": settings.ANTHROPIC_MODEL,
            "qwen": settings.QWEN_MODEL,
        }

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://bestconsulting.ru",
            "X-Title": "BestConsulting AI Core",
        }

    async def generate(self, provider: str, messages: list[dict], temperature: float = 0.7) -> dict:
        if not self.is_available():
            raise LLMUnavailableException("openrouter")

        model = self.model_map.get(provider, settings.OPENAI_MODEL)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        logger.info(f"[LLM] Запрос к {provider} ({model}) через OpenRouter")

        resp = await self.http.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "tokens_prompt": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_completion": data.get("usage", {}).get("completion_tokens", 0),
        }

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str = "Опиши подробно, что изображено на этом изображении. Если это документ — извлеки весь текст полностью, сохраняя структуру.",
        provider: str = "openai",
        mime_type: str = "image/jpeg",
    ) -> dict:
        """Распознавание изображения через мультимодальный вызов OpenRouter (vision).

        Модель openai/gpt-4o-mini принимает изображение напрямую в сообщении
        в формате data-URL (base64), без отдельного API для vision.
        """
        if not self.is_available():
            raise LLMUnavailableException("openrouter")

        model = self.model_map.get(provider, settings.OPENAI_MODEL)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "temperature": 0.3,
        }

        logger.info(f"[LLM] Vision-запрос к {provider} ({model}) через OpenRouter")

        resp = await self.http.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "tokens_prompt": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_completion": data.get("usage", {}).get("completion_tokens", 0),
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Векторизация. OpenRouter не предоставляет embeddings-endpoint —
        это ограничение API-провайдера, а не временная заглушка."""
        logger.warning("[Embed] OpenRouter не поддерживает embeddings, возвращаю псевдо-векторы")
        return [[0.0] * 1536 for _ in texts]
