"""Сервис опроса очереди outbox и отправки сообщений пользователям."""

import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot.services.backend_client import BackendClient

logger = logging.getLogger("bot.outbox_poller")

_POLL_INTERVAL_SECONDS = 5


async def _send_one(bot: Bot, item: dict[str, Any]) -> None:
    """Отправляет одно сообщение из outbox через aiogram.

    Прокидывает ``parse_mode`` (если есть) — backend кладёт это поле для
    HTML/Markdown-разметки (см. §2.7, §3.1 outbox.parse_mode).
    """
    parse_mode = item.get("parse_mode")
    kwargs: dict[str, Any] = {
        "chat_id": item["chat_id"],
        "text": item["text"],
    }
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    await bot.send_message(**kwargs)


async def outbox_loop(bot: Bot, client: BackendClient) -> None:
    """Бесконечный цикл опроса очереди исходящих сообщений.

    Каждые ``_POLL_INTERVAL_SECONDS`` секунд запрашивает у backend
    неотправленные записи из outbox и отправляет их пользователям.

    Контракт ack (§2.7):
    - Успех → ``ack_outbox(id, status="sent")``.
    - Любое исключение (включая Telegram*Error) →
      ``ack_outbox(id, status="failed", error=str(exc))``; backend сам
      решает, ретраить (до 3 попыток) или окончательно зафейлить.

    Args:
        bot: Экземпляр aiogram Bot.
        client: BackendClient для работы с внутренним API.
    """
    while True:
        try:
            items = await client.get_outbox(limit=50)
            for item in items:
                msg_id = item["id"]
                chat_id = item["chat_id"]

                try:
                    await _send_one(bot, item)
                except TelegramRetryAfter as exc:
                    logger.warning(
                        "Flood control: ждём %d сек перед следующей итерацией",
                        exc.retry_after,
                    )
                    await client.ack_outbox(
                        msg_id, status="failed", error=f"retry_after={exc.retry_after}"
                    )
                    await asyncio.sleep(exc.retry_after)
                    continue
                except TelegramForbiddenError as exc:
                    logger.warning(
                        "Бот заблокирован пользователем chat_id=%d, ack=failed",
                        chat_id,
                    )
                    await client.ack_outbox(
                        msg_id, status="failed", error=str(exc)
                    )
                    continue
                except Exception as exc:
                    logger.error(
                        "Ошибка отправки сообщения id=%d: %s", msg_id, exc
                    )
                    await client.ack_outbox(
                        msg_id, status="failed", error=str(exc)
                    )
                    continue

                logger.info(
                    "Отправлено сообщение id=%d → chat_id=%d", msg_id, chat_id
                )
                await client.ack_outbox(msg_id, status="sent")

        except asyncio.CancelledError:
            logger.info("Outbox loop остановлен")
            raise
        except Exception as exc:
            logger.error("Ошибка в outbox_loop: %s", exc)

        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
