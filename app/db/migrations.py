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
        
        if not has_code_data:
            logger.warning("[Migration] Обнаружена старая схема knowledge_items — пересоздание")
            await conn.execute(text("DROP TABLE knowledge_items CASCADE;"))
            await conn.run_sync(Base.metadata.create_all, tables=[KnowledgeItem.__table__])
            logger.info("[Migration] Таблица knowledge_items пересоздана с новой схемой")
            return
        
        # Проверяем тип колонки 'type' (enum -> varchar)
        result3 = await conn.execute(text("""
            SELECT udt_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
              AND table_name = 'knowledge_items'
              AND column_name = 'type';
        """))
        type_udt = result3.scalar()
        
        if type_udt and type_udt != 'varchar':
            logger.warning(f"[Migration] Колонка type имеет тип '{type_udt}' (enum) — конвертация в varchar")
            await conn.execute(text(
                "ALTER TABLE knowledge_items ALTER COLUMN type TYPE varchar USING type::text;"
            ))
            logger.info("[Migration] Колонка type успешно переведена в varchar")
        
        # Проверяем, разрешён ли NULL в колонке code_data
        result4 = await conn.execute(text("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
              AND table_name = 'knowledge_items'
              AND column_name = 'code_data';
        """))
        code_data_nullable = result4.scalar()
        
        if code_data_nullable == 'NO':
            logger.warning("[Migration] Колонка code_data имеет NOT NULL — разрешаем NULL")
            await conn.execute(text(
                "ALTER TABLE knowledge_items ALTER COLUMN code_data DROP NOT NULL;"
            ))
            logger.info("[Migration] Колонка code_data теперь допускает NULL")
        
        logger.info("[Migration] Таблица knowledge_items проверена и актуальна")
