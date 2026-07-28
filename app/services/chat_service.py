"""Chat Service — обработка сообщений с идентификацией группы и RAG."""
import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService
from app.memory.dialog_manager import DialogManager
from app.services.knowledge_service import search_knowledge
from app.utils.logger import setup_logging

logger = setup_logging()

# Ключевые слова для определения группы
GROUP_KEYWORDS = {
    "A": ["личн", "контакт", "агафонов", "павлов", "партнёр", "основатель", "группа а", "группа a", "личное", "конфиденциально", "основател", "владелец", "акционер"],
    "B": ["услуг", "лендинг", "сайт", "цена", "заказ", "прайс", "услуга", "группа б", "группа b", "стоимость", "калькулятор", "разработка", "дизайн", "seo", "реклама"],
    "C": ["общий", "вопрос", "информация", "другое", "группа в", "группа c", "консультация", "звонок"],
}

SYSTEM_PROMPT_CORE = (
    "Ты — Высокотехнологичный сотрудник Bestconsulting. "
    "Правила ответа: "
    "1. ТОЛЬКО конкретный ответ. Без размышлений, догадок, философии. "
    "2. Без вводных фраз типа 'Я думаю', 'Возможно', 'Судя по всему'. "
    "3. Если не знаешь — скажи 'Нет данных'. "
    "4. Кратко. По существу. "
)

GROUP_CONTEXT = {
    "A": "Клиент Группы А (личные контакты, конфиденциально). Доступны личные контакты основателей. ",
    "B": "Клиент Группы Б (услуги компании). Доступны прайсы, услуги, сроки. ",
    "C": "Клиент Группы В (общий). Стандартные ответы, без конфиденциальных данных. ",
}


class ChatService:
    def __init__(self):
        self.llm = LLMService()
        self.dialog = DialogManager()

    async def process_message(self, db: AsyncSession, client_id: str, channel: str, message: str) -> dict:
        start_time = time.time()
        session_id = f"{client_id}_{channel}"

        # 1. Получаем/создаём клиента
        client = await self.dialog._get_or_create_client(db, client_id, channel)

        # 2. Проверяем группу
        group = await self.dialog.get_client_group(db, client_id)

        if not group:
            # Пытаемся определить из текста
            group = self._detect_group(message)
            if group:
                await self.dialog.set_client_group(db, client_id, group)
                logger.info(f"[Chat] Клиент {client_id} → Группа {group}")
            else:
                # Не определили — задаём уточняющий вопрос
                return {
                    "response": (
                        "Здравствуйте! Чтобы я мог помочь точнее, уточните: "
                        "ваш вопрос связан с личными контактами (Группа А), "
                        "с услугами компании (Группа Б), или это общий вопрос (Группа В)?"
                    ),
                    "model_used": "system",
                    "processing_time": round(time.time() - start_time, 3),
                    "session_id": session_id,
                    "group": None,
                    "requires_identification": True,
                }

        # 3. Сохраняем сообщение пользователя
        await self.dialog.save_message(db, session_id, client_id, channel, "user", message)

        # 4. История
        history = await self.dialog.get_history(db, session_id, limit=10)

        # 5. Поиск знаний (с фильтром по группе)
        knowledge_text = await self._fetch_knowledge(db, message, group)

        # 6. Системный промпт
        system_msg = SYSTEM_PROMPT_CORE + GROUP_CONTEXT.get(group, "")

        # 7. Сообщения для LLM
        messages = [{"role": "system", "content": system_msg}]
        if knowledge_text:
            messages.append({"role": "system", "content": knowledge_text})
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        # 8. LLM (низкая температура = меньше галлюцинаций и размышлений)
        try:
            result = await self.llm.generate("openai", messages, temperature=0.2)
            response_text = result["content"]
            model_used = "openai"
            tokens = result.get("tokens_prompt", 0) + result.get("tokens_completion", 0)
        except Exception as e:
            logger.error(f"[Chat] LLM ошибка: {e}")
            response_text = "Ошибка сервиса. Попробуйте позже."
            model_used = "error"
            tokens = 0

        # 9. Сохраняем ответ
        await self.dialog.save_message(
            db, session_id, client_id, channel, "assistant", response_text,
            model_used=model_used, tokens_used=tokens
        )

        return {
            "response": response_text,
            "model_used": model_used,
            "processing_time": round(time.time() - start_time, 3),
            "session_id": session_id,
            "group": group,
            "requires_identification": False,
        }

    def _detect_group(self, text: str) -> str | None:
        """Определяет группу по ключевым словам."""
        t = text.lower()
        for grp, keywords in GROUP_KEYWORDS.items():
            for kw in keywords:
                if kw in t:
                    return grp
        return None

    async def _fetch_knowledge(self, db: AsyncSession, query: str, group: str) -> str:
        """Ищет знания и фильтрует по группе."""
        try:
            results = await search_knowledge(db, query, limit=5)
            if not results:
                return ""
            
            lines = []
            for r in results:
                tags = r.get("tags", [])
                # Группа А видит всё
                if group == "A":
                    lines.append(f"- {r['title']}")
                # Группа Б — услуги, прайс
                elif group == "B" and any(t in ["группа_б", "услуги", "прайс", "цена"] for t in tags):
                    lines.append(f"- {r['title']}")
                # Группа В — только общие
                elif group == "C" and any(t in ["общее", "группа_в", "faq"] for t in tags):
                    lines.append(f"- {r['title']}")
            
            return "Контекст:\n" + "\n".join(lines) if lines else ""
        except Exception as e:
            logger.warning(f"[Chat] Поиск знаний: {e}")
            return ""
