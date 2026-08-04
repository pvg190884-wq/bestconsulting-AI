"""Chat Service — обработка сообщений с идентификацией группы, руководителя и RAG."""
import time
import traceback
import json
import re
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.llm_service import LLMService
from app.services.founder_service import FounderService
from app.services.document_generator import build_xlsx, build_pptx, build_pdf
from app.services import dzen_service
from app.services import dubai_jobs_service
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

REMEMBER_TRIGGERS = [
    "запомни", "сохрани в баз", "сохрани в базу", "занеси в базу",
    "добавь в базу знаний", "зафиксируй в базе", "запиши в базу",
    "сохранить информацию", "нужно сохранить", "сохрани эту",
    "занеси эту", "сохранить в базу", "сохранить в базе",
]

DOCUMENT_REFERENCE_WORDS = [
    "документ", "файл", "детализирова", "подробн", "полную информацию",
    "все пункты", "веху", "вехи", "названия", "сроки", "подъобъект", "пункт",
    "сохранил", "сохранено", "сохранённ", "что ты сохранил", "базе знаний сохран",
    "какую информацию", "покажи что",
]

WHO_AM_I_PHRASES = [
    "кто я", "ты знаешь кто я", "как меня зовут", "кто я такой", "узнаешь меня",
]

NAME_PATTERNS = [
    re.compile(r"меня зовут ([А-ЯЁ][а-яё]+)", re.IGNORECASE),
    re.compile(r"я\s*[—\-–]\s*([А-ЯЁ][а-яё]+)\b"),
]

STOPWORDS = {
    "нужен", "нужна", "нужно", "нужны", "какие", "какой", "какая", "какое",
    "что", "это", "вы", "ты", "мне", "ли", "есть", "добрый", "день", "дент",
    "утро", "вечер", "привет", "пожалуйста", "для", "как", "чем", "можете",
    "можно", "хочу", "хочется", "меня", "тебя", "она", "они", "оно", "или",
    "на", "по", "из", "от", "до", "за", "при", "уже", "ещё", "тоже", "так",
}

IDENTIFICATION_QUESTION = (
    "Здравствуйте! Я высокотехнологичный сотрудник Bestconsulting. "
    "Уточните, из какой вы организации и представьтесь?"
)

