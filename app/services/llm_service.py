"""LLM Service — вызовы API через OpenRouter с fallback. Поддержка tools (function calling) и веб-поиска."""
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

    async def generate(
        self,
        provider: str,
        messages: list[dict],
        temperature: float = 0.7,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> dict:
        """
        Универсальный вызов чат-модели через OpenRouter.
        Если передан `tools` — модель может вернуть tool_calls вместо финального ответа
        (используется для function calling, например web_search).
        """
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
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        logger.info(f"[LLM] Запрос к {provider} ({model}) через OpenRouter" + (" [tools]" if tools else ""))

        resp = await self.http.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        choice_msg = data["choices"][0]["message"]

        return {
            "content": choice_msg.get("content") or "",
            "tool_calls": choice_msg.get("tool_calls"),
            "model": data.get("model", model),
            "tokens_prompt": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_completion": data.get("usage", {}).get("completion_tokens", 0),
        }

    async def web_search(self, query: str, provider: str = "openai") -> str:
        """
        Поиск актуальной информации в открытых источниках через OpenRouter.
        Используется суффикс модели ':online' — OpenRouter сам подключает веб-поиск (Exa)
        и подмешивает результаты перед генерацией ответа.
        Возвращает готовый текст с фактами и источниками — этот текст затем скармливается
        основной модели как результат вызова инструмента web_search.
        """
        if not self.is_available():
            return "Поиск недоступен: нет доступа к OpenRouter."

        model = self.model_map.get(provider, settings.OPENAI_MODEL)
        online_model = model if model.endswith(":online") else f"{model}:online"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://bestconsulting.ru",
            "X-Title": "BestConsulting AI Core - Web Search",
        }

        payload = {
            "model": online_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — модуль веб-поиска. Найди актуальную информацию по запросу в открытых "
                        "источниках интернета. Ответь кратко, только фактами по делу, обязательно "
                        "укажи источник (домен или название сайта) для каждого факта. Если по теме "
                        "ничего не нашлось или информация противоречива — прямо скажи об этом, не выдумывай."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "temperature": 0.2,
        }

        try:
            logger.info(f"[LLM] Веб-поиск через OpenRouter ({online_model}): {query[:80]}")
            resp = await self.http.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"[LLM] Веб-поиск не удался: {e}")
            return (
                f"Веб-поиск временно недоступен ({e}). Отвечай на основе имеющихся знаний, "
                f"честно предупредив, что данные могут быть неактуальны."
            )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Векторизация. OpenRouter не даёт embeddings — заглушка для v2.2."""
        logger.warning("[Embed] OpenRouter не поддерживает embeddings, возвращаю псевдо-векторы")
        return [[0.0] * 1536 for _ in texts]
