"""Тесты internal bot endpoints: heartbeat и log batch."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.log_buffer import ring_handler
from app.models.bot_heartbeat import BotHeartbeat

_INTERNAL_HEADERS = {"X-Internal-Token": settings.INTERNAL_API_TOKEN}


@pytest.mark.asyncio
async def test_heartbeat_creates_record(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /api/internal/bot/heartbeat создаёт/обновляет запись heartbeat."""
    # Создаём начальную запись
    hb = BotHeartbeat(id=1)
    db_session.add(hb)
    await db_session.commit()

    resp = await client.post(
        "/api/internal/bot/heartbeat",
        json={"polling_ok": True, "version": "1.2.3"},
        headers=_INTERNAL_HEADERS,
    )
    assert resp.status_code == 204

    await db_session.refresh(hb)
    assert hb.polling_ok is True
    assert hb.version == "1.2.3"
    assert hb.last_seen_at is not None


@pytest.mark.asyncio
async def test_heartbeat_updates_polling_status(
    client: AsyncClient, db_session: AsyncSession
):
    """Повторный heartbeat обновляет polling_ok."""
    hb = BotHeartbeat(id=1, polling_ok=True)
    db_session.add(hb)
    await db_session.commit()

    resp = await client.post(
        "/api/internal/bot/heartbeat",
        json={"polling_ok": False},
        headers=_INTERNAL_HEADERS,
    )
    assert resp.status_code == 204

    await db_session.refresh(hb)
    assert hb.polling_ok is False


@pytest.mark.asyncio
async def test_bot_log_batch_stored_in_buffer(client: AsyncClient):
    """POST /api/internal/bot/log пушит записи в кольцевой буфер."""
    before_count = len(ring_handler.snapshot(q="bot_log_batch_unique_marker"))

    resp = await client.post(
        "/api/internal/bot/log",
        json={
            "records": [
                {
                    "ts": "2026-04-25T10:00:00Z",
                    "level": "INFO",
                    "name": "bot.polling",
                    "message": "bot_log_batch_unique_marker",
                }
            ]
        },
        headers=_INTERNAL_HEADERS,
    )
    assert resp.status_code == 204

    after = ring_handler.snapshot(q="bot_log_batch_unique_marker")
    assert len(after) > before_count
    assert after[-1]["source"] == "bot"


@pytest.mark.asyncio
async def test_bot_log_requires_internal_token(client: AsyncClient):
    """POST /api/internal/bot/log без токена → 403."""
    resp = await client.post(
        "/api/internal/bot/log",
        json={"records": []},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_heartbeat_requires_internal_token(client: AsyncClient):
    """POST /api/internal/bot/heartbeat без токена → 403."""
    resp = await client.post(
        "/api/internal/bot/heartbeat",
        json={"polling_ok": True},
    )
    assert resp.status_code == 403
