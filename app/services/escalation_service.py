"""Escalation Service — детекция и создание эскалаций."""
import re
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.escalation import Escalation, EscalationPriority
from app.utils.security import generate_id
from app.utils.logger import setup_logging

logger = setup_logging()

# Триггеры эскалации
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

# Группа А + технический = эскалация
GROUP_A_TECH_KEYWORDS = ["сложный технический", "инженер", "проект", "чертеж", "смета", "пнр", "смр"]


def detect_escalation(message: str, group: str) -> tuple[bool, str, EscalationPriority]:
    """
    Анализирует сообщение на признаки эскалации.
    
    Returns: (needs_escalation, reason, priority)
    """
    t = message.lower()
    
    # 1. Высокий приоритет: деньги, договоры, живой человек
    for pattern in ESCALATION_TRIGGERS["HIGH"]["patterns"]:
        if re.search(pattern, t):
            reason = f"Обнаружен триггер высокого приоритета: {pattern.replace(chr(92), '')}"
            return True, reason, EscalationPriority.HIGH
    
    # 2. Средний приоритет: конфликты, жалобы
    for pattern in ESCALATION_TRIGGERS["MEDIUM"]["patterns"]:
        if re.search(pattern, t):
            reason = f"Обнаружен триггер среднего приоритета: {pattern.replace(chr(92), '')}"
            return True, reason, EscalationPriority.MEDIUM
    
    # 3. Группа А + технический вопрос
    if group == "A":
        for kw in GROUP_A_TECH_KEYWORDS:
            if kw in t:
                reason = "Сложный технический вопрос Группы А"
                return True, reason, EscalationPriority.HIGH
    
    # 4. Запрос вне компетенции (длинный + непонятный)
    if len(message) > 500 and not any(k in t for k in ["спасибо", "пока", "до свидания"]):
        # Эвристика: если сообщение длинное и не содержит ключевых слов ни одной группы
        has_group_keywords = any(k in t for k in ESCALATION_TRIGGERS["HIGH"]["keywords"] + ESCALATION_TRIGGERS["MEDIUM"]["keywords"])
        if not has_group_keywords:
            reason = "Запрос вне компетенции (не распознан)"
            return True, reason, EscalationPriority.LOW
    
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
    
    logger.warning(f"[ESCALATE] Создана эскалация {esc.id}: {trigger_reason} | Приоритет: {priority.value}")
    
    return esc


def format_escalation_message(esc: Escalation, group: str) -> str:
    """Форматирует сообщение эскалации по шаблону из промпта."""
    return (
        f"[Руководитель], требуется ваше решение по вопросу: {esc.trigger_reason}.\n"
        f"Контекст: {esc.context_summary or 'Клиент запросил эскалацию через чат-бот'}.\n"
        f"Рекомендация: {esc.recommendation or 'Требуется вмешательство человека'}.\n"
        f"Срочность: {esc.priority.value}. Группа: {group}."
    )
