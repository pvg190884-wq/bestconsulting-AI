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

    async def generate(self, provider: str, messages: list[dict], temperature: float = 0.7) -> dict:
        if not self.is_available():
            raise LLMUnavailableException("openrouter")

        model = self.model_map.get(provider, settings.OPENAI_MODEL)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://bestconsulting.ru",
            "X-Title": "BestConsulting AI Core",
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        logger.info(f"[LLM] Запрос к {provider} ({model}) через OpenRouter")
        
        resp = await self.http.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
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
        """Векторизация. OpenRouter не даёт embeddings — заглушка для v2.2."""
        logger.warning("[Embed] OpenRouter не поддерживает embeddings, возвращаю псевдо-векторы")
        return [[0.0] * 1536 for _ in texts]
