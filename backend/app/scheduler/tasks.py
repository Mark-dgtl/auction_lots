"""Задачи планировщика APScheduler.

Каждая задача создаёт собственную сессию БД и вызывает соответствующий сервис.
Ошибки логируются на уровне ERROR и не прерывают работу планировщика.
"""

import logging

from app.core.config import settings
from app.db.session import async_session_maker

logger = logging.getLogger("app.scheduler")


async def parser_tick() -> None:
    """Запускает все источники парсера по расписанию.

    Перебирает PARSER_SOURCES, инициализирует каждый источник
    и передаёт в IngestService.run_source(). Ошибки отдельных источников
    не прерывают обработку остальных.
    """
    from app.services.ingest_service import IngestService

    source_names = [s.strip() for s in settings.PARSER_SOURCES.split(",") if s.strip()]

    for source_name in source_names:
        try:
            source = _get_source(source_name)
            if source is None:
                logger.warning("Неизвестный источник парсера: %s", source_name)
                continue

            async with async_session_maker() as session:
                svc = IngestService(session)
                report = await svc.run_source(source)
                logger.info(
                    "Парсер %s: новых=%d, обновлено=%d, пропущено=%d",
                    source_name,
                    report.lots_new,
                    report.lots_updated,
                    report.lots_skipped,
                )
        except Exception as exc:
            logger.error("Ошибка запуска источника %s: %s", source_name, exc)


async def digest_tick() -> None:
    """Проверяет дайджесты и создаёт outbox-записи для пользователей.

    Вызывается каждые DIGEST_CHECK_INTERVAL_MINUTES минут.
    """
    from app.services.digest_service import DigestService

    try:
        async with async_session_maker() as session:
            svc = DigestService(session)
            count = await svc.tick()
            if count > 0:
                logger.info("Дайджест: создано %d новых сообщений", count)
    except Exception as exc:
        logger.error("Ошибка при выполнении digest_tick: %s", exc)


def _get_source(name: str):
    """Возвращает экземпляр источника парсера по имени.

    Args:
        name: Идентификатор источника ('efrsb' или 'torgi_gov').

    Returns:
        Экземпляр BaseSource или None, если имя неизвестно.
    """
    try:
        if name == "efrsb":
            from parser.sources.efrsb import EfrsbSource
            return EfrsbSource()
        elif name == "torgi_gov":
            from parser.sources.torgi import TorgiSource
            return TorgiSource()
    except ImportError as exc:
        logger.warning("Не удалось импортировать источник %s: %s", name, exc)
    return None
