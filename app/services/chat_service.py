"""Chat Service — основная логика диалога.

1. Получает сообщение от пользователя
2. Загружает контекст (история диалога + релевантные знания из БД)
3. Отправляет в GPT (или fallback-модель)
4. Сохраняет ответ в БД
5. Возвращает ответ пользователю
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.services.llm_service import LLMService
from app.orchestrator.router import ModelRouter, TaskType
from app.memory.dialog_manager import DialogManager
from app.utils.logger import setup_logging
from app.utils.security import generate_id

logger = setup_logging()


class ChatService:
    def __init__(self):
        self.llm = LLMService()
        self.router = ModelRouter()
        self.dialog = DialogManager()

    async def process_message(self, message: str, user_id: str, channel: str, session_id: str, db: AsyncSession) -> dict:
        """Обработка одного сообщения."""
        logger.info(f"[Chat] user={user_id} channel={channel} session={session_id}")

        # 1. Определяем тип задачи (в v2.2 — всегда CHAT, GPT сам разберётся)
        task_type = TaskType.CHAT
        model = await self.router.route(task_type, message)

        # 2. Загружаем системный промпт + историю диалога
        system_prompt = await self._load_system_prompt()
        history = await self.dialog.get_history(db, session_id, limit=10)

        messages = [{"role": "system", "content": system_prompt}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        # 3. Вызываем LLM с fallback
        result = await self._call_with_fallback(model, messages)

        # 4. Сохраняем в БД
        await self.dialog.save_message(db, session_id, user_id, channel, "user", message)
        await self.dialog.save_message(
            db, session_id, user_id, channel, "assistant",
            result["content"],
            model_used=result["model"],
            tokens_used=result.get("tokens_prompt", 0) + result.get("tokens_completion", 0),
        )

        return {
            "response": result["content"],
            "model_used": result["model"],
            "session_id": session_id,
        }

    async def _call_with_fallback(self, model: str, messages: list[dict]) -> dict:
        """Вызов LLM с цепочкой fallback."""
        current_model = model
        attempted = []

        while current_model:
            try:
                logger.info(f"[LLM] Попытка вызова {current_model}")
                result = await self.llm.generate(current_model, messages)
                result["model"] = current_model
                return result
            except Exception as e:
                logger.warning(f"[LLM] {current_model} недоступен: {e}")
                attempted.append(current_model)
                current_model = await self.router.get_fallback(current_model)

        # Все модели недоступны
        logger.error("[LLM] Все модели недоступны")
        return {
            "content": "Проводятся технические работы. Пожалуйста, попробуйте позже.",
            "model": "unavailable",
        }

    async def _load_system_prompt(self) -> str:
        """Загружает системный промпт."""
        try:
            with open("app/prompts/system.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return f"Ты — {settings.AGENT_NAME}. Помогай клиентам профессионально и вежливо."
