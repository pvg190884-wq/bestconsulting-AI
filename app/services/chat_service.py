"""Chat Service — обработка сообщений с идентификацией группы, руководителя и RAG."""
import time
import traceback
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.llm_service import LLMService
from app.services.founder_service import FounderService
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
    "FOUNDER": "ОСНОВАТЕЛЬ Павлов Вадим Геннадьевич. Стиль: уважительный, оперативный, инициативный. Исполнять все поручения. Докладывать о результатах. ",
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
                "response": f"Ошибка сервера. Попробуйте ещё раз.",
                "model_used": "error",
                "processing_time": 0,
                "session_id": f"{client_id}_{channel}",
                "group": None,
                "error_detail": err[:500],
            }

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

        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            raise

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

            if cmd == "/задача":
                if not arg:
                    return {"response": "Укажите текст поручения после команды. Пример: /задача собрать 100 подписчиков", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                res = await self.founder.create_task(db, arg[:200], arg)
                if res["success"]:
                    return {"response": f"✅ Поручение создано: {res['title']}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                return {"response": f"❌ Ошибка: {res.get('error')}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/отчет":
                stats = await self.founder.get_stats(db)
                text = (
                    f"📊 Отчёт ({stats.get('timestamp', 'сейчас')}):\n"
                    f"• Всего контактов: {stats.get('total_clients', 0)}\n"
                    f"• По группам: {stats.get('by_group', {})}\n"
                    f"• По каналам: {stats.get('by_channel', {})}\n"
                    f"• Эскалаций за неделю: {stats.get('escalations_week', 0)}\n"
                    f"• Записей в базе знаний: {stats.get('knowledge_items', 0)}"
                )
                return {"response": text, "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

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
                    return {"response": "Укажите тему. Пример: /доклад анализ эскалаций за месяц", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                prompt = f"Сформируй аналитический доклад на тему: {arg}. Структура: 1. Введение 2. Данные 3. Выводы 4. Рекомендации. Кратко, по делу."
                try:
                    result = await self.llm.generate("openai", [{"role": "user", "content": prompt}], temperature=0.3)
                    return {
                        "response": f"📄 Доклад «{arg}»:\n\n{result['content'][:1500]}\n\n(Сохраните текст — он не сохранён автоматически. Для автосохранения используйте /база [текст])",
                        "model_used": result.get("model", "openai"),
                        "session_id": session_id,
                        "group": "FOUNDER"
                    }
                except Exception as e:
                    return {"response": f"❌ Ошибка генерации доклада: {e}", "model_used": "error", "session_id": session_id, "group": "FOUNDER"}

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
                            ed = json.loads(extra)
                            name = ed.get("name", "—")
                        except:
                            name = "—"
                        lines.append(f"• {name} | {row['client_id']} | {row['channel']} | Группа: {row['client_group'] or '—'}")
                    return {"response": "\n".join(lines), "model_used": "system", "session_id": session_id, "group": "FOUNDER"}
                except Exception as e:
                    return {"response": f"❌ Ошибка: {e}", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            if cmd == "/очистить":
                await self.dialog.clear_pending_escalation(db, client_id)
                return {"response": "✅ Ожидания сброшены. Готов к новым задачам.", "model_used": "system", "session_id": session_id, "group": "FOUNDER"}

            await self.dialog.save_message(db, session_id, client_id, channel, "user", message)
            
            if len(message) > 30 and any(w in message.lower() for w in ["нужно", "сделай", "собери", "подготовь", "напиши", "создай"]):
                await self.founder.create_task(db, message[:100], message)
                prefix = "✅ Зафиксировал как поручение. "
            else:
                prefix = ""

            knowledge_text = await self._fetch_knowledge(db, message, "FOUNDER")
            system_msg = self.system_prompt + "\n\n" + GROUP_CONTEXT["FOUNDER"]
            
            messages = [{"role": "system", "content": system_msg}]
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
                    except:
                        pass
                    
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
            group_tag = f"группа_{group.lower()}" if group else ""
            
            if group_tag:
                sql = text("""
                    SELECT title, original_content, tags 
                    FROM knowledge_items 
                    WHERE verified = true 
                      AND (title ILIKE :q OR original_content ILIKE :q)
                    ORDER BY 
                        CASE WHEN tags @> :group_tag_json THEN 0 ELSE 1 END,
                        created_at DESC 
                    LIMIT 3
                """)
                result = await db.execute(sql, {"q": f"%{query}%", "group_tag_json": json.dumps([group_tag])})
            else:
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
