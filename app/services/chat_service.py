"""Chat Service — обработка сообщений с идентификацией группы и RAG."""
import time
import traceback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.llm_service import LLMService
from app.memory.dialog_manager import DialogManager
from app.utils.logger import setup_logging

logger = setup_logging()

GROUP_A_ORGS = [
    "газпром инвест", "газстройпром", "системы управления",
    "ленгазспецстрой", "стройтранснефтегаз", "газпром", "газ строй",
]

GROUP_KEYWORDS = {
    "A": ["газпром", "газстройпром", "системы управления", "ленгазспецстрой", "стройтранснефтегаз", "корпоративн", "ооо", "ао"],
    "B": ["услуг", "лендинг", "сайт", "цена", "заказ", "прайс", "услуга", "стоимость", "калькулятор", "разработка", "дизайн", "seo", "реклама", "контент", "продвижение", "маркетинг"],
    "C": ["семья", "друг", "личн", "знаком", "родственник", "дом", "дружб"],
}

IDENTIFICATION_QUESTION = (
    "Здравствуйте! Я высокотехнологичный сотрудник Bestconsulting. "
    "Уточните, из какой вы организации и представьтесь?"
)

GROUP_CONTEXT = {
    "A": "Клиент Группы А (Корпоративный: Газпром инвест, Газстройпром, Системы управления, Ленгазспецстрой, СтройТрансНефтегаз). Стиль: строгий деловой. НЕ предлагать услуги Bestconsulting. НЕ брать деньги. ",
    "B": "Клиент Группы Б (Клиент Bestconsulting). Стиль: экспертный/консультационный. Услуги по прайсу. ",
    "C": "Клиент Группы В (Личные контакты: семья, друзья). Стиль: тёплый личный. НИКАКИХ продаж и цен. ",
}


def _load_system_prompt() -> str:
    try:
        with open("app/prompts/system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return (
            "Ты — Bestconsulting, Senior specialist (10+ лет опыта). "
            "Правила ответа: 1. ТОЛЬКО конкретный ответ. Без размышлений. "
            "2. Без вводных фраз. 3. Если не знаешь — скажи 'Нет данных'. 4. Кратко. По существу."
        )


