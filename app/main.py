"""BestConsulting AI Core v2.2 — GPT Orchestrator
Единый ИИ-сотрудник. GPT — основной мозг.
"""
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.utils.logger import setup_logging
from app.core.exceptions import BestConsultingException
from app.api.v1.router import api_router
from app.db.base import init_db
from app.db.migrations import run_migrations

logger = setup_logging()


async def _start_background_schedulers():
    """Регистрирует cron-задачи (Дзен, Дубай) при каждом старте приложения —
    иначе расписание теряется при каждом передеплое."""
    try:
        from app.services import dzen_service, dubai_jobs_service
        dzen_service._ensure_scheduler_started()
        dubai_jobs_service._ensure_scheduled(dzen_service._scheduler)
        logger.info("✅ Фоновые планировщики (Дзен, Дубай) зарегистрированы")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации планировщиков: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 CANARY-0001 v2.2 запущен")
    logger.info(f"Окружение: {settings.APP_ENV}")
    logger.info(f"Оркестратор: {settings.OPENAI_MODEL} (OpenRouter)")
    try:
        await init_db()
        await run_migrations()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

    # Telegram webhook
    if settings.TELEGRAM_BOT_TOKEN:
        from app.services.telegram_service import set_webhook
        railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN")
        if railway_url:
            tg_webhook = f"https://{railway_url}/api/v1/telegram/webhook"
            await set_webhook(tg_webhook)
            logger.info(f"✅ Telegram webhook: {tg_webhook}")

    # MAX — настраивается вручную через @MasterBot
    railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_url and settings.MAX_API_TOKEN:
        logger.info(f"📋 Настрой MAX webhook через @MasterBot:")
        logger.info(f"   URL: https://{railway_url}/api/v1/max/webhook")

    # Фоновые планировщики — регистрируются при каждом старте, переживают передеплой
    await _start_background_schedulers()

    yield
    logger.info("🛑 BestConsulting AI Core остановлен")


app = FastAPI(
    title="BestConsulting AI Core",
    description="Единый ИИ-сотрудник с GPT-оркестрацией, памятью и самообучением.",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.exception_handler(BestConsultingException)
async def bestconsulting_exception_handler(request: Request, exc: BestConsultingException):
    logger.error(f"BestConsultingException: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Необработанное исключение: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера. Мы уже работаем над исправлением.", "code": "INTERNAL_ERROR"},
    )


app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["root"])
async def root():
    return {
        "name": "BestConsulting AI Core",
        "version": "2.2.0",
        "status": "running",
        "agent": settings.AGENT_NAME,
        "orchestrator": "GPT",
    }
