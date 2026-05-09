"""Сервис heartbeat: периодически сообщает backend'у, что бот живой."""

import asyncio
import logging

from bot.services.backend_client import BackendClient

logger = logging.getLogger("bot.heartbeat")


async def heartbeat_loop(
    client: BackendClient,
    interval_seconds: int = 30,
    version: str = "1.0.0",
) -> None:
    """Бесконечный цикл отправки heartbeat backend'у.

    Каждые ``interval_seconds`` секунд шлёт
    ``POST /api/internal/bot/heartbeat`` с ``{polling_ok: True, version}``.
    Любая ошибка клиента (сеть/HTTP) логируется как WARNING и не
    останавливает цикл — следующая попытка после очередного sleep.

    Корректно завершается по ``asyncio.CancelledError``.

    Args:
        client: Сконфигурированный BackendClient.
        interval_seconds: Период между heartbeat в секундах.
        version: Версия бота, прокидывается в payload.
    """
    logger.info(
        "Heartbeat loop запущен (interval=%ds, version=%s)",
        interval_seconds,
        version,
    )
    try:
        while True:
            try:
                await client.post_heartbeat(polling_ok=True, version=version)
                logger.debug("Heartbeat отправлен")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Не падаем: backend может быть временно недоступен.
                logger.warning("Heartbeat не доставлен: %s", exc)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Heartbeat loop остановлен")
        raise
