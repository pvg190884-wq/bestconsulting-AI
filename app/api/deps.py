"""Зависимости API."""
from app.config import settings
from app.db.session import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession


def get_settings():
    return settings


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
