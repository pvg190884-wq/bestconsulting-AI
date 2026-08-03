"""Dubai Jobs Service — ежедневный пост про трудоустройство в Дубае в Telegram-группу."""
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import _get_engine
from app.services.llm_service import LLMService
from app.services.telegram_service import send_message
from app.utils.logger import setup_logging

logger = setup_logging()

DUBAI_GROUP_CHAT_ID = -1003921754469

# Ротация углов подачи — чтобы посты не повторялись день в день
TOPIC_ANGLES = [
    "Какие профессии и навыки сейчас востребованы на рынке труда Дубая в целом (без конкретных вакансий, по общим отраслевым трендам)",
    "Как правильно искать работу в Дубае: с чего начать, какие площадки и агентства использовать, как составить резюме под местный рынок",
    "Стоит ли переезжать в Дубай без готового оффера — риски, плюсы и минусы такого решения, что нужно предусмотреть заранее",
    "Сколько реально занимает поиск работы в Дубае для разных категорий специалистов и от чего это зависит",
    "Какие визовые и юридические особенности трудоустройства в ОАЭ нужно знать до переезда",
    "Что ждёт рынок труда Дубая в ближайшие годы: на какие отрасли делает ставку экономика ОАЭ",
    "Типичные ошибки соискателей при поиске работы в Дубае и как их избежать",
    "Разница между поиском работы через агентство и самостоятельным поиском в Дубае",
]

POST_INSTRUCTION = (
    "Ты — эксперт по трудоустройству и релокации в Дубай (ОАЭ), ведёшь Telegram-канал Bestconsulting. "
    "Текущий год — 2026. Пиши практический, полезный пост на указанную тему. "
    "СТРОГО ВАЖНО: НЕ упоминай конкретные названия вакансий, зарплаты, компании или цифры, которые ты не можешь "
    "подтвердить — у тебя нет доступа к актуальным данным рынка труда в реальном времени. Говори об общих, "
    "проверенных временем принципах и трендах, а не о «вакансиях, открытых сейчас». Если делаешь прогноз — "
    "явно обозначай его как мнение/тенденцию, а не факт. "
    "Формат: пост для Telegram, 200-400 слов, живой стиль, без markdown-разметки (это обычный чат, не поддерживает "
    "жирный шрифт через **), можно использовать эмодзи по смыслу, разбивка на короткие абзацы. "
    "В конце — короткий вопрос к аудитории для вовлечения (комментарии). "
    "Ответь ТОЛЬКО текстом поста, без вступлений от себя, без кавычек вокруг всего текста."
)


def _session_maker():
    engine = _get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_setting(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(text("SELECT value FROM app_settings WHERE key = :k"), {"k": key})
    row = result.first()
    return row[0] if row else None


async def set_setting(db: AsyncSession, key: str, value: str):
    await db.execute(text("""
        INSERT INTO app_settings (key, value, updated_at) VALUES (:k, :v, NOW())
        ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = NOW()
    """), {"k": key, "v": value})
    await db.commit()


async def _get_next_angle_index(db: AsyncSession) -> int:
    raw = await get_setting(db, "dubai_jobs_last_index")
    idx = int(raw) if raw is not None else -1
    next_idx = (idx + 1) % len(TOPIC_ANGLES)
    return next_idx


async def generate_post(llm: LLMService, angle: str) -> str:
    result = await llm.generate("openai", [
        {"role": "system", "content": POST_INSTRUCTION},
        {"role": "user", "content": f"Тема сегодняшнего поста: {angle}"},
    ], temperature=0.7)
    return result["content"].strip()


async def run_daily_post():
    """Вызывается планировщиком раз в день — генерирует и публикует один пост в группу."""
    Session = _session_maker()
    async with Session() as db:
        try:
            enabled = await get_setting(db, "dubai_jobs_enabled")
            if enabled != "true":
                return

            idx = await _get_next_angle_index(db)
            angle = TOPIC_ANGLES[idx]

            llm = LLMService()
            post_text = await generate_post(llm, angle)

            ok = await send_message(DUBAI_GROUP_CHAT_ID, post_text)
            if ok:
                await set_setting(db, "dubai_jobs_last_index", str(idx))
                await set_setting(db, "dubai_jobs_last_posted", datetime.now().isoformat())
                logger.info(f"[DubaiJobs] Пост опубликован (угол #{idx}): {angle[:60]}...")
            else:
                logger.error("[DubaiJobs] Не удалось отправить пост в группу")
        except Exception as e:
            logger.error(f"[DubaiJobs] Ошибка ежедневного поста: {e}")


_scheduler_job_added = False


def _ensure_scheduled(scheduler):
    global _scheduler_job_added
    if _scheduler_job_added:
        return
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(run_daily_post, CronTrigger(hour=9, minute=0), id="dubai_jobs_daily")
    _scheduler_job_added = True
    logger.info("[DubaiJobs] Ежедневный пост запланирован на 09:00 (время сервера)")


async def start_daily_posts(db: AsyncSession) -> str:
    await set_setting(db, "dubai_jobs_enabled", "true")
    from app.services import dzen_service
    dzen_service._ensure_scheduler_started()
    _ensure_scheduled(dzen_service._scheduler)
    return "✅ Ежедневные посты про Дубай включены. Публикация в 09:00 (время сервера) в группу."


async def stop_daily_posts(db: AsyncSession) -> str:
    await set_setting(db, "dubai_jobs_enabled", "false")
    return "⏸ Ежедневные посты про Дубай приостановлены. Возобновить — /дубай_старт."


async def status_daily_posts(db: AsyncSession) -> str:
    enabled = await get_setting(db, "dubai_jobs_enabled")
    last_posted = await get_setting(db, "dubai_jobs_last_posted")
    idx_raw = await get_setting(db, "dubai_jobs_last_index")
    idx = int(idx_raw) if idx_raw is not None else -1
    return (
        f"📊 Статус постов про Дубай:\n"
        f"• Активны: {'да' if enabled == 'true' else 'нет'}\n"
        f"• Последняя публикация: {last_posted or 'ещё не было'}\n"
        f"• Последний угол подачи: #{idx + 1}/{len(TOPIC_ANGLES)}\n"
        f"• Группа: {DUBAI_GROUP_CHAT_ID}"
    )


async def test_post_now(db: AsyncSession) -> str:
    """Публикует пост немедленно, вне расписания — для проверки."""
    idx = await _get_next_angle_index(db)
    angle = TOPIC_ANGLES[idx]
    llm = LLMService()
    post_text = await generate_post(llm, angle)
    ok = await send_message(DUBAI_GROUP_CHAT_ID, post_text)
    if ok:
        await set_setting(db, "dubai_jobs_last_index", str(idx))
        await set_setting(db, "dubai_jobs_last_posted", datetime.now().isoformat())
        return f"✅ Тестовый пост опубликован в группу (угол: {angle[:60]}...)"
    return "❌ Не удалось опубликовать тестовый пост."
