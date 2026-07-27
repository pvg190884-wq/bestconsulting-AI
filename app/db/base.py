"""База данных: engine, session, Base.
Поддерживает PostgreSQL (asyncpg) и SQLite (aiosqlite).
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

Base = declarative_base()

_engine = None
_AsyncSessionLocal = None


def _get_async_url():
    """Railway даёт postgresql://, но async engine требует postgresql+asyncpg://."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _get_engine():
    global _engine
    if _engine is None:
        kwargs = {
            "echo": settings.DB_ECHO,
            "future": True,
        }
        if "postgresql" in settings.DATABASE_URL:
            kwargs["pool_size"] = settings.DB_POOL_SIZE
            kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        _engine = create_async_engine(_get_async_url(), **kwargs)
    return _engine


def get_session_maker():
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _AsyncSessionLocal


AsyncSessionLocal = get_session_maker()


async def init_db():
    """Создаёт таблицы при старте (для dev/SQLite).
    Для production используй Alembic миграции."""
    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
