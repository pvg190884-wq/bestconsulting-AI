"""Dialog Manager — управление диалогами и памятью."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm.attributes import flag_modified
from app.db.models.chat import ChatSession, ChatMessage
from app.db.models.client import Client
from app.utils.security import generate_id
from app.utils.logger import setup_logging

logger = setup_logging()


class DialogManager:
    async def _get_or_create_client(self, db: AsyncSession, client_id: str, channel: str) -> Client:
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if not client:
            client = Client(id=generate_id(), external_id=client_id, channel=channel)
            db.add(client)
            await db.commit()
            logger.info(f"[Dialog] Создан новый клиент {client_id}")
        return client

    async def get_client_group(self, db: AsyncSession, client_id: str) -> str | None:
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client and client.extra_data:
            return client.extra_data.get("group")
        return None

    async def set_client_group(self, db: AsyncSession, client_id: str, group: str):
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client:
            if not client.extra_data:
                client.extra_data = {}
            client.extra_data["group"] = group
            flag_modified(client, "extra_data")
            await db.commit()
            logger.info(f"[Dialog] Группа {group} сохранена для {client_id}")

    async def get_client_contacts(self, db: AsyncSession, client_id: str) -> dict:
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client and client.extra_data:
            return client.extra_data.get("contacts", {})
        return {}

    async def set_client_contacts(self, db: AsyncSession, client_id: str, contacts: dict):
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client:
            if not client.extra_data:
                client.extra_data = {}
            client.extra_data["contacts"] = contacts
            flag_modified(client, "extra_data")
            await db.commit()
            logger.info(f"[Dialog] Контакты сохранены для {client_id}")

    async def get_pending_escalation(self, db: AsyncSession, client_id: str) -> dict | None:
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client and client.extra_data:
            return client.extra_data.get("pending_escalation")
        return None

    async def set_pending_escalation(self, db: AsyncSession, client_id: str, data: dict):
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client:
            if not client.extra_data:
                client.extra_data = {}
            client.extra_data["pending_escalation"] = data
            flag_modified(client, "extra_data")
            await db.commit()

    async def clear_pending_escalation(self, db: AsyncSession, client_id: str):
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client and client.extra_data:
            client.extra_data.pop("pending_escalation", None)
            flag_modified(client, "extra_data")
            await db.commit()

    async def get_pending_document(self, db: AsyncSession, client_id: str) -> dict | None:
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client and client.extra_data:
            return client.extra_data.get("pending_document")
        return None

    async def set_pending_document(self, db: AsyncSession, client_id: str, data: dict):
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client:
            if not client.extra_data:
                client.extra_data = {}
            client.extra_data["pending_document"] = data
            flag_modified(client, "extra_data")
            await db.commit()
            logger.info(f"[Dialog] Ожидающий документ сохранён для {client_id}")

    async def clear_pending_document(self, db: AsyncSession, client_id: str):
        result = await db.execute(select(Client).where(Client.external_id == client_id))
        client = result.scalar_one_or_none()
        if client and client.extra_data:
            client.extra_data.pop("pending_document", None)
            flag_modified(client, "extra_data")
            await db.commit()

    async def get_history(self, db: AsyncSession, session_id: str, limit: int = 20) -> list[dict]:
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
        client = await self._get_or_create_client(db, client_id, channel)
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            session = ChatSession(id=session_id, client_id=client.id, channel=channel)
            db.add(session)
            await db.commit()
        msg = ChatMessage(
            id=generate_id(), session_id=session_id, role=role, content=content,
            model_used=model_used, tokens_used=tokens_used,
        )
        db.add(msg)
        await db.commit()
        logger.info(f"[Dialog] Сохранено сообщение {role} в сессию {session_id}")
