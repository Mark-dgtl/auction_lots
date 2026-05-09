"""Юнит-тесты обновлённого BackendClient.ack_outbox + heartbeat + post_logs."""

import json

import pytest
import respx
from httpx import Response

from bot.services.backend_client import BackendClient


@pytest.mark.asyncio
async def test_ack_outbox_sent_default(backend_url, internal_token):
    """По умолчанию ack шлёт body {status: 'sent'} без error."""
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/outbox/7/ack").mock(
            return_value=Response(204)
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.ack_outbox(7)

    assert route.called
    body = json.loads(route.calls[0].request.content)
    assert body == {"status": "sent"}


@pytest.mark.asyncio
async def test_ack_outbox_failed_with_error(backend_url, internal_token):
    """При status='failed' в body должен быть error."""
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/outbox/9/ack").mock(
            return_value=Response(204)
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.ack_outbox(9, status="failed", error="Forbidden: bot blocked")

    assert route.called
    body = json.loads(route.calls[0].request.content)
    assert body == {"status": "failed", "error": "Forbidden: bot blocked"}


@pytest.mark.asyncio
async def test_ack_outbox_explicit_sent_no_error(backend_url, internal_token):
    """Явный status='sent' без error — поле error не добавляется."""
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/outbox/1/ack").mock(
            return_value=Response(204)
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.ack_outbox(1, status="sent")

    body = json.loads(route.calls[0].request.content)
    assert body == {"status": "sent"}
    assert "error" not in body


@pytest.mark.asyncio
async def test_post_heartbeat_sends_correct_payload(backend_url, internal_token):
    """post_heartbeat шлёт {polling_ok, version} с X-Internal-Token."""
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/bot/heartbeat").mock(
            return_value=Response(204)
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.post_heartbeat(polling_ok=True, version="1.2.3")

    assert route.called
    request = route.calls[0].request
    assert request.headers.get("x-internal-token") == internal_token
    body = json.loads(request.content)
    assert body == {"polling_ok": True, "version": "1.2.3"}


@pytest.mark.asyncio
async def test_post_heartbeat_without_version(backend_url, internal_token):
    """Если version=None — поле в body отсутствует."""
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/bot/heartbeat").mock(
            return_value=Response(204)
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.post_heartbeat(polling_ok=False)

    body = json.loads(route.calls[0].request.content)
    assert body == {"polling_ok": False}


@pytest.mark.asyncio
async def test_post_logs_sends_records_batch(backend_url, internal_token):
    """post_logs шлёт {records: [...]} в нужный endpoint."""
    records = [
        {"ts": "2026-04-25T07:00:00+00:00", "level": "INFO", "name": "x", "message": "hi"},
        {"ts": "2026-04-25T07:00:01+00:00", "level": "WARNING", "name": "y", "message": "ok"},
    ]
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/bot/log").mock(return_value=Response(204))
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.post_logs(records)

    assert route.called
    body = json.loads(route.calls[0].request.content)
    assert body == {"records": records}


@pytest.mark.asyncio
async def test_post_logs_empty_skips_request(backend_url, internal_token):
    """Пустой список — не шлём ничего."""
    with respx.mock(base_url=backend_url, assert_all_called=False) as mock:
        route = mock.post("/api/internal/bot/log").mock(return_value=Response(204))
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.post_logs([])

    assert not route.called


@pytest.mark.asyncio
async def test_post_heartbeat_raises_on_http_error(backend_url, internal_token):
    """post_heartbeat пробрасывает HTTPError, чтобы вызывающий мог поймать."""
    import httpx

    with respx.mock(base_url=backend_url) as mock:
        mock.post("/api/internal/bot/heartbeat").mock(return_value=Response(500))
        client = BackendClient(base_url=backend_url, token=internal_token)
        with pytest.raises(httpx.HTTPStatusError):
            await client.post_heartbeat(polling_ok=True)
