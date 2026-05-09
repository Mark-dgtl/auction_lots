"""Юнит-тесты LogForwardHandler и log_forwarder_loop."""

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from bot.services.log_forwarder import LogForwardHandler, log_forwarder_loop


def _make_record(msg: str = "hello", level: int = logging.INFO) -> logging.LogRecord:
    """Фабрика LogRecord для тестов."""
    return logging.LogRecord(
        name="test.logger",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


@pytest.mark.asyncio
async def test_handler_puts_record_into_queue():
    """LogForwardHandler.emit кладёт правильный dict в очередь."""
    queue: asyncio.Queue = asyncio.Queue()
    handler = LogForwardHandler(queue=queue, min_level=logging.INFO)

    handler.emit(_make_record("msg-1"))

    payload = queue.get_nowait()
    assert payload["message"] == "msg-1"
    assert payload["level"] == "INFO"
    assert payload["name"] == "test.logger"
    assert payload["ts"].endswith("+00:00") or payload["ts"].endswith("Z")


@pytest.mark.asyncio
async def test_handler_drops_silently_on_full_queue():
    """При переполнении очереди emit не должен бросать исключение."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    handler = LogForwardHandler(queue=queue)
    handler.emit(_make_record("first"))
    # Должно быть тихим дропом, а не raise.
    handler.emit(_make_record("second"))
    handler.emit(_make_record("third"))
    assert queue.qsize() == 1


@pytest.mark.asyncio
async def test_log_forwarder_flushes_on_batch_size():
    """При достижении batch_size батч уезжает немедленно."""
    queue: asyncio.Queue = asyncio.Queue()
    client = AsyncMock()
    client.post_logs = AsyncMock(return_value=None)

    task = asyncio.create_task(
        log_forwarder_loop(
            client, queue, batch_size=3, flush_interval_seconds=10.0
        )
    )

    for i in range(3):
        queue.put_nowait({"ts": "x", "level": "INFO", "name": "n", "message": str(i)})

    # Даём воркеру время прочитать и заслать.
    for _ in range(50):
        if client.post_logs.await_count >= 1:
            break
        await asyncio.sleep(0.02)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert client.post_logs.await_count >= 1
    sent = client.post_logs.await_args_list[0].args[0]
    assert len(sent) == 3
    assert sent[0]["message"] == "0"
    assert sent[2]["message"] == "2"


@pytest.mark.asyncio
async def test_log_forwarder_flushes_on_timeout():
    """Если не накопили batch_size, флашим по timeout."""
    queue: asyncio.Queue = asyncio.Queue()
    client = AsyncMock()
    client.post_logs = AsyncMock(return_value=None)

    task = asyncio.create_task(
        log_forwarder_loop(
            client, queue, batch_size=100, flush_interval_seconds=0.1
        )
    )

    queue.put_nowait({"ts": "x", "level": "INFO", "name": "n", "message": "one"})
    queue.put_nowait({"ts": "x", "level": "INFO", "name": "n", "message": "two"})

    # Ждём timeout-флаш.
    for _ in range(50):
        if client.post_logs.await_count >= 1:
            break
        await asyncio.sleep(0.05)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert client.post_logs.await_count >= 1
    sent = client.post_logs.await_args_list[0].args[0]
    assert [r["message"] for r in sent] == ["one", "two"]


@pytest.mark.asyncio
async def test_log_forwarder_survives_client_error():
    """Ошибка post_logs не должна останавливать воркер."""
    queue: asyncio.Queue = asyncio.Queue()
    client = AsyncMock()
    client.post_logs = AsyncMock(
        side_effect=[RuntimeError("boom"), None, None]
    )

    task = asyncio.create_task(
        log_forwarder_loop(
            client, queue, batch_size=1, flush_interval_seconds=10.0
        )
    )

    for i in range(3):
        queue.put_nowait({"ts": "x", "level": "INFO", "name": "n", "message": str(i)})

    for _ in range(50):
        if client.post_logs.await_count >= 3:
            break
        await asyncio.sleep(0.02)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert client.post_logs.await_count >= 3


@pytest.mark.asyncio
async def test_log_forwarder_flushes_remainder_on_cancel():
    """При CancelledError остаток буфера должен уйти финальным флашем."""
    queue: asyncio.Queue = asyncio.Queue()
    client = AsyncMock()
    client.post_logs = AsyncMock(return_value=None)

    task = asyncio.create_task(
        log_forwarder_loop(
            client, queue, batch_size=100, flush_interval_seconds=10.0
        )
    )

    queue.put_nowait({"ts": "x", "level": "INFO", "name": "n", "message": "tail"})
    # Дадим воркеру забрать в буфер (но не флашить — таймаут далеко).
    await asyncio.sleep(0.1)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert client.post_logs.await_count == 1
    assert client.post_logs.await_args_list[0].args[0][0]["message"] == "tail"
