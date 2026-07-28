"""Автомиграции базы данных при старте."""
from sqlalchemy import text
from app.db.base import _get_engine, Base
from app.db.models.knowledge import KnowledgeItem
from app.utils.logger import setup_logging

logger = setup_logging()


async def run_migrations():
    """Проверяет и исправляет схему БД без ручного вмешательства."""
    engine = _get_engine()
    
    async with engine.begin() as conn:
        # Проверяем, существует ли таблица knowledge_items
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'knowledge_items'
            );
        """))
        table_exists = result.scalar()
        
        if not table_exists:
            # Таблицы нет — создадим при обычном init_db
            logger.info("[Migration] Таблица knowledge_items не найдена, будет создана автоматически")
            return
        
        # Таблица есть — проверяем наличие новой колонки code_data
        result2 = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public'
                AND table_name = 'knowledge_items' 
                AND column_name = 'code_data'
            );
        """))
        has_code_data = result2.scalar()
        
        if has_code_data:
            logger.info("[Migration] Таблица knowledge_items актуальна")
            return
        
        # Старая схема — пересоздаём таблицу
        logger.warning("[Migration] Обнаружена старая схема knowledge_items — пересоздание")
        await conn.execute(text("DROP TABLE knowledge_items CASCADE;"))
        await conn.run_sync(Base.metadata.create_all, tables=[KnowledgeItem.__table__])
        logger.info("[Migration] Таблица knowledge_items пересоздана с новой схемой")
