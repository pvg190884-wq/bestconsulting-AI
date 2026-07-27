"""Dialog Manager — управление диалогами и памятью.

Уровни памяти:
1. Диалоговая — текущий разговор (chat_sessions + chat_messages)
2. Клиентская — история общения с клиентом
3. Проектная — контекст проекта (v2.3+)
4. Глобальная — база знаний компании (knowledge_items)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models.chat import ChatSession, ChatMessage
from app.utils.security import generate_id
from app.utils.logger import setup_logging

logger = setup_logging()


class DialogManager:
    """Управление диалогами."""

    async def get_history(self, db: AsyncSession, session_id: str, limit: int = 20) -> list[dict]:
        """Получает историю сообщений сессии."""
        from sqlalchemy import select
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()
        # Возвращаем в хронологическом порядке
        return [{"role": m.role.value, "content": m.content} for m in reversed(messages)]

    async def save_message(self, db: AsyncSession, session_id: str, client_id: str,
                           channel: str, role: str, content: str,
                           model_used: str = None, tokens_used: int = None):
        """Сохраняет сообщение в БД."""
        # Проверяем, есть ли сессия
        from sqlalchemy import select
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()

        if not session:
            session = ChatSession(
                id=session_id,
                client_id=client_id,
                channel=channel,
            )
            db.add(session)

        msg = ChatMessage(
            id=generate_id(),
            session_id=session_id,
            role=role,
            content=content,
            model_used=model_used,
            tokens_used=tokens_used,
        )
        db.add(msg)
        await db.commit()
        logger.info(f"[Dialog] Сохранено сообщение {role} в сессию {session_id}")
