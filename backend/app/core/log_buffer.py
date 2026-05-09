"""Кольцевой буфер логов с поддержкой SSE-подписчиков.

Используется для live-tail логов в /api/admin/logs и /api/admin/logs/stream.
Поддерживает логи backend (через logging.Handler) и бота (через push_external).
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("app.admin.log_buffer")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RingLogHandler(logging.Handler):
    """Logging handler, хранящий последние N записей в памяти.

    Также уведомляет всех подписчиков (asyncio.Queue) о новых записях.

    Attributes:
        _buffer: Кольцевой буфер записей.
        _subscribers: Множество активных Queue-подписчиков.
        _loop: Event loop для thread-safe нотификации.
    """

    def __init__(self) -> None:
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=settings.ADMIN_LOG_BUFFER_SIZE)
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop | None:
        """Возвращает текущий event loop, если он работает."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return loop
        except RuntimeError:
            pass
        return None

    def emit(self, record: logging.LogRecord) -> None:
        """Добавляет запись в буфер и уведомляет подписчиков."""
        record_dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "level": record.levelname,
            "source": "backend",
            "logger": record.name,
            "message": self.format(record),
        }
        self._push(record_dict)

    def push_external(self, record_dict: dict) -> None:
        """Добавляет внешнюю запись (например, от бота) в буфер.

        Args:
            record_dict: Словарь с полями ts, level, source, logger, message.
        """
        self._push(record_dict)

    def _push(self, record_dict: dict) -> None:
        """Помещает запись в буфер и нотифицирует подписчиков."""
        self._buffer.append(record_dict)
        loop = self._get_loop()
        if loop is not None:
            loop.call_soon_threadsafe(self._notify_subscribers, record_dict)

    def _notify_subscribers(self, record_dict: dict) -> None:
        """Уведомляет всех активных подписчиков о новой записи."""
        dead = set()
        for q in self._subscribers:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(record_dict)
            except Exception:
                dead.add(q)
        self._subscribers -= dead

    def subscribe(self) -> asyncio.Queue:
        """Создаёт новый канал подписки на живой поток записей.

        Returns:
            asyncio.Queue с maxsize=200.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Отписывается от живого потока.

        Args:
            q: Queue, возвращённый subscribe().
        """
        self._subscribers.discard(q)

    def snapshot(
        self,
        level: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict]:
        """Возвращает снапшот буфера с фильтрацией.

        Args:
            level: Фильтр по уровню логирования (INFO, WARNING и т.д.).
            q: Подстрока для поиска в message (регистронезависимо).
            limit: Максимальное число записей.

        Returns:
            Список словарей-записей логов.
        """
        records = list(self._buffer)
        if level:
            level_upper = level.upper()
            records = [r for r in records if r.get("level") == level_upper]
        if q:
            q_lower = q.lower()
            records = [r for r in records if q_lower in r.get("message", "").lower()]
        return records[-limit:]


# Singleton-инстанс
ring_handler = RingLogHandler()
ring_handler.setFormatter(
    logging.Formatter("%(message)s")
)
