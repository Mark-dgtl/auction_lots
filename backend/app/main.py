"""Точка входа FastAPI-приложения «Агрегатор торгов»."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api import api_router
from app.core.config import settings
from app.core.errors import AppError
from app.core.log_buffer import ring_handler
from app.core.logging import configure_logging

configure_logging()

# Подключаем кольцевой обработчик к корневому логгеру
logging.getLogger().addHandler(ring_handler)

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle FastAPI-приложения.

    Запускает APScheduler (парсер + digest) при SCHEDULER_ENABLED=true.
    В тестах SCHEDULER_ENABLED=false — планировщик не стартует.
    """
    # Bootstrap администратора
    from app.core.admin_bootstrap import bootstrap_admin_if_needed
    from app.db.session import async_session_maker
    await bootstrap_admin_if_needed(async_session_maker)

    scheduler = None
    if settings.SCHEDULER_ENABLED:
        from app.scheduler import create_scheduler
        scheduler = create_scheduler()
        scheduler.start()
        logger.info(
            "Планировщик запущен (парсер каждые %d мин, дайджест каждые %d мин)",
            settings.PARSER_INTERVAL_MINUTES,
            settings.DIGEST_CHECK_INTERVAL_MINUTES,
        )
    else:
        logger.info("Планировщик отключён (SCHEDULER_ENABLED=false)")

    if settings.MEDIA_WARM_ON_STARTUP:
        from app.services.media_prefetch import schedule_warm_all_lots

        cache_dir = settings.resolved_media_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Каталог кэша изображений: %s", cache_dir)
        schedule_warm_all_lots(delay_seconds=settings.MEDIA_WARM_STARTUP_DELAY_SECONDS)

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("Планировщик остановлен")
    logger.info("Приложение остановлено")


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Формирует JSON-ответ с ошибкой в стандартном конверте §2.1."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


app = FastAPI(
    title="Агрегатор торгов",
    description="REST API для агрегации лотов торгов",
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS ---
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception handlers ---

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Обрабатывает бизнес-исключения AppError и его подклассы."""
    return _error_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """Обрабатывает ошибки целостности БД (дубликат email и т.п.)."""
    logger.warning("IntegrityError: %s", exc.orig)
    return _error_response(409, "CONFLICT", "Конфликт данных")


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Обрабатывает ошибки валидации Pydantic (тело запроса)."""
    return _error_response(422, "VALIDATION_ERROR", "Ошибка валидации входных данных")


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обрабатывает все непойманные исключения."""
    logger.exception("Необработанная ошибка на %s %s: %s", request.method, request.url.path, exc)
    return _error_response(500, "INTERNAL_ERROR", "Внутренняя ошибка сервера")


# --- Wrap FastAPI HTTPException in error envelope ---
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Оборачивает стандартные FastAPI HTTPException в единый конверт ошибок."""
    code_map: dict[int, str] = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }
    code = code_map.get(exc.status_code, "INTERNAL_ERROR")
    return _error_response(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Обрабатывает ошибки валидации query/body параметров FastAPI."""
    errors = exc.errors()
    message = "; ".join(
        f"{' → '.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in errors
    )
    return _error_response(422, "VALIDATION_ERROR", message)


app.include_router(api_router)
