"""Dialog Manager — управление диалогами и памятью."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models.chat import ChatSession, ChatMessage
from app.db.models.client import Client
from app.utils.security import generate_id
from app.utils.logger import setup_logging

logger = setup_logging()


class DialogManager:
    """Управление диалогами."""

    async def _get_or_create_client(self, db: AsyncSession, client_id: str, channel: str) -> Client:
        """Получает клиента или создаёт нового."""
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        
        if not client:
            client = Client(
                id=generate_id(),
                external_id=client_id,
                channel=channel,
            )
            db.add(client)
            await db.commit()
            logger.info(f"[Dialog] Создан новый клиент {client_id}")
        
        return client

    async def get_history(self, db: AsyncSession, session_id: str, limit: int = 20) -> list[dict]:
        """Получает историю сообщений сессии."""
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()
        return [{"role": m.role.value, "content": m.content} for m in reversed(messages)]

    async def save_message(self, db: AsyncSession, session_id: str, client_id: str,
                           channel: str, role: str, content: str,
                           model_used: str = None, tokens_used: int = None):
        """Сохраняет сообщение в БД. Автоматически создаёт клиента и сессию, если нужно."""
        # 1. Получаем или создаём клиента
        client = await self._get_or_create_client(db, client_id, channel)
        
        # 2. Проверяем, есть ли сессия
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        
        if not session:
            session = ChatSession(
                id=session_id,
                client_id=client.id,  # Используем внутренний UUID, а не external_id
                channel=channel,
            )
            db.add(session)
            await db.commit()
        
        # 3. Сохраняем сообщение
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