GROUP_CONTEXT = {
    "A": "Клиент Группы А (Корпоративный: Газпром инвест, Газстройпром, Системы управления, Ленгазспецстрой, СтройТрансНефтегаз). Стиль: строгий деловой. НЕ предлагать услуги Bestconsulting. НЕ брать деньги. ",
    "B": "Клиент Группы Б (Клиент Bestconsulting). Стиль: экспертный/консультационный. Услуги по прайсу. ",
    "C": (
        "Клиент Группы В (Личные контакты: семья, друзья). Стиль: тёплый, живой, неформальный личный. "
        "НИКАКИХ продаж, цен и услуг. Можно свободно поддерживать разговор на любые темы "
        "(погода, настроение, общие темы) — это нормальное живое общение, а не консультация. "
    ),
    "FOUNDER": (
        "Ты общаешься с ОСНОВАТЕЛЕМ и руководителем компании Bestconsulting — Павлов Вадим Геннадьевич. "
        "Если он спрашивает 'кто я', 'ты знаешь кто я' или подобное — отвечай прямо: он основатель и руководитель Bestconsulting, Вадим Геннадьевич. "
        "Правило передачи менеджеру (эскалация клиентских заказов Группы Б) к тебе НЕ применяется — ты и есть руководитель, "
        "не отвечай фразой 'ваш запрос принят, передам руководителю' на его собственные просьбы. "
        "Правило верификации документов (требование подтвердить 'это подписанный документ?') относится ТОЛЬКО к клиентам Группы А "
        "и НИКОГДА не применяется к самому основателю — он может сохранять любую информацию в базу знаний сразу по команде "
        "«запомни»/«сохрани», без запроса подтверждения о подписи документа. "
        "У тебя ЕСТЬ функции: сохранение информации в базу знаний, приём и анализ файлов (TXT, PDF, Excel, PowerPoint, JPG, PNG), "
        "формирование докладов/презентаций/таблиц через команду /доклад, генерация черновиков статей через /статья, "
        "автоматизированная серия статей для Дзен через /дзен_старт /дзен_стоп /дзен_статус, "
        "ежедневные посты про рынок труда Дубая через /дубай_старт /дубай_стоп /дубай_статус /дубай_тест. "
        "Никогда не говори, что не можешь сохранять информацию или анализировать документы/изображения — эти функции у тебя есть. "
        "Стиль: уважительный, оперативный, инициативный. Исполнять все поручения. Докладывать о результатах. "
    ),
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
        self.founder = FounderService()
        self.system_prompt = _load_system_prompt()

    # ---------- Вспомогательные детекторы ----------

    def _is_remember_request(self, message: str) -> bool:
        if not message:
            return False
        t = message.lower()
        return any(trig in t for trig in REMEMBER_TRIGGERS)

    def _extract_remember_content(self, message: str) -> str:
        t = message.lower()
        for trig in REMEMBER_TRIGGERS:
            idx = t.find(trig)
            if idx != -1:
                rest = message[idx + len(trig):].strip(" :,-—")
                return rest if rest else message
        return message

    def _references_document(self, message: str) -> bool:
        t = message.lower()
        return any(w in t for w in DOCUMENT_REFERENCE_WORDS)

    def _is_who_am_i(self, message: str) -> bool:
        t = message.lower().strip("?!. ")
        return any(phrase in t for phrase in WHO_AM_I_PHRASES)

    def _extract_name(self, message: str) -> str | None:
        for pattern in NAME_PATTERNS:
            m = pattern.search(message)
            if m:
                return m.group(1)
        return None

    async def _maybe_learn_style(self, db: AsyncSession, client_id: str, message: str):
        name = self._extract_name(message)
        if name:
            try:
                await self.dialog.set_client_style(db, client_id, {"name": name})
                logger.info(f"[Chat] Имя контакта сохранено: {name} ({client_id})")
            except Exception as e:
                logger.warning(f"[Chat] Не удалось сохранить имя: {e}")

    async def _generate_creative(self, messages: list[dict]) -> str:
        api_key = getattr(self.llm, "api_key", None)
        base_url = getattr(self.llm, "base_url", None) or "https://openrouter.ai/api/v1"

        if api_key:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": "deepseek/deepseek-chat", "messages": messages, "temperature": 0.8},
                    )
                    r.raise_for_status()
                    data = r.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"[Chat] Creative (DeepSeek) недоступен, fallback: {e}")

        try:
            result = await self.llm.generate("openai", messages, temperature=0.8)
            return result.get("content", "")
        except Exception:
            return "Извините, не могу сейчас ответить, но обязательно вернусь к разговору чуть позже."

    # ---------- Обработка входящих текстовых сообщений ----------

    async def process_message(self, db: AsyncSession, client_id: str, channel: str, message: str) -> dict:
        try:
            return await self._process(db, client_id, channel, message)
        except Exception as e:
            err = traceback.format_exc()
            logger.error(f"[Chat] CRITICAL ERROR: {err}")
            try:
                await db.rollback()
            except Exception:
                pass
            return {
                "response": "Ошибка сервера. Попробуйте ещё раз.",
                "model_used": "error",
                "processing_time": 0,
                "session_id": f"{client_id}_{channel}",
                "group": None,
                "error_detail": err[:500],
            }

    # ---------- Обработка файлов (п.3 и п.4) ----------

    async def process_file(self, db: AsyncSession, client_id: str, channel: str,
                            extracted_text: str, filename: str, caption: str = "") -> dict:
        session_id = f"{client_id}_{channel}"
        try:
            is_founder = self.founder.is_founder(client_id, channel)
            client = await self.dialog._get_or_create_client(db, client_id, channel)
            group = await self.dialog.get_client_group(db, client_id)

            if is_founder and group != "FOUNDER":
                group = "FOUNDER"
                await self.dialog.set_client_group(db, client_id, "FOUNDER")

            if not extracted_text or not extracted_text.strip():
                return {
                    "response": "Не удалось извлечь текст из файла. Поддерживаются: TXT, PDF, Excel, PowerPoint, JPG, PNG.",
                    "model_used": "system", "session_id": session_id, "group": group,
                }

            if not group:
                await self.dialog.save_message(db, session_id, client_id, channel, "user", f"[Файл: {filename}]")
                await self.dialog.save_message(db, session_id, client_id, channel, "assistant", IDENTIFICATION_QUESTION)
                return {
                    "response": IDENTIFICATION_QUESTION, "model_used": "system",
                    "session_id": session_id, "group": None, "requires_identification": True,
                }

            await self.dialog.set_last_document(db, client_id, {"text": extracted_text, "filename": filename})

            wants_remember = self._is_remember_request(caption)

            if wants_remember:
                if group == "FOUNDER":
                    res = await self.founder.save_founder_knowledge(
                        db, extracted_text, title=f"Файл от основателя: {filename}"
                    )
                    response_text = (
                        f"✅ Файл «{filename}» сохранён в базу знаний (ID: {res['id']})."
                        if res["success"] else f"❌ Ошибка сохранения файла: {res.get('error')}"
                    )
                    await self.dialog.save_message(db, session_id, client_id, channel, "user", f"[Файл: {filename}] {caption}".strip())
                    await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)
                    return {"response": response_text, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

                if group == "A":
                    await self.dialog.set_pending_document(
                        db, client_id, {"text": extracted_text[:8000], "filename": filename}
                    )
                    response_text = (
                        f"Получен файл «{filename}». Это официальный подписанный документ для базы знаний? "
                        f"Ответьте «да» для подтверждения."
                    )
                    await self.dialog.save_message(db, session_id, client_id, channel, "user", f"[Файл: {filename}] {caption}".strip())
                    await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)
                    return {
                        "response": response_text, "model_used": "system",
                        "session_id": session_id, "group": "A", "awaiting_verification": True,
                    }

                response_text = (
                    "База знаний пополняется только по официально подтверждённым документам "
                    "от партнёров группы А или поручениям основателя."
                )
                await self.dialog.save_message(db, session_id, client_id, channel, "user", f"[Файл: {filename}] {caption}".strip())
                await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)
                return {"response": response_text, "model_used": "system", "session_id": session_id, "group": group}

            question = caption.strip() if caption and caption.strip() else "Проанализируй содержимое документа детально: перечисли ВСЕ пункты, даты и названия без сокращений."
            system_msg = self.system_prompt + "\n\n" + GROUP_CONTEXT.get(group, "")
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "system", "content": (
                    f"Тебе УЖЕ ПРЕДОСТАВЛЕНО содержимое присланного файла «{filename}» — оно распознано и приведено ниже целиком. "
                    f"НИКОГДА не говори, что не можешь просмотреть/проанализировать изображение или документ — ты его уже видишь в виде текста ниже. "
                    f"Это разовый анализ, документ НЕ сохраняется в базу знаний автоматически. "
                    f"Отвечай на основе ВСЕГО текста ниже, не сокращай и не обобщай пункты, если явно не попросили краткую сводку.\n\n"
                    f"{extracted_text[:8000]}"
                )},
                {"role": "user", "content": question},
            ]
            try:
                result = await self.llm.generate("openai", messages, temperature=0.2)
                response_text = result["content"]
                model_used = result.get("model", "openai")
            except Exception as e:
                logger.error(f"[Chat] Ошибка анализа файла: {e}")
                response_text = "Не удалось проанализировать файл. Попробуйте ещё раз."
                model_used = "error"

            await self.dialog.save_message(db, session_id, client_id, channel, "user", f"[Файл: {filename}] {caption}".strip())
            await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text, model_used=model_used)
            return {"response": response_text, "model_used": model_used, "session_id": session_id, "group": group}

        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            logger.error(f"[Chat] Ошибка обработки файла: {traceback.format_exc()}")
            return {
                "response": "Ошибка при обработке файла. Попробуйте ещё раз.",
                "model_used": "error", "session_id": session_id, "group": None,
            }

    # ---------- Основной обработчик ----------

    async def _process(self, db: AsyncSession, client_id: str, channel: str, message: str) -> dict:
        start_time = time.time()
        session_id = f"{client_id}_{channel}"

        try:
            is_founder = self.founder.is_founder(client_id, channel)

            client = await self.dialog._get_or_create_client(db, client_id, channel)
            group = await self.dialog.get_client_group(db, client_id)
            history = await self.dialog.get_history(db, session_id, limit=5)

            if is_founder and group != "FOUNDER":
                group = "FOUNDER"
                await self.dialog.set_client_group(db, client_id, "FOUNDER")
                logger.info(f"[Chat] Основатель идентифицирован: {client_id}")

            if group == "FOUNDER":
                return await self._process_founder(db, client_id, channel, message, history, start_time, session_id)

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

            await self._maybe_learn_style(db, client_id, message)

            pending_doc = await self.dialog.get_pending_document(db, client_id)
            if pending_doc:
                if message.strip().lower() in ["да", "yes", "подтверждаю", "верно"]:
                    res = await self.founder.save_founder_knowledge(
                        db, pending_doc["text"],
                        title=f"Документ от группы А: {pending_doc.get('filename') or 'без файла'}"
                    )
                    try:
                        await db.execute(text("""
                            UPDATE knowledge_items 
                            SET tags = array_append(tags, 'группа_а_подписано') 
                            WHERE id = :kid
                        """), {"kid": res["id"]})
                        await db.commit()
                    except Exception:
                        await db.rollback()

                    await self.dialog.clear_pending_document(db, client_id)
                    response_text = (
                        f"✅ Документ верифицирован и сохранён (ID: {res['id']}). "
                        f"Версия: v1. Дата: {datetime.now().strftime('%Y-%m-%d')}."
                    )
                    await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
                    await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)
                    return {
                        "response": response_text, "model_used": "system",
                        "processing_time": round(time.time() - start_time, 3),
                        "session_id": session_id, "group": "A",
                    }
                else:
                    await self.dialog.clear_pending_document(db, client_id)

            if self._is_remember_request(message):
                content = self._extract_remember_content(message)

                if self._references_document(message):
                    last_doc = await self.dialog.get_last_document(db, client_id)
                    if last_doc and last_doc.get("text"):
                        content = last_doc["text"]

                if group == "A":
                    await self.dialog.set_pending_document(db, client_id, {"text": content, "filename": None})
                    response_text = "Это официальный подписанный документ для базы знаний? Ответьте «да» для подтверждения."
                else:
                    response_text = (
                        "База знаний пополняется только по официально подтверждённым документам "
                        "от партнёров группы А или поручениям основателя."
                    )
                await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
                await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)
                return {
                    "response": response_text, "model_used": "system",
                    "processing_time": round(time.time() - start_time, 3),
                    "session_id": session_id, "group": group,
                }

            if group == "A" and len(message) > 50:
                return await self._handle_group_a_document(db, client_id, channel, message, history, start_time, session_id)

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
                    "Спасибо! Ваш запрос принят, я всё рассчитаю и мы обязательно с вами свяжемся. "
                    "Информация с вашими контактами передана руководителю."
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
                        "Оставьте, пожалуйста, ваши контакты для связи (имя, телефон или email)."
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

            await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
            history = await self.dialog.get_history(db, session_id, limit=10)

            client_style = await self.dialog.get_client_style(db, client_id)
            name_hint = f"Обращайся к собеседнику по имени: {client_style['name']}. " if client_style.get("name") else ""

            if group == "C":
                system_msg = self.system_prompt + "\n\n" + GROUP_CONTEXT["C"] + name_hint
                messages = [{"role": "system", "content": system_msg}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
                messages.append({"role": "user", "content": message})

                response_text = await self._generate_creative(messages)
                model_used = "deepseek/deepseek-chat"

                await self.dialog.save_message(
                    db, session_id, client_id, channel, "assistant", response_text,
                    model_used=model_used
                )
                return {
                    "response": response_text,
                    "model_used": model_used,
                    "processing_time": round(time.time() - start_time, 3),
                    "session_id": session_id,
                    "group": group,
                }

            document_context = ""
            if self._references_document(message):
                last_doc = await self.dialog.get_last_document(db, client_id)
                if last_doc and last_doc.get("text"):
                    document_context = (
                        f"Ранее присланный документ «{last_doc.get('filename', '')}» "
                        f"(используй для ответа на текущий вопрос):\n\n{last_doc['text'][:8000]}"
                    )

            knowledge_text = await self._fetch_knowledge(db, message, group)

            system_msg = self.system_prompt + "\n\n" + GROUP_CONTEXT.get(group, "") + name_hint
            system_msg += (
                "\n\nВАЖНО: отвечай ТОЛЬКО на основе предоставленной базы знаний (см. ниже) и текущих правил. "
                "Если информации нет в базе знаний — ответь 'Нет данных.' Не выдумывай факты, цены или обещания от имени компании."
            )

            messages = [{"role": "system", "content": system_msg}]
            if document_context:
                messages.append({"role": "system", "content": document_context})
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

        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            raise

    # ---------- Обработка сообщений основателя ----------

    async def _process_founder(self, db, client_id, channel, message, history, start_time, session_id):
        try:
            cmd, arg = self.founder.parse_command(message)

            if not history:
                welcome = "Здравствуйте, Вадим Геннадьевич! Я готов к работе. Что поручите?"
                await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
                await self.dialog.save_message(db, session_id, client_id, channel, "assistant", welcome)
                return {
                    "response": welcome,
                    "model_used": "system",
                    "processing_time": round(time.time() - start_time, 3),
                    "session_id": session_id,
                    "group": "FOUNDER",
                }

            if self._is_who_am_i(message):
                response_text = (
                    "Вы — Павлов Вадим Геннадьевич, основатель и руководитель Bestconsulting. "
                    "Я готов исполнять ваши поручения."
                )
                await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
                await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)
                return {
                    "response": response_text, "model_used": "system",
                    "processing_time": round(time.time() - start_time, 3),
                    "session_id": session_id, "group": "FOUNDER",
                }

            if cmd == "/задача":
                if not arg:
                    return {"response": "Укажите текст поручения после команды. Пример: /задача собрать 100 подписчиков", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                res = await self.founder.create_task(db, arg[:200], arg)
                if res["success"]:
                    return {"response": f"✅ Поручение создано: {res['title']}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                return {"response": f"❌ Ошибка: {res.get('error')}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/отчет":
                stats = await self.founder.get_stats(db)
                report_text = (
                    f"📊 Отчёт ({stats.get('timestamp', 'сейчас')}):\n"
                    f"• Всего контактов: {stats.get('total_clients', 0)}\n"
                    f"• По группам: {stats.get('by_group', {})}\n"
                    f"• По каналам: {stats.get('by_channel', {})}\n"
                    f"• Эскалаций за неделю: {stats.get('escalations_week', 0)}\n"
                    f"• Записей в базе знаний: {stats.get('knowledge_items', 0)}"
                )
                return {"response": report_text, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/база":
                if not arg:
                    return {"response": "Укажите текст для сохранения. Пример: /база Новый тариф на лендинг: 35 000 руб", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                res = await self.founder.save_founder_knowledge(db, arg)
                if res["success"]:
                    return {"response": f"✅ Сохранено в базу знаний (ID: {res['id']})", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                return {"response": f"❌ Ошибка сохранения: {res.get('error')}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/подписчики":
                stats = await self.founder.get_stats(db)
                by_ch = stats.get("by_channel", {})
                return {
                    "response": f"📢 Подписчики:\n• Telegram: {by_ch.get('telegram', 0)}\n• MAX: {by_ch.get('max', 0)}\n• Всего: {stats.get('total_clients', 0)}",
                    "model_used": "system", "session_id": session_id, "group": "FOUNDER"
                }

            if cmd == "/ютуб":
                return {
                    "response": "📺 YouTube-канал:\n• Статус: интеграция в разработке\n• Для подключения статистики необходим API-ключ YouTube Data API\n• Контент-план формируется по запросу.",
                    "model_used": "system", "session_id": session_id, "group": "FOUNDER"
                }

            if cmd == "/медиа":
                if not arg:
                    return {"response": "Укажите описание. Пример: /медиа логотип Bestconsulting, синий фон, минимализм", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                res = await self.founder.generate_media(arg)
                if res["success"]:
                    return {
                        "response": f"🎨 Изображение сгенерировано:\n{res['url']}\n\nПромпт: {res['prompt']}\n\nСкачайте по ссылке (действительно 24 часа).",
                        "model_used": "system", "session_id": session_id, "group": "FOUNDER"
                    }
                return {"response": f"❌ Ошибка генерации: {res.get('error')}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/доклад":
                if not arg:
                    return {"response": "Укажите тему. Пример: /доклад анализ эскалаций за месяц (excel/презентация — по ключевым словам в теме)", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

                arg_lower = arg.lower()
                if any(w in arg_lower for w in ["презентация", "powerpoint", "слайд", "pptx"]):
                    fmt = "pptx"
                elif any(w in arg_lower for w in ["excel", "таблиц", "сводн", "xlsx"]):
                    fmt = "xlsx"
                else:
                    fmt = "pdf"

                knowledge_text = await self._fetch_knowledge(db, arg, "FOUNDER")
                last_doc = await self.dialog.get_last_document(db, client_id)
                doc_context = last_doc["text"][:8000] if (last_doc and self._references_document(arg)) else ""

                if fmt == "xlsx":
                    struct_instruction = (
                        "Сформируй данные для сводной таблицы Excel по теме запроса. "
                        "Ответь СТРОГО валидным JSON без markdown, без пояснений, в формате: "
                        '{"headers": ["Колонка1", "Колонка2", ...], "rows": [["значение", "значение", ...], ...]}'
                    )
                elif fmt == "pptx":
                    struct_instruction = (
                        "Сформируй структуру презентации по теме запроса (5-8 слайдов). "
                        "Ответь СТРОГО валидным JSON без markdown, без пояснений, в формате: "
                        '{"slides": [{"title": "Заголовок слайда", "bullets": ["пункт 1", "пункт 2"]}, ...]}'
                    )
                else:
                    struct_instruction = (
                        "Сформируй структуру аналитического доклада по теме запроса, максимально подробно, "
                        "не сокращай детали. Ответь СТРОГО валидным JSON без markdown, без пояснений, в формате: "
                        '{"sections": [{"heading": "Заголовок раздела", "text": "Текст раздела"}, ...]}'
                    )

                gen_messages = [{"role": "system", "content": struct_instruction}]
                if doc_context:
                    gen_messages.append({"role": "system", "content": f"Содержимое ранее присланного документа:\n{doc_context}"})
                if knowledge_text:
                    gen_messages.append({"role": "system", "content": f"База знаний по теме:\n{knowledge_text}"})
                gen_messages.append({"role": "user", "content": arg})

                try:
                    result = await self.llm.generate("openai", gen_messages, temperature=0.3)
                    raw = result["content"].strip()
                    if raw.startswith("```"):
                        raw = raw.strip("`")
                        if raw.lower().startswith("json"):
                            raw = raw[4:].strip()
                    data = json.loads(raw)

                    if fmt == "xlsx":
                        file_bytes = build_xlsx(arg[:60], data.get("headers", []), data.get("rows", []))
                        filename = "отчет.xlsx"
                    elif fmt == "pptx":
                        file_bytes = build_pptx(arg[:60], data.get("slides", []))
                        filename = "презентация.pptx"
                    else:
                        file_bytes = build_pdf(arg[:60], data.get("sections", []))
                        filename = "доклад.pdf"

                    return {
                        "response": f"📄 Готово: «{arg}». Файл прикреплён.",
                        "model_used": result.get("model", "openai"),
                        "session_id": session_id, "group": "FOUNDER",
                        "attachments": [{"bytes": file_bytes, "filename": filename}],
                    }
                except Exception as e:
                    logger.error(f"[Chat] Ошибка генерации файла-доклада: {e}")
                    return {"response": f"❌ Не удалось сформировать файл: {str(e)[:200]}", "model_used": "error", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/статья":
                if not arg:
                    return {"response": "Укажите тему или нишу. Пример: /статья психология отношений в браке", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

                struct_instruction = (
                    "Ты — редактор канала Bestconsulting на Дзен. Текущий год — 2026, не упоминай 2025 год как актуальный. "
                    "Напиши статью по указанной теме/нише. "
                    "Требования: заголовок кликабельный, но не желтушный, не длиннее 128 символов; объём 600-1000 слов; "
                    "структура — вступление-крючок, 3-4 смысловых блока с подзаголовками, заключение с призывом подписаться; "
                    "живой разговорный стиль, конкретные примеры, риторические вопросы к читателю; без ссылок внутри текста; "
                    "текст не должен читаться как очевидный, шаблонный ИИ-текст. "
                    "Ответь СТРОГО валидным JSON без markdown и пояснений, в формате: "
                    '{"title_options": ["вариант1", "вариант2", "вариант3"], "article_text": "полный текст статьи", '
                    '"description": "краткое описание для превью, 150-200 символов", "tags": ["тег1", "тег2", "тег3"], '
                    '"image_prompt": "короткое описание обложки на английском для генерации изображения"}'
                )

                gen_messages = [
                    {"role": "system", "content": struct_instruction},
                    {"role": "user", "content": arg},
                ]

                try:
                    result = await self.llm.generate("openai", gen_messages, temperature=0.7)
                    raw = result["content"].strip()
                    if raw.startswith("```"):
                        raw = raw.strip("`")
                        if raw.lower().startswith("json"):
                            raw = raw[4:].strip()
                    data = json.loads(raw)

                    titles = data.get("title_options", [])
                    article_text = data.get("article_text", "")
                    description = data.get("description", "")
                    tags = data.get("tags", [])
                    image_prompt = data.get("image_prompt", arg)

                    txt_content = (
                        "=== BESTCONSULTING — Черновик статьи для Дзен ===\n\n"
                        "ВАРИАНТЫ ЗАГОЛОВКА:\n"
                        + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles)) + "\n\n"
                        f"ОПИСАНИЕ (для превью):\n{description}\n\n"
                        f"ТЕГИ:\n{', '.join(tags)}\n\n"
                        "======================\n"
                        "ТЕКСТ СТАТЬИ:\n"
                        "======================\n\n"
                        f"{article_text}"
                    )

                    attachments = [{"bytes": txt_content.encode("utf-8"), "filename": "статья_дзен.txt"}]

                    media_res = await self.founder.generate_media(image_prompt, width=1200, height=675)
                    if media_res.get("success"):
                        try:
                            import httpx
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                img_r = await client.get(media_res["url"])
                                if img_r.status_code == 200:
                                    attachments.append({"bytes": img_r.content, "filename": "обложка.jpg"})
                        except Exception as e:
                            logger.warning(f"[Chat] Не удалось скачать обложку: {e}")

                    preview_title = titles[0] if titles else arg
                    return {
                        "response": (
                            f"📝 Черновик статьи готов: «{preview_title}»\n\n"
                            f"Файл с текстом статьи, заголовками и тегами + обложка — прикреплены. "
                            f"Скопируйте текст в Дзен-студию и опубликуйте вручную."
                        ),
                        "model_used": result.get("model", "openai"),
                        "session_id": session_id, "group": "FOUNDER",
                        "attachments": attachments,
                    }
                except Exception as e:
                    logger.error(f"[Chat] Ошибка генерации статьи: {e}")
                    return {"response": f"❌ Не удалось сформировать статью: {str(e)[:200]}", "model_used": "error", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/дзен_старт":
                msg = await dzen_service.start_series(db)
                return {"response": msg, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/дзен_стоп":
                msg = await dzen_service.stop_series(db)
                return {"response": msg, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/дзен_статус":
                msg = await dzen_service.status_series(db)
                return {"response": msg, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/дубай_старт":
                msg = await dubai_jobs_service.start_daily_posts(db)
                return {"response": msg, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/дубай_стоп":
                msg = await dubai_jobs_service.stop_daily_posts(db)
                return {"response": msg, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/дубай_статус":
                msg = await dubai_jobs_service.status_daily_posts(db)
                return {"response": msg, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/дубай_тест":
                msg = await dubai_jobs_service.test_post_now(db)
                return {"response": msg, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/контакты":
                try:
                    filter_group = arg.strip() if arg else ""
                    if filter_group:
                        sql = text("SELECT client_id, channel, client_group, extra_data FROM clients WHERE client_group = :g ORDER BY created_at DESC LIMIT 20")
                        r = await db.execute(sql, {"g": filter_group})
                    else:
                        sql = text("SELECT client_id, channel, client_group, extra_data FROM clients ORDER BY created_at DESC LIMIT 20")
                        r = await db.execute(sql)
                    rows = r.mappings().all()
                    lines = ["📋 Контакты:"]
                    for row in rows:
                        extra = row.get("extra_data") or "{}"
                        try:
                            ed = json.loads(extra) if isinstance(extra, str) else extra
                            name = ed.get("style", {}).get("name") or ed.get("name", "—")
                        except Exception:
                            name = "—"
                        lines.append(f"• {name} | {row['client_id']} | {row['channel']} | Группа: {row['client_group'] or '—'}")
                    return {"response": "\n".join(lines), "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                except Exception as e:
                    await db.rollback()
                    return {"response": f"❌ Ошибка: {e}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/очистить":
                await self.dialog.clear_pending_escalation(db, client_id)
                await self.dialog.clear_pending_document(db, client_id)
                await self.dialog.clear_last_document(db, client_id)
                return {"response": "✅ Ожидания сброшены. Готов к новым задачам.", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if self._is_remember_request(message):
                content = self._extract_remember_content(message)

                if self._references_document(message):
                    last_doc = await self.dialog.get_last_document(db, client_id)
                    if last_doc and last_doc.get("text"):
                        content = last_doc["text"]

                res = await self.founder.save_founder_knowledge(db, content)
                response_text = (
                    f"✅ Сохранено в базу знаний (ID: {res['id']})."
                    if res["success"] else f"❌ Ошибка сохранения: {res.get('error')}"
                )
                await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
                await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)
                return {"response": response_text, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            await self.dialog.save_message(db, session_id, client_id, channel, "user", message)

            if len(message) > 30 and any(w in message.lower() for w in ["нужно", "сделай", "собери", "подготовь", "напиши", "создай"]):
                await self.founder.create_task(db, message[:100], message)
                prefix = "✅ Зафиксировал как поручение. "
            else:
                prefix = ""

            document_context = ""
            if self._references_document(message):
                last_doc = await self.dialog.get_last_document(db, client_id)
                if last_doc and last_doc.get("text"):
                    document_context = (
                        f"Ранее присланный документ «{last_doc.get('filename', '')}» "
                        f"(используй для ответа на текущий вопрос, отвечай ПОДРОБНО, без сокращений):\n\n{last_doc['text'][:8000]}"
                    )

            knowledge_text = await self._fetch_knowledge(db, message, "FOUNDER")
            system_msg = self.system_prompt + "\n\n" + GROUP_CONTEXT["FOUNDER"]

            messages = [{"role": "system", "content": system_msg}]
            if document_context:
                messages.append({"role": "system", "content": document_context})
            if knowledge_text:
                messages.append({"role": "system", "content": knowledge_text})
            hist = await self.dialog.get_history(db, session_id, limit=10)
            for h in hist:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            try:
                result = await self.llm.generate("openai", messages, temperature=0.3)
                response_text = prefix + result["content"]
                model_used = result.get("model", "openai")
            except Exception as e:
                response_text = prefix + f"Принято. (Ошибка LLM: {e})"
                model_used = "error"

            await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text, model_used=model_used)

            return {
                "response": response_text,
                "model_used": model_used,
                "processing_time": round(time.time() - start_time, 3),
                "session_id": session_id,
                "group": "FOUNDER",
            }

        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            raise

    async def _handle_group_a_document(self, db, client_id, channel, message, history, start_time, session_id):
        try:
            last_bot = None
            for h in reversed(history):
                if h["role"] == "assistant":
                    last_bot = h["content"]
                    break

            if last_bot and "подписанный документ" in last_bot and message.lower() in ["да", "yes", "подтверждаю", "верно"]:
                prev_msg = None
                for h in reversed(history):
                    if h["role"] == "user" and h["content"] != message:
                        prev_msg = h["content"]
                        break

                if prev_msg:
                    res = await self.founder.save_founder_knowledge(db, prev_msg, title="Документ от группы А (верифицирован)")
                    try:
                        await db.execute(text("""
                            UPDATE knowledge_items 
                            SET tags = array_append(tags, 'группа_а_подписано') 
                            WHERE id = :kid
                        """), {"kid": res["id"]})
                        await db.commit()
                    except Exception:
                        await db.rollback()

                    return {
                        "response": f"✅ Документ верифицирован и сохранён (ID: {res['id']}). Версия: v1. Дата: {datetime.now().strftime('%Y-%m-%d')}.",
                        "model_used": "system",
                        "processing_time": round(time.time() - start_time, 3),
                        "session_id": session_id,
                        "group": "A",
                    }

            response_text = (
                "Получена информация, которая может являться документом. "
                "Для верификации требуется подтверждение: это подписанный документ? "
                "Ответьте 'да' для сохранения или уточните детали."
            )
            await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
            await self.dialog.save_message(db, session_id, client_id, channel, "assistant", response_text)

            return {
                "response": response_text,
                "model_used": "system",
                "processing_time": round(time.time() - start_time, 3),
                "session_id": session_id,
                "group": "A",
                "awaiting_verification": True,
            }
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            raise

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

    async def _detect_group_advanced(self, db: AsyncSession, message_text: str) -> str:
        t = message_text.lower()
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
            result = await db.execute(sql, {"q": f"%{message_text[:50]}%"})
            row = result.mappings().first()
            if row:
                return "A"
        except Exception as e:
            logger.warning(f"[Chat] Поиск организации: {e}")
            await db.rollback()
        return None

    async def _fetch_knowledge(self, db: AsyncSession, query: str, group: str) -> str:
        try:
            raw_words = [w.strip(".,!?:;()\"'«»").lower() for w in query.split()]
            keywords = [w for w in raw_words if len(w) >= 3 and w not in STOPWORDS]

            if not keywords:
                keywords = [query.strip()[:50]] if query.strip() else []
            if not keywords:
                return ""

            keywords = keywords[:8]

            conditions = []
            params = {}
            for i, kw in enumerate(keywords):
                conditions.append(f"(title ILIKE :kw{i} OR original_content ILIKE :kw{i})")
                params[f"kw{i}"] = f"%{kw}%"
            where_clause = " OR ".join(conditions)

            group_tag = f"группа_{group.lower()}" if group else ""

            if group_tag:
                sql = text(f"""
                    SELECT title, original_content, tags 
                    FROM knowledge_items 
                    WHERE verified = true AND ({where_clause})
                    ORDER BY 
                        CASE WHEN tags @> :group_tag_json THEN 0 ELSE 1 END,
                        created_at DESC 
                    LIMIT 5
                """)
                params["group_tag_json"] = json.dumps([group_tag])
            else:
                sql = text(f"""
                    SELECT title, original_content, tags 
                    FROM knowledge_items 
                    WHERE verified = true AND ({where_clause})
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)

            result = await db.execute(sql, params)
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
            await db.rollback()
            return ""
