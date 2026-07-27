"""Сессия БД для FastAPI dependencies."""
from app.db.base import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
