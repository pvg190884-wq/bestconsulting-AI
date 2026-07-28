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
            r"сч[ёе]т", r"договор", r"заказ", r"оплат", r"деньг",
            r"юрист", r"адвокат", r"суд", r"иск",
            r"живой человек", r"оператор", r"менеджер", r"руководитель",
        ],
    },
    "MEDIUM": {
        "patterns": [r"конфликт", r"жалоб", r"претензи", r"недовол", r"сбой"],
    },
}

GROUP_A_TECH_KEYWORDS = ["сложный технический", "инженер", "проект", "чертеж", "смета"]


def detect_escalation(message: str, group: str) -> tuple[bool, str, EscalationPriority]:
    t = message.lower()
    for pattern in ESCALATION_TRIGGERS["HIGH"]["patterns"]:
        if re.search(pattern, t):
            return True, f"Триггер: {pattern.replace(chr(92), '')}", EscalationPriority.HIGH
    for pattern in ESCALATION_TRIGGERS["MEDIUM"]["patterns"]:
        if re.search(pattern, t):
            return True, f"Триггер: {pattern.replace(chr(92), '')}", EscalationPriority.MEDIUM
    if group == "A":
        for kw in GROUP_A_TECH_KEYWORDS:
            if kw in t:
                return True, "Сложный технический вопрос Группы А", EscalationPriority.HIGH
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
    
    logger.warning(f"[ESCALATE] Создана: {esc.id} | {trigger_reason} | {priority.value}")
    
    # Уведомления — в фоне, не блокируем ответ клиенту
    try:
        await _send_notifications(esc, group, recommendation)
    except Exception as e:
        logger.error(f"[ESCALATE] Ошибка уведомлений: {e}")
    
    return esc


async def _send_notifications(esc: Escalation, group: str, contacts: str):
    """Отправляет уведомления в Telegram и Email."""
    
    logger.info(f"[NOTIFY] Старт для {esc.id}")
    
    tg_text = (
        f"🚨 <b>ЭСКАЛАЦИЯ</b>\n\n"
        f"Причина: {esc.trigger_reason}\n"
        f"Группа: {group}\n"
        f"Клиент: {esc.client_id}\n\n"
        f"📋 Потребность:\n{esc.context_summary[:300]}\n\n"
        f"📞 Контакты:\n{contacts[:200]}\n\n"
        f"ID: {esc.id}"
    )
    
    # 1. Telegram
    logger.info("[NOTIFY] Telegram...")
    try:
        from app.services.telegram_service import send_message_to_admin
        await send_message_to_admin(tg_text)
        logger.info("[NOTIFY] Telegram OK")
    except Exception as e:
        logger.error(f"[NOTIFY] Telegram FAIL: {e}")
    
    # 2. Email
    logger.info("[NOTIFY] Email...")
    try:
        from app.services.email_service import send_email_notification, format_escalation_email
        subject = f"[ЭСКАЛАЦИЯ] {esc.trigger_reason[:50]} | {group}"
        body = format_escalation_email(
            esc_id=esc.id,
            client_id=esc.client_id,
            reason=esc.trigger_reason,
            context=esc.context_summary or "—",
            contacts=contacts or "—",
        )
        ok = await send_email_notification(subject, body)
        logger.info(f"[NOTIFY] Email {'OK' if ok else 'FAIL'}")
    except Exception as e:
        logger.error(f"[NOTIFY] Email FAIL: {e}")
