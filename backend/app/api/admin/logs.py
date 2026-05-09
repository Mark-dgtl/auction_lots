"""Эндпоинты /api/admin/logs и /api/admin/logs/stream."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from app.core.log_buffer import ring_handler

router = APIRouter()
logger = logging.getLogger("app.admin.logs")


@router.get("/logs")
async def get_logs(
    level: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    """Возвращает снапшот кольцевого буфера логов.

    Args:
        level: Фильтр по уровню (INFO, WARNING, ERROR и т.д.).
        q: Подстрока для поиска в message (регистронезависимо).
        limit: Максимальное число записей (1..1000).
    """
    items = ring_handler.snapshot(level=level, q=q, limit=limit)
    return {"items": items}


@router.get("/logs/stream")
async def stream_logs() -> EventSourceResponse:
    """SSE-поток живых логов.

    При подключении отправляет последние 50 записей, затем живые события.
    Каждые 15 секунд отправляет heartbeat-комментарий.
    """

    async def _generator():
        # Отправляем последние 50 записей из снапшота
        for record in ring_handler.snapshot(limit=50):
            yield {"data": json.dumps(record, ensure_ascii=False)}

        queue = ring_handler.subscribe()
        try:
            while True:
                try:
                    record = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {"data": json.dumps(record, ensure_ascii=False)}
                except asyncio.TimeoutError:
                    # Heartbeat каждые 15 сек
                    yield {"comment": "heartbeat"}
        finally:
            ring_handler.unsubscribe(queue)

    return EventSourceResponse(_generator())
