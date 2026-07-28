"""Escalation Service — детекция и создание эскалаций."""
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
    """Создаёт запись об эскалации в БД."""
    
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
    
    return esc


def format_escalation_message(esc: Escalation, group: str) -> str:
    """Форматирует сообщение эскалации."""
    return (
        f"[Руководитель], требуется ваше решение: {esc.trigger_reason}.\n"
        f"Контекст: {esc.context_summary or 'Запрос через чат-бот'}.\n"
        f"Рекомендация: {esc.recommendation or 'Требуется вмешательство человека'}.\n"
        f"Срочность: {esc.priority.value}. Группа: {group}."
    )
