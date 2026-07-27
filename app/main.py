"""BestConsulting AI Core v2.0 — Foundation
Единый ИИ-сотрудник компании Bestconsulting.
Оркестратор, маршрутизатор, память, самообучение.
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.logger import setup_logging
from app.core.exceptions import BestConsultingException
from app.api.v1.router import api_router

# Настройка логирования
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    logger.info("🚀 BestConsulting AI Core v2.0 запущен")
    logger.info(f"Окружение: {settings.APP_ENV}")
    logger.info(f"Модель оркестратора: {settings.KIMI_MODEL}")
    yield
    logger.info("🛑 BestConsulting AI Core остановлен")


app = FastAPI(
    title="BestConsulting AI Core",
    description="Единый ИИ-сотрудник с оркестрацией, памятью и самообучением.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Добавляет время обработки запроса."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.exception_handler(BestConsultingException)
async def bestconsulting_exception_handler(request: Request, exc: BestConsultingException):
    """Обработка кастомных исключений."""
    logger.error(f"BestConsultingException: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальная обработка непредвиденных ошибок."""
    logger.exception(f"Необработанное исключение: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера. Мы уже работаем над исправлением.", "code": "INTERNAL_ERROR"},
    )


# Подключение API роутеров
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["root"])
async def root():
    """Корневой endpoint."""
    return {
        "name": "BestConsulting AI Core",
        "version": "2.0.0",
        "status": "running",
        "agent": settings.AGENT_NAME,
    }
