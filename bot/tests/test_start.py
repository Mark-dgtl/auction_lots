"""Юнит-тесты BackendClient.bind_telegram (логика хендлера /start)."""

import pytest
import respx
from httpx import Response

from bot.services.backend_client import BackendClient


@pytest.mark.asyncio
async def test_bind_success(backend_url, internal_token):
    """Успешная привязка токена → True."""
    with respx.mock(base_url=backend_url) as mock:
        mock.post("/api/internal/telegram/bind").mock(
            return_value=Response(200, json={"user_id": 42})
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        result = await client.bind_telegram(
            link_token="valid-token", telegram_user_id=111, chat_id=111
        )
    assert result is True


@pytest.mark.asyncio
async def test_bind_invalid_token(backend_url, internal_token):
    """Несуществующий токен → False (backend вернул 404)."""
    with respx.mock(base_url=backend_url) as mock:
        mock.post("/api/internal/telegram/bind").mock(
            return_value=Response(404, json={"error": {"code": "NOT_FOUND", "message": "..."}})
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        result = await client.bind_telegram(
            link_token="bad-token", telegram_user_id=222, chat_id=222
        )
    assert result is False


@pytest.mark.asyncio
async def test_bind_network_error(backend_url, internal_token):
    """Ошибка соединения с backend → False (не падает)."""
    import httpx

    with respx.mock(base_url=backend_url) as mock:
        mock.post("/api/internal/telegram/bind").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        result = await client.bind_telegram(
            link_token="any", telegram_user_id=333, chat_id=333
        )
    assert result is False


@pytest.mark.asyncio
async def test_bind_sends_correct_headers(backend_url, internal_token):
    """Запрос должен содержать X-Internal-Token."""
    with respx.mock(base_url=backend_url) as mock:
        route = mock.post("/api/internal/telegram/bind").mock(
            return_value=Response(200, json={"user_id": 1})
        )
        client = BackendClient(base_url=backend_url, token=internal_token)
        await client.bind_telegram("tok", 1, 1)

    assert route.called
    request = route.calls[0].request
    assert request.headers.get("x-internal-token") == internal_token
