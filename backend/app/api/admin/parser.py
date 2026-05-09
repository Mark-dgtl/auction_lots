"""Эндпоинты /api/admin/parser/run и /api/admin/parser/runs."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import NotFound
from app.db.session import get_db
from app.models.parser_run import ParserRun
from app.models.user import User

router = APIRouter()
logger = logging.getLogger("app.admin.parser")

# Флаг занятости парсера
_parser_running: bool = False


from pydantic import BaseModel


class ParserRunBody(BaseModel):
    """Тело запроса на ручной запуск парсера."""
    source: str = "all"


@router.post("/parser/run")
async def run_parser(
    body: ParserRunBody,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Запускает парсер вручную.

    Args:
        body: Параметры запуска (source: 'torgi_gov' | 'all').
        admin: Текущий администратор.
    """
    global _parser_running
    if _parser_running:
        from app.core.errors import AppError
        raise AppError("Парсер уже выполняется", code="PARSER_BUSY")

    from app.core.config import settings
    from app.services.ingest_service import IngestService

    source_names = [s.strip() for s in settings.PARSER_SOURCES.split(",") if s.strip()]
    if body.source != "all":
        if body.source not in source_names:
            raise NotFound(f"Источник '{body.source}' не найден")
        source_names = [body.source]

    _parser_running = True
    results = []
    try:
        for source_name in source_names:
            source_obj = _get_source(source_name)
            if source_obj is None:
                logger.warning("Неизвестный источник парсера: %s", source_name)
                continue

            svc = IngestService(db)
            report = await svc.run_source(
                source_obj,
                triggered_by="admin",
                triggered_by_user_id=admin.id,
            )
            results.append({
                "source": report.source,
                "status": report.status,
                "lots_seen": report.lots_seen,
                "lots_new": report.lots_new,
                "lots_updated": report.lots_updated,
                "lots_skipped": report.lots_skipped,
                "pages_fetched": report.pages_fetched,
                "expected_total_elements": report.expected_total_elements,
                "yielded_total": report.yielded_total,
                "skipped_invalid": report.skipped_invalid,
                "full_scan_completed": report.full_scan_completed,
                "error": report.error,
                "started_at": None,
                "finished_at": None,
            })
            logger.info(
                "Ручной запуск парсера '%s' завершён: новых=%d, обновлено=%d",
                source_name,
                report.lots_new,
                report.lots_updated,
            )
    finally:
        _parser_running = False

    if len(results) == 1:
        return results[0]
    return {"results": results}


@router.get("/parser/runs")
async def list_parser_runs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Возвращает историю запусков парсера.

    Args:
        limit: Максимальное число записей.
    """
    runs = await db.scalars(
        select(ParserRun).order_by(ParserRun.started_at.desc()).limit(limit)
    )
    items = [
        {
            "id": r.id,
            "source": r.source,
            "status": r.status,
            "lots_seen": r.lots_seen,
            "lots_new": r.lots_new,
            "lots_updated": r.lots_updated,
            "pages_fetched": r.pages_fetched,
            "expected_total_elements": r.expected_total_elements,
            "yielded_total": r.yielded_total,
            "skipped_invalid": r.skipped_invalid,
            "full_scan_completed": r.full_scan_completed,
            "triggered_by": r.triggered_by,
            "triggered_by_user_id": r.triggered_by_user_id,
            "started_at": r.started_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.started_at else None,
            "finished_at": r.finished_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.finished_at else None,
            "error": r.error,
        }
        for r in runs.all()
    ]
    return {"items": items}


def _get_source(name: str):
    """Возвращает экземпляр источника парсера по имени."""
    try:
        if name == "torgi_gov":
            from parser.sources.torgi import TorgiSource
            return TorgiSource()
        elif name == "efrsb":
            from parser.sources.efrsb import EfrsbSource
            return EfrsbSource()
    except ImportError as exc:
        logger.warning("Не удалось импортировать источник %s: %s", name, exc)
    return None
