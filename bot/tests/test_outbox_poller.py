"""Юнит-тесты BackendClient: get_outbox и ack_outbox."""

import pytest
import respx
from httpx import Response

from bot.services.backend_client import BackendClient


@pytest.mark.asyncio
async def test_get_outbox_returns_items(backend_url, internal_token):
    """get_outbox возвращает список items из ответа backend."""
    items = [
        {"id": 1, "chat_id": 100, "text": "Сообщение 1", "lot_ids": []},
        {"id": 2, "chat_id": 200, "text": "Сообщение 2", "lot_ids": [10, 11]},
    ]
    with respx.mock(base_url=backend_url) as mock:
        mock.get("/api/internal/outbox").mock(
            return_value=Response(200, json={"items": items})
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        result = await client.get_outbox(limit=50)

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["text"] == "Сообщение 2"


@pytest.mark.asyncio
async def test_get_outbox_backend_error(backend_url, internal_token):
    """При ошибке backend get_outbox возвращает пустой список."""
    with respx.mock(base_url=backend_url) as mock:
        mock.get("/api/internal/outbox").mock(return_value=Response(500))
        client = BackendClient(base_url=backend_url, token=internal_token)
        result = await client.get_outbox()

    assert result == []


@pytest.mark.asyncio
async def test_ack_outbox_calls_correct_endpoint(backend_url, internal_token):
    """ack_outbox вызывает POST /api/internal/outbox/{id}/ack."""
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/outbox/42/ack").mock(
            return_value=Response(204)
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.ack_outbox(42)

    assert route.called


@pytest.mark.asyncio
async def test_get_outbox_empty(backend_url, internal_token):
    """Пустая очередь → пустой список."""
    with respx.mock(base_url=backend_url) as mock:
        mock.get("/api/internal/outbox").mock(
            return_value=Response(200, json={"items": []})
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        result = await client.get_outbox()

    assert result == []


@pytest.mark.asyncio
async def test_get_outbox_network_error(backend_url, internal_token):
    """Ошибка сети → пустой список, не падает."""
    import httpx

    with respx.mock(base_url=backend_url) as mock:
        mock.get("/api/internal/outbox").mock(
            side_effect=httpx.ConnectError("timeout")
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        result = await client.get_outbox()

    assert result == []
