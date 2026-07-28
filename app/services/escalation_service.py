"""Escalation Service — детекция, создание и уведомления."""
import re
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.escalation import Escalation, EscalationPriority
from app.utils.security import generate_id
from app.utils.logger import setup_logging

logger = setup_logging()

ESCALATION_TRIGGERS = {
    "HIGH": {
        "patterns": [
            r"сч[ёе]т",
            r"договор",
            r"заказ",
            r"оплат",
            r"деньг",
            r"цена.*договор",
            r"юрист",
            r"адвокат",
            r"суд",
            r"иск",
            r"живой человек",
            r"оператор",
            r"менеджер",
            r"руководитель",
        ],
        "keywords": ["счёт", "договор", "заказ", "оплата", "юрист", "суд", "живой человек", "оператор"],
    },
    "MEDIUM": {
        "patterns": [
            r"конфликт",
            r"жалоб",
            r"претензи",
            r"недовол",
            r"ошибк",
            r"сбой",
            r"не работает",
        ],
        "keywords": ["конфликт", "жалоба", "претензия", "недовольство"],
    },
}

GROUP_A_TECH_KEYWORDS = ["сложный технический", "инженер", "проект", "чертеж", "смета", "пнр", "смр"]


def detect_escalation(message: str, group: str) -> tuple[bool, str, EscalationPriority]:
    """Анализирует сообщение на признаки эскалации."""
    t = message.lower()
    
    for pattern in ESCALATION_TRIGGERS["HIGH"]["patterns"]:
        if re.search(pattern, t):
            reason = f"Триггер: {pattern.replace(chr(92), '')}"
            return True, reason, EscalationPriority.HIGH
    
    for pattern in ESCALATION_TRIGGERS["MEDIUM"]["patterns"]:
        if re.search(pattern, t):
            reason = f"Триггер: {pattern.replace(chr(92), '')}"
            return True, reason, EscalationPriority.MEDIUM
    
    if group == "A":
        for kw in GROUP_A_TECH_KEYWORDS:
            if kw in t:
                reason = "Сложный технический вопрос Группы А"
                return True, reason, EscalationPriority.HIGH
    
    return False, "", EscalationPriority.LOW


async def create_escalation(
    db: AsyncSession,
    session_id: str,
    client_id: str,
    channel: str,
    trigger_reason: str,
    trigger_message: str,
    context_summary: str = "",
    recommendation: str = "",
    priority: EscalationPriority = EscalationPriority.MEDIUM,
    group: str = "",
) -> Escalation:
    """Создаёт запись об эскалации в БД и отправляет уведомления."""
    
    esc = Escalation(
        id=generate_id(),
        session_id=session_id,
        client_id=client_id,
        channel=channel,
        trigger_reason=trigger_reason,
        trigger_message=trigger_message,
        context_summary=context_summary,
        recommendation=recommendation,
        priority=priority,
        extra_data=f"Группа: {group}",
    )
    
    db.add(esc)
    await db.commit()
    
    logger.warning(f"[ESCALATE] {esc.id}: {trigger_reason} | {priority.value}")
    
    # === УВЕДОМЛЕНИЯ ===
    await _send_notifications(esc, group, recommendation)
    
    return esc


async def _send_notifications(esc: Escalation, group: str, contacts: str):
    """Отправляет уведомления в Telegram и Email."""
    
    logger.info(f"[NOTIFY] Начинаю отправку уведомлений для эскалации {esc.id}")
    
    # Формируем текст уведомления
    tg_text = (
        f"🚨 <b>ЭСКАЛАЦИЯ</b>\n\n"
        f"Причина: {esc.trigger_reason}\n"
        f"Группа: {group}\n"
        f"Клиент: {esc.client_id}\n\n"
        f"📋 Потребность:\n{esc.context_summary[:300]}\n\n"
        f"📞 Контакты:\n{contacts[:200]}\n\n"
        f"ID: {esc.id}"
    )
    
    # 1. Telegram руководителю
    logger.info(f"[NOTIFY] Попытка отправки Telegram...")
    try:
        from app.services.telegram_service import send_message_to_admin
        await send_message_to_admin(tg_text)
        logger.info("[NOTIFY] Telegram отправлен успешно")
    except Exception as e:
        logger.error(f"[NOTIFY] Ошибка Telegram: {e}")
    
    # 2. Email
    logger.info(f"[NOTIFY] Попытка отправки Email...")
    try:
        from app.services.email_service import send_email_notification, format_escalation_email
        subject = f"[ЭСКАЛАЦИЯ] {esc.trigger_reason[:50]} | Группа {group}"
        body = format_escalation_email(
            esc_id=esc.id,
            client_id=esc.client_id,
            reason=esc.trigger_reason,
            context=esc.context_summary or "—",
            contacts=contacts or "—",
        )
        result = send_email_notification(subject, body)
        if result:
            logger.info("[NOTIFY] Email отправлен успешно")
        else:
            logger.warning("[NOTIFY] Email НЕ отправлен (функция вернула False)")
    except Exception as e:
        logger.error(f"[NOTIFY] Ошибка Email: {e}")


def format_escalation_message(esc: Escalation, group: str) -> str:
    """Форматирует сообщение эскалации."""
    return (
        f"[Руководитель], требуется ваше решение: {esc.trigger_reason}.\n"
        f"Контекст: {esc.context_summary or 'Запрос через чат-бот'}.\n"
        f"Рекомендация: {esc.recommendation or 'Требуется вмешательство человека'}.\n"
        f"Срочность: {esc.priority.value}. Группа: {group}."
    )
