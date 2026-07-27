"""LLM Service — живые вызовы API с fallback.

Поддерживает:
- OpenAI GPT (основной оркестратор)
- DeepSeek (аналитика, резерв)
- Anthropic Claude (длинные документы, резерв)
- Qwen (код, резерв)
"""
import httpx
from app.config import settings
from app.core.exceptions import LLMUnavailableException
from app.utils.logger import setup_logging

logger = setup_logging()


class LLMService:
    """Унифицированный сервис для работы с LLM."""

    def __init__(self):
        self.providers = {
            "openai": {"key": settings.OPENAI_API_KEY, "url": settings.OPENAI_BASE_URL},
            "deepseek": {"key": settings.DEEPSEEK_API_KEY, "url": settings.DEEPSEEK_BASE_URL},
            "claude": {"key": settings.ANTHROPIC_API_KEY, "url": "https://api.anthropic.com/v1"},
            "qwen": {"key": settings.QWEN_API_KEY, "url": settings.QWEN_BASE_URL},
        }
        self.http = httpx.AsyncClient(timeout=60.0)

    def is_available(self, provider: str) -> bool:
        return bool(self.providers.get(provider, {}).get("key"))

    async def generate(self, provider: str, messages: list[dict], model: str = None, temperature: float = 0.7) -> dict:
        """Генерация ответа через указанного провайдера."""
        if not self.is_available(provider):
            raise LLMUnavailableException(provider)

        cfg = self.providers[provider]

        if provider == "openai":
            return await self._call_openai(cfg, messages, model or settings.OPENAI_MODEL, temperature)
        elif provider == "deepseek":
            return await self._call_openai_compatible(cfg, messages, model or settings.DEEPSEEK_MODEL, temperature)
        elif provider == "claude":
            return await self._call_claude(cfg, messages, model or settings.ANTHROPIC_MODEL, temperature)
        elif provider == "qwen":
            return await self._call_openai_compatible(cfg, messages, model or settings.QWEN_MODEL, temperature)
        else:
            raise LLMUnavailableException(provider)

    async def _call_openai(self, cfg: dict, messages: list[dict], model: str, temperature: float) -> dict:
        """Вызов OpenAI API."""
        headers = {"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = await self.http.post(f"{cfg['url']}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "tokens_prompt": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_completion": data.get("usage", {}).get("completion_tokens", 0),
        }

    async def _call_openai_compatible(self, cfg: dict, messages: list[dict], model: str, temperature: float) -> dict:
        """Вызов OpenAI-compatible API (DeepSeek, Qwen)."""
        headers = {"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = await self.http.post(f"{cfg['url']}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "tokens_prompt": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_completion": data.get("usage", {}).get("completion_tokens", 0),
        }

    async def _call_claude(self, cfg: dict, messages: list[dict], model: str, temperature: float) -> dict:
        """Вызов Anthropic Claude API."""
        headers = {
            "x-api-key": cfg["key"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        # Преобразуем messages в формат Claude
        system_msg = ""
        claude_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                claude_messages.append({"role": m["role"], "content": m["content"]})

        payload = {
            "model": model,
            "messages": claude_messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        if system_msg:
            payload["system"] = system_msg

        resp = await self.http.post(f"{cfg['url']}/messages", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "content": data["content"][0]["text"],
            "model": data.get("model", model),
            "tokens_prompt": data.get("usage", {}).get("input_tokens", 0),
            "tokens_completion": data.get("usage", {}).get("output_tokens", 0),
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Векторизация текста через OpenAI."""
        cfg = self.providers["openai"]
        headers = {"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}
        payload = {
            "model": settings.OPENAI_EMBEDDING_MODEL,
            "input": texts,
        }
        resp = await self.http.post(f"{cfg['url']}/embeddings", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]
