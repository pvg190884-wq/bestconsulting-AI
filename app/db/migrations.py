"""Автомиграции базы данных при старте."""
from sqlalchemy import text
from app.db.base import _get_engine, Base
from app.db.models.knowledge import KnowledgeItem
from app.utils.logger import setup_logging

logger = setup_logging()

# Колонки, которые обязаны оставаться NOT NULL (без них запись бессмысленна)
REQUIRED_NOT_NULL = {"id", "title", "original_content", "created_at"}


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

        # ─────────────────────────────────────────────────────────
        # НОВОЕ: Проверяем тип колонки 'tags' (json -> jsonb)
        # Без jsonb оператор @> (contains) не работает — падает
        # UndefinedFunctionError при каждом поиске по базе знаний.
        # ─────────────────────────────────────────────────────────
        result_tags = await conn.execute(text("""
            SELECT udt_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
              AND table_name = 'knowledge_items'
              AND column_name = 'tags';
        """))
        tags_udt = result_tags.scalar()

        if tags_udt == 'json':
            logger.warning("[Migration] Колонка tags имеет тип 'json' — конвертация в jsonb (критично для поиска)")
            await conn.execute(text(
                "ALTER TABLE knowledge_items ALTER COLUMN tags TYPE jsonb USING tags::jsonb;"
            ))
            logger.info("[Migration] Колонка tags успешно переведена в jsonb")
        elif tags_udt is None:
            logger.warning("[Migration] Колонка tags не найдена — добавляем как jsonb")
            await conn.execute(text(
                "ALTER TABLE knowledge_items ADD COLUMN tags jsonb DEFAULT '[]'::jsonb;"
            ))
            logger.info("[Migration] Колонка tags добавлена как jsonb")

        # Проверяем наличие GIN-индекса для быстрого поиска по tags
        result_idx = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'knowledge_items'
                  AND indexname = 'idx_knowledge_items_tags'
            );
        """))
        has_index = result_idx.scalar()

        if not has_index:
            logger.info("[Migration] Создаём GIN-индекс для колонки tags")
            await conn.execute(text(
                "CREATE INDEX idx_knowledge_items_tags ON knowledge_items USING gin(tags);"
            ))
            logger.info("[Migration] GIN-индекс на tags создан")

        # Универсальная проверка: снимаем NOT NULL со всех колонок, кроме обязательных
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

    # ─────────────────────────────────────────────────────────
    # Post-migration валидация: реально проверяем что поиск работает,
    # а не просто что колонки правильного типа.
    # Если это упадёт — приложение НЕ должно стартовать молча.
    # ─────────────────────────────────────────────────────────
    await validate_knowledge_search(engine)


async def validate_knowledge_search(engine):
    """
    Прогоняет реальный поисковый запрос к knowledge_items,
    чтобы гарантировать, что оператор @> и вся схема работают.
    Если упадёт — приложение не должно стартовать,
    иначе бот будет тихо деградировать в fallback-ответы.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                SELECT id FROM knowledge_items
                WHERE tags @> '["__migration_healthcheck__"]'::jsonb
                LIMIT 1;
            """))
        logger.info("[Migration] ✅ Поиск по knowledge_items прошёл проверку (jsonb @>)")
    except Exception as e:
        logger.critical(f"[Migration] ❌ КРИТИЧЕСКАЯ ОШИБКА: поиск по базе знаний не работает: {e}")
        raise SystemExit(
            "Автомиграция обнаружила, что поиск по knowledge_items сломан. "
            "Приложение остановлено, чтобы избежать тихой деградации в fallback-ответы."
        )
