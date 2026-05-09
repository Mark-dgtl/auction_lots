"""Передача логов бота в backend для admin live-tail (см. §2.7, §2.9.2).

Состоит из двух компонентов:

* :class:`LogForwardHandler` — синхронный ``logging.Handler``, который
  кладёт записи в ``asyncio.Queue`` без блокировки.
* :func:`log_forwarder_loop` — асинхронный воркер, который батчует
  записи и шлёт их в backend ``POST /api/internal/bot/log``.

Принципы:
- Никогда не должны блокировать поток логирования (в т.ч. event loop).
- При переполнении очереди — молча дропаем запись (никаких log() здесь!),
  иначе получим бесконечную рекурсию.
- Потеря записей при ошибке backend допустима: они уже не in-memory.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from bot.services.backend_client import BackendClient

logger = logging.getLogger("bot.log_forwarder")

# Жёсткий лимит контракта §2.7: <= 200 записей за один POST.
_MAX_BATCH = 200


class LogForwardHandler(logging.Handler):
    """``logging.Handler``, перекладывающий записи в ``asyncio.Queue``.

    Сконвертированный dict имеет вид:
    ``{"ts": ISO-UTC, "level": str, "name": str, "message": str}``
    — ровно как ожидает backend по контракту §2.7.

    Args:
        queue: Очередь, в которую помещаются записи.
        min_level: Минимальный уровень логов для пересылки.
    """

    def __init__(
        self,
        queue: asyncio.Queue[dict[str, Any]],
        min_level: int = logging.INFO,
    ) -> None:
        super().__init__(level=min_level)
        self._queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        """Кладёт запись в очередь без блокировки.

        При полной очереди — молча дропает (важно: НЕЛЬЗЯ ничего логировать
        внутри handler'а, иначе будет рекурсия).
        """
        try:
            payload = {
                "ts": datetime.fromtimestamp(
                    record.created, tz=timezone.utc
                ).isoformat(),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            }
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Намеренно молча: иначе self.handleError → log → рекурсия.
            return
        except Exception:
            # Ни при каких обстоятельствах нельзя пробрасывать исключение
            # из логирования — это уронит вызывающий код.
            return


async def log_forwarder_loop(
    client: BackendClient,
    queue: asyncio.Queue[dict[str, Any]],
    batch_size: int = 50,
    flush_interval_seconds: float = 5.0,
) -> None:
    """Асинхронный воркер: батчит логи из очереди и шлёт в backend.

    Поведение:
    - Накапливает записи во внутренний буфер.
    - Флашит, когда:
      * буфер достиг ``batch_size`` (но не больше ``_MAX_BATCH = 200``);
      * прошло ``flush_interval_seconds`` без флаша при наличии записей.
    - На ошибку клиента — WARNING, буфер очищается (записи теряем — это
      допустимо по контракту: они уже out-of-memory логирования бота).
    - На ``asyncio.CancelledError`` — флашит остаток и выходит.

    Args:
        client: Сконфигурированный BackendClient.
        queue: Очередь, заполняемая ``LogForwardHandler``.
        batch_size: Желаемый размер батча перед флашем.
        flush_interval_seconds: Максимальная задержка флаша по времени.
    """
    effective_batch = min(batch_size, _MAX_BATCH)
    buffer: list[dict[str, Any]] = []
    deadline: float | None = None
    loop = asyncio.get_running_loop()

    async def _flush() -> None:
        if not buffer:
            return
        # Шлём чанками не более _MAX_BATCH (на случай batch_size > 200
        # или если буфер успел переполниться).
        to_send = buffer[:]
        buffer.clear()
        for i in range(0, len(to_send), _MAX_BATCH):
            chunk = to_send[i : i + _MAX_BATCH]
            try:
                await client.post_logs(chunk)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Log forwarder: не удалось доставить %d записей: %s",
                    len(chunk),
                    exc,
                )
                # Не пытаемся ретраить: следующий батч уже в пути.

    try:
        while True:
            timeout: float | None
            if deadline is None:
                timeout = None  # ждём первую запись бесконечно
            else:
                timeout = max(0.0, deadline - loop.time())

            try:
                record = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                await _flush()
                deadline = None
                continue

            buffer.append(record)
            if deadline is None:
                deadline = loop.time() + flush_interval_seconds

            if len(buffer) >= effective_batch:
                await _flush()
                deadline = None
    except asyncio.CancelledError:
        # Финальный флаш на shutdown.
        try:
            await _flush()
        except Exception as exc:
            logger.warning("Финальный флаш логов не удался: %s", exc)
        raise
