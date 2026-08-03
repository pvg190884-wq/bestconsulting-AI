"""Автомиграции базы данных при старте."""
from sqlalchemy import text
from app.db.base import _get_engine, Base
from app.db.models.knowledge import KnowledgeItem
from app.utils.logger import setup_logging
logger = setup_logging()

REQUIRED_NOT_NULL = {"id", "title", "original_content", "created_at"}


async def run_migrations():
    """Проверяет и исправляет схему БД без ручного вмешательства."""
    engine = _get_engine()

    async with engine.begin() as conn:
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
        else:
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
            else:
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

                result4 = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                      AND table_name = 'knowledge_items'
                      AND is_nullable = 'NO';
                """))
                not_null_columns = [row[0] for row in result4.fetchall()]

                for col in not_null_columns:
                    if col in REQUIRED_NOT_NULL:
                        continue
                    logger.warning(f"[Migration] Колонка '{col}' имеет NOT NULL — разрешаем NULL")
                    await conn.execute(text(
                        f'ALTER TABLE knowledge_items ALTER COLUMN "{col}" DROP NOT NULL;'
                    ))
                    logger.info(f"[Migration] Колонка '{col}' теперь допускает NULL")

                logger.info("[Migration] Таблица knowledge_items проверена и актуальна")

        # --- app_settings: простое key-value хранилище глобальных флагов ---
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR PRIMARY KEY,
                value VARCHAR NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """))
        logger.info("[Migration] Таблица app_settings проверена")

        # --- dzen_content_plan: план серии статей для Дзен ---
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dzen_content_plan (
                id SERIAL PRIMARY KEY,
                sequence INTEGER NOT NULL,
                stage INTEGER NOT NULL,
                stage_title VARCHAR NOT NULL,
                angle VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                article_title VARCHAR,
                generated_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))
        logger.info("[Migration] Таблица dzen_content_plan проверена")
