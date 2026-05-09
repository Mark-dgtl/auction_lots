"""Юнит-тесты heartbeat_loop."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from bot.services.heartbeat import heartbeat_loop


@pytest.mark.asyncio
async def test_heartbeat_loop_calls_post_heartbeat_periodically():
    """За 1 секунду при interval_seconds=0.2 должно быть >= 4 вызовов."""
    client = AsyncMock()
    client.post_heartbeat = AsyncMock(return_value=None)

    task = asyncio.create_task(
        heartbeat_loop(client, interval_seconds=0.2, version="test-1.0")
    )
    await asyncio.sleep(1.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert client.post_heartbeat.await_count >= 4
    # Проверяем, что в payload передаются ожидаемые аргументы.
    args, kwargs = client.post_heartbeat.call_args
    assert kwargs.get("polling_ok") is True
    assert kwargs.get("version") == "test-1.0"


@pytest.mark.asyncio
async def test_heartbeat_loop_survives_client_errors():
    """Ошибки клиента не должны останавливать цикл."""
    client = AsyncMock()
    # Каждый второй вызов кидает, остальные — ОК.
    client.post_heartbeat = AsyncMock(
        side_effect=[
            RuntimeError("backend down"),
            None,
            RuntimeError("still down"),
            None,
            None,
            None,
        ]
    )

    task = asyncio.create_task(
        heartbeat_loop(client, interval_seconds=0.05, version="x")
    )
    await asyncio.sleep(0.4)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Цикл должен был сделать несколько попыток несмотря на ошибки.
    assert client.post_heartbeat.await_count >= 4


@pytest.mark.asyncio
async def test_heartbeat_loop_handles_cancel_cleanly():
    """CancelledError корректно пробрасывается, без подавления."""
    client = AsyncMock()
    client.post_heartbeat = AsyncMock(return_value=None)

    task = asyncio.create_task(
        heartbeat_loop(client, interval_seconds=10, version="x")
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
