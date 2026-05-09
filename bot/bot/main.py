"""Точка входа Telegram-бота агрегатора торгов.

Запускает четыре фоновые задачи параллельно:
- aiogram polling;
- опрос outbox и доставка сообщений;
- heartbeat в backend (см. §2.7);
- пересылка логов в backend (см. §2.7, §2.9.2).

Если ``TELEGRAM_BOT_TOKEN`` не задан — бот логирует предупреждение и ждёт.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.handlers import router as handlers_router
from bot.services.backend_client import BackendClient
from bot.services.heartbeat import heartbeat_loop
from bot.services.log_forwarder import LogForwardHandler, log_forwarder_loop
from bot.services.outbox_poller import outbox_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot.main")

_BOT_VERSION = "1.0.0"
_LOG_QUEUE_MAXSIZE = 1000


def _install_log_forwarder(queue: asyncio.Queue[dict[str, Any]]) -> LogForwardHandler:
    """Подключает LogForwardHandler к root-логгеру (уровень INFO)."""
    handler = LogForwardHandler(queue=queue, min_level=logging.INFO)
    logging.getLogger().addHandler(handler)
    return handler


async def _run_services(
    bot: Bot,
    dp: Dispatcher,
    backend_client: BackendClient,
    log_queue: asyncio.Queue[dict[str, Any]],
) -> None:
    """Запускает все фоновые задачи и корректно гасит их при отмене."""
    tasks: list[asyncio.Task[Any]] = [
        asyncio.create_task(
            dp.start_polling(bot, allowed_updates=["message"]),
            name="polling",
        ),
        asyncio.create_task(outbox_loop(bot, backend_client), name="outbox"),
        asyncio.create_task(
            heartbeat_loop(backend_client, interval_seconds=30, version=_BOT_VERSION),
            name="heartbeat",
        ),
        asyncio.create_task(
            log_forwarder_loop(backend_client, log_queue),
            name="log_forwarder",
        ),
    ]

    try:
        # gather с return_exceptions=False — если что-то падает, ловим
        # исключение здесь и аккуратно отменяем все остальные задачи.
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Получен shutdown, отменяем фоновые задачи")
        raise
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        # Дожидаемся завершения всех задач, исключения проглатываем —
        # они уже были залогированы соответствующими сервисами.
        await asyncio.gather(*tasks, return_exceptions=True)


async def main() -> None:
    """Запускает бота и все фоновые сервисы.

    Если ``TELEGRAM_BOT_TOKEN`` не задан — логирует предупреждение
    и уходит в бесконечное ожидание (не падает, чтобы тесты работали).
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning(
            "TELEGRAM_BOT_TOKEN не задан. Бот не запущен. "
            "Установите переменную окружения и перезапустите."
        )
        while True:
            await asyncio.sleep(3600)
        return

    log_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_LOG_QUEUE_MAXSIZE)
    _install_log_forwarder(log_queue)

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(handlers_router)

    backend_client = BackendClient(
        base_url=settings.BACKEND_INTERNAL_URL,
        token=settings.INTERNAL_API_TOKEN,
    )

    logger.info(
        "Бот запущен (version=%s). Сервисы: polling, outbox, heartbeat, log_forwarder.",
        _BOT_VERSION,
    )

    try:
        await _run_services(bot, dp, backend_client, log_queue)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
