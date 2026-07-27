"""База данных: engine, session, Base.
Поддерживает PostgreSQL (asyncpg) и SQLite (aiosqlite).
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

Base = declarative_base()

# Создаём async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE if "postgresql" in settings.DATABASE_URL else None,
    max_overflow=settings.DB_MAX_OVERFLOW if "postgresql" in settings.DATABASE_URL else None,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db():
    """Создаёт таблицы при старте (для dev/SQLite).
    Для production используй Alembic миграции."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
