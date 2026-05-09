"""Эндпоинты /api/admin/scheduler/*."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.errors import NotFound

router = APIRouter()
logger = logging.getLogger("app.admin.scheduler")


def _get_scheduler():
    """Возвращает экземпляр планировщика или None."""
    try:
        from app.scheduler import _scheduler_instance
        return _scheduler_instance
    except Exception:
        return None


def _job_to_dict(job) -> dict:
    return {
        "id": job.id,
        "name": job.name,
        "next_run_time": (
            job.next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            if job.next_run_time
            else None
        ),
        "trigger": str(job.trigger),
        "paused": job.next_run_time is None,
    }


@router.get("/scheduler/jobs")
async def list_jobs() -> dict:
    """Возвращает список задач планировщика."""
    scheduler = _get_scheduler()
    if scheduler is None:
        return {"items": []}
    return {"items": [_job_to_dict(j) for j in scheduler.get_jobs()]}


@router.post("/scheduler/jobs/{job_id}/run", status_code=204)
async def run_job(job_id: str) -> None:
    """Немедленно запускает задачу планировщика.

    Args:
        job_id: Идентификатор задачи APScheduler.
    """
    scheduler = _get_scheduler()
    if scheduler is None:
        raise NotFound("Планировщик не запущен")

    job = scheduler.get_job(job_id)
    if job is None:
        raise NotFound("Задача не найдена", code="JOB_NOT_FOUND")

    scheduler.modify_job(job_id, next_run_time=datetime.now(timezone.utc))
    logger.info("Задача '%s' запущена вручную администратором", job_id)


@router.post("/scheduler/jobs/{job_id}/pause", status_code=204)
async def pause_job(job_id: str) -> None:
    """Приостанавливает задачу планировщика.

    Args:
        job_id: Идентификатор задачи.
    """
    scheduler = _get_scheduler()
    if scheduler is None:
        raise NotFound("Планировщик не запущен")
    job = scheduler.get_job(job_id)
    if job is None:
        raise NotFound("Задача не найдена", code="JOB_NOT_FOUND")
    scheduler.pause_job(job_id)
    logger.info("Задача '%s' приостановлена", job_id)


@router.post("/scheduler/jobs/{job_id}/resume", status_code=204)
async def resume_job(job_id: str) -> None:
    """Возобновляет приостановленную задачу планировщика.

    Args:
        job_id: Идентификатор задачи.
    """
    scheduler = _get_scheduler()
    if scheduler is None:
        raise NotFound("Планировщик не запущен")
    job = scheduler.get_job(job_id)
    if job is None:
        raise NotFound("Задача не найдена", code="JOB_NOT_FOUND")
    scheduler.resume_job(job_id)
    logger.info("Задача '%s' возобновлена", job_id)