class ChatService:
    def __init__(self):
        self.llm = LLMService()
        self.dialog = DialogManager()
        self.system_prompt = _load_system_prompt()

    async def process_message(self, db: AsyncSession, client_id: str, channel: str, message: str) -> dict:
        try:
            return await self._process(db, client_id, channel, message)
        except Exception as e:
            err = traceback.format_exc()
            logger.error(f"[Chat] CRITICAL ERROR: {err}")
            # Возвращаем ПОЛНЫЙ traceback для диагностики
            return {
                "response": f"Ошибка: {str(e)[:200]}",
                "model_used": "error",
                "processing_time": 0,
                "session_id": f"{client_id}_{channel}",
                "group": None,
                "error_detail": err[:1000],  # Полный traceback
            }

    async def _process(self, db: AsyncSession, client_id: str, channel: str, message: str) -> dict:
        start_time = time.time()
        session_id = f"{client_id}_{channel}"

        client = await self.dialog._get_or_create_client(db, client_id, channel)
        group = await self.dialog.get_client_group(db, client_id)
        history = await self.dialog.get_history(db, session_id, limit=5)

        if not group:
            if not history:
                await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
                await self.dialog.save_message(
                    db, session_id, client_id, channel, "assistant", IDENTIFICATION_QUESTION
                )
                return {
                    "response": IDENTIFICATION_QUESTION,
                    "model_used": "system",
                    "processing_time": round(time.time() - start_time, 3),
                    "session_id": session_id,
                    "group": None,
                    "requires_identification": True,
                }

            group = await self._detect_group_advanced(db, message)
            if group:
                await self.dialog.set_client_group(db, client_id, group)
                logger.info(f"[Chat] Клиент {client_id} → Группа {group}")
            else:
                group = "B"
                await self.dialog.set_client_group(db, client_id, group)
                logger.info(f"[Chat] Клиент {client_id} → Группа B (по умолчанию)")

        # Проверка pending escalation
        pending = await self.dialog.get_pending_escalation(db, client_id)
        if pending:
            contacts = {"info": message, "provided_at": time.time()}
            await self.dialog.set_client_contacts(db, client_id, contacts)
            await self.dialog.clear_pending_escalation(db, client_id)
            
            context_msgs = [h["content"] for h in history[-5:] if h["role"] == "user"]
            context_summary = " | ".join(context_msgs)[:400] if context_msgs else "Запрос через чат-бот"
            
            from app.services.escalation_service import create_escalation, EscalationPriority
            esc = await create_escalation(
                db=db,
                session_id=session_id,
                client_id=client_id,
                channel=channel,
                trigger_reason=pending["reason"],
                trigger_message=context_summary,
                context_summary=f"Потребность клиента: {context_summary}",
                recommendation=f"Контакты для связи: {message[:200]}",
                priority=EscalationPriority(pending["priority"]),
                group=pending["group"],
            )
            
            response_text = (
                "Спасибо! Ваш запрос с контактными данными передан руководителю. "
                "Ожидайте связи в ближайшее время."
            )
            
            await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
            await self.dialog.save_message(
                db, session_id, client_id, channel, "assistant", response_text,
                model_used="escalation", tokens_used=0
            )
            
            return {
                "response": response_text,
                "model_used": "escalation",
                "processing_time": round(time.time() - start_time, 3),
                "session_id": session_id,
                "group": pending["group"],
                "escalation": True,
                "escalation_id": esc.id,
            }

        # Эскалация
        from app.services.escalation_service import detect_escalation, create_escalation, EscalationPriority
        
        needs_esc, reason, priority = detect_escalation(message, group or "B")
        
        if needs_esc:
            contacts = await self.dialog.get_client_contacts(db, client_id)
            
            if not contacts or not contacts.get("info"):
                await self.dialog.set_pending_escalation(db, client_id, {
                    "reason": reason,
                    "priority": priority.value,
                    "group": group
                })
                await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
                
                response_text = (
                    "Ваш запрос требует внимания руководителя. "
                    "Для оперативной связи, прошу направить ваши контакты: имя, телефон, email."
                )
                await self.dialog.save_message(
                    db, session_id, client_id, channel, "assistant", response_text,
                    model_used="system", tokens_used=0
                )
                
                return {
                    "response": response_text,
                    "model_used": "system",
                    "processing_time": round(time.time() - start_time, 3),
                    "session_id": session_id,
                    "group": group,
                    "awaiting_contacts": True,
                }
            
            context_msgs = [h["content"] for h in history[-5:] if h["role"] == "user"]
            context_summary = " | ".join(context_msgs)[:400] if context_msgs else "Запрос через чат-бот"
            
            esc = await create_escalation(
                db=db,
                session_id=session_id,
                client_id=client_id,
                channel=channel,
                trigger_reason=reason,
                trigger_message=message,
                context_summary=f"Потребность: {context_summary}",
                recommendation=f"Контакты клиента: {contacts.get('info', 'Нет')[:200]}",
                priority=priority,
                group=group,
            )
            
            response_text = (
                "Ваш запрос требует внимания руководителя. "
                "Информация передана. Ожидайте ответа."
            )
            
            await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
            await self.dialog.save_message(
                db, session_id, client_id, channel, "assistant", response_text,
                model_used="escalation", tokens_used=0
            )
            
            return {
                "response": response_text,
                "model_used": "escalation",
                "processing_time": round(time.time() - start_time, 3),
                "session_id": session_id,
                "group": group,
                "escalation": True,
                "escalation_id": esc.id,
            }

        # Обычный диалог
        await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
        history = await self.dialog.get_history(db, session_id, limit=10)
        knowledge_text = await self._fetch_knowledge(db, message, group)

        system_msg = self.system_prompt + "\n\n" + GROUP_CONTEXT.get(group, "")

        messages = [{"role": "system", "content": system_msg}]
        if knowledge_text:
            messages.append({"role": "system", "content": knowledge_text})
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        try:
            result = await self.llm.generate("openai", messages, temperature=0.2)
            response_text = result["content"]
            model_used = result.get("model", "openai")
            tokens = result.get("tokens_prompt", 0) + result.get("tokens_completion", 0)
        except Exception as e:
            logger.error(f"[Chat] LLM ошибка: {e}")
            response_text = f"Ошибка LLM: {str(e)[:200]}"
            model_used = "error"
            tokens = 0

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

    def _detect_group(self, text: str):
        t = text.lower()
        for org in GROUP_A_ORGS:
            if org in t:
                return "A"
        for grp, keywords in GROUP_KEYWORDS.items():
            for kw in keywords:
                if kw in t:
                    return grp
        return None

    async def _detect_group_advanced(self, db: AsyncSession, text: str) -> str:
        t = text.lower()
        for org in GROUP_A_ORGS:
            if org in t:
                return "A"
        for kw in GROUP_KEYWORDS["C"]:
            if kw in t:
                return "C"
        for kw in GROUP_KEYWORDS["B"]:
            if kw in t:
                return "B"
        try:
            sql = text("""
                SELECT title, tags 
                FROM knowledge_items 
                WHERE verified = true 
                  AND tags @> '["группа_а"]'
                  AND (title ILIKE :q OR original_content ILIKE :q)
                LIMIT 1
            """)
            result = await db.execute(sql, {"q": f"%{text[:50]}%"})
            row = result.mappings().first()
            if row:
                return "A"
        except Exception as e:
            logger.warning(f"[Chat] Поиск организации: {e}")
        return None

    async def _fetch_knowledge(self, db: AsyncSession, query: str, group: str) -> str:
        try:
            sql = text("""
                SELECT title, original_content, tags 
                FROM knowledge_items 
                WHERE verified = true 
                  AND (title ILIKE :q OR original_content ILIKE :q)
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            result = await db.execute(sql, {"q": f"%{query}%"})
            rows = result.mappings().all()
            if not rows:
                return ""
            parts = []
            for r in rows:
                content = r.get('original_content', '') or ''
                parts.append(f"=== {r['title']} ===\n{content[:1000]}")
            return "\n\n".join(parts) if parts else ""
        except Exception as e:
            logger.warning(f"[Chat] Поиск знаний: {e}")
            return ""
