"""Планировщик задач APScheduler.

Создаёт AsyncIOScheduler с двумя задачами:
- parser_tick — запуск парсеров каждые PARSER_INTERVAL_MINUTES минут;
- digest_tick — проверка дайджестов каждые DIGEST_CHECK_INTERVAL_MINUTES минут.

Планировщик запускается в lifespan FastAPI и отключается через SCHEDULER_ENABLED=false.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.scheduler.tasks import digest_tick, parser_tick

# Глобальный экземпляр планировщика (None до старта)
_scheduler_instance: AsyncIOScheduler | None = None


def create_scheduler() -> AsyncIOScheduler:
    """Создаёт и настраивает планировщик задач.

    Returns:
        Настроенный AsyncIOScheduler (не запущен).
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        parser_tick,
        trigger="interval",
        minutes=settings.PARSER_INTERVAL_MINUTES,
        id="parser_tick",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        digest_tick,
        trigger="interval",
        minutes=settings.DIGEST_CHECK_INTERVAL_MINUTES,
        id="digest_tick",
        replace_existing=True,
        max_instances=1,
    )

    global _scheduler_instance
    _scheduler_instance = scheduler
    return scheduler
