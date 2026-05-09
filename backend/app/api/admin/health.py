"""Эндпоинты /api/admin/health и /api/admin/stats."""

import logging
import time as _time
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.lot import Lot
from app.models.outbox import Outbox
from app.models.parser_run import ParserRun
from app.models.saved_filter import SavedFilter
from app.models.user import User
from app.models.favorite import Favorite
from app.models.bot_heartbeat import BotHeartbeat

router = APIRouter()
logger = logging.getLogger("app.admin.health")

_start_time = _time.time()


@router.get("/health")
async def get_health(db: AsyncSession = Depends(get_db)) -> dict:
    """Возвращает отчёт о состоянии системы."""
    # DB latency
    t0 = _time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
        db_latency_ms = round((_time.monotonic() - t0) * 1000, 1)
    except Exception:
        db_ok = False
        db_latency_ms = None

    # Scheduler
    scheduler_info = _get_scheduler_info()

    # Outbox pending/failed
    pending_count = await db.scalar(
        select(func.count()).select_from(Outbox).where(Outbox.status == "pending")
    ) or 0
    failed_count = await db.scalar(
        select(func.count()).select_from(Outbox).where(Outbox.status == "failed")
    ) or 0
    oldest_pending = await db.scalar(
        select(Outbox.created_at)
        .where(Outbox.status == "pending")
        .order_by(Outbox.created_at)
        .limit(1)
    )
    oldest_pending_age = None
    if oldest_pending:
        now = datetime.now(timezone.utc)
        if oldest_pending.tzinfo is None:
            oldest_pending = oldest_pending.replace(tzinfo=timezone.utc)
        oldest_pending_age = round((now - oldest_pending).total_seconds())

    # Bot heartbeat
    hb = await db.scalar(select(BotHeartbeat).where(BotHeartbeat.id == 1))
    bot_online = False
    last_hb_at = None
    if hb:
        last_hb_at = hb.last_seen_at
        if last_hb_at.tzinfo is None:
            last_hb_at = last_hb_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last_hb_at).total_seconds()
        bot_online = age < settings.ADMIN_BOT_OFFLINE_THRESHOLD_SECONDS

    # Parser last runs
    runs = await db.scalars(
        select(ParserRun).order_by(ParserRun.started_at.desc()).limit(5)
    )
    last_runs = [
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
            "started_at": r.started_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.started_at else None,
            "finished_at": r.finished_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.finished_at else None,
            "error": r.error,
        }
        for r in runs.all()
    ]

    # Process metrics
    proc = psutil.Process()
    rss_mb = round(proc.memory_info().rss / 1024 / 1024, 1)
    cpu_pct = proc.cpu_percent(interval=None)
    uptime_sec = round(_time.time() - _start_time)

    return {
        "db": {"ok": db_ok, "latency_ms": db_latency_ms},
        "scheduler": scheduler_info,
        "outbox": {
            "pending": pending_count,
            "failed": failed_count,
            "oldest_pending_age_seconds": oldest_pending_age,
        },
        "bot": {
            "online": bot_online,
            "last_heartbeat_at": (
                last_hb_at.strftime("%Y-%m-%dT%H:%M:%SZ") if last_hb_at else None
            ),
        },
        "parser": {"last_runs": last_runs},
        "process": {
            "version": settings.APP_VERSION,
            "uptime_seconds": uptime_sec,
            "rss_mb": rss_mb,
            "cpu_percent": cpu_pct,
        },
    }


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Возвращает агрегированную статистику системы."""
    users_total = await db.scalar(select(func.count()).select_from(User)) or 0
    users_with_tg = await db.scalar(
        select(func.count()).select_from(User).where(User.telegram_user_id.isnot(None))
    ) or 0
    users_admin = await db.scalar(
        select(func.count()).select_from(User).where(User.is_admin.is_(True))
    ) or 0
    users_blocked = await db.scalar(
        select(func.count()).select_from(User).where(User.is_blocked.is_(True))
    ) or 0

    lots_total = await db.scalar(select(func.count()).select_from(Lot)) or 0

    # lots_by_source
    from sqlalchemy import distinct
    sources_rows = await db.execute(
        select(Lot.source, func.count(Lot.id).label("cnt")).group_by(Lot.source)
    )
    lots_by_source = {row.source: row.cnt for row in sources_rows}

    # lots_added_24h
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    lots_24h = await db.scalar(
        select(func.count()).select_from(Lot).where(Lot.first_seen_at >= cutoff)
    ) or 0

    favorites_total = await db.scalar(select(func.count()).select_from(Favorite)) or 0
    filters_total = await db.scalar(select(func.count()).select_from(SavedFilter)) or 0
    filters_notify = await db.scalar(
        select(func.count()).select_from(SavedFilter).where(
            SavedFilter.notify_enabled.is_(True)
        )
    ) or 0

    pending_out = await db.scalar(
        select(func.count()).select_from(Outbox).where(Outbox.status == "pending")
    ) or 0
    sent_out = await db.scalar(
        select(func.count()).select_from(Outbox).where(Outbox.status == "sent")
    ) or 0
    failed_out = await db.scalar(
        select(func.count()).select_from(Outbox).where(Outbox.status == "failed")
    ) or 0

    # errors_24h — подсчёт парсер-запусков с ошибками
    errors_24h = await db.scalar(
        select(func.count()).select_from(ParserRun).where(
            ParserRun.status == "error",
            ParserRun.started_at >= cutoff,
        )
    ) or 0

    return {
        "users_total": users_total,
        "users_with_telegram": users_with_tg,
        "users_admin": users_admin,
        "users_blocked": users_blocked,
        "lots_total": lots_total,
        "lots_by_source": lots_by_source,
        "lots_added_24h": lots_24h,
        "favorites_total": favorites_total,
        "filters_total": filters_total,
        "filters_with_notify": filters_notify,
        "outbox": {"pending": pending_out, "sent": sent_out, "failed": failed_out},
        "errors_24h": errors_24h,
    }


def _get_scheduler_info() -> dict:
    """Возвращает информацию о планировщике APScheduler."""
    try:
        from app.scheduler import _scheduler_instance
        if _scheduler_instance is None:
            return {"running": False, "jobs": []}
        jobs = []
        for job in _scheduler_instance.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if job.next_run_time
                    else None
                ),
                "trigger": str(job.trigger),
                "paused": job.next_run_time is None,
            })
        return {"running": _scheduler_instance.running, "jobs": jobs}
    except Exception as exc:
        logger.debug("Не удалось получить информацию о планировщике: %s", exc)
        return {"running": False, "jobs": []}
