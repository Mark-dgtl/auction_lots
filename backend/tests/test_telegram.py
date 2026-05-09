"""Тесты Telegram-интеграции: генерация deep-link, unlink, internal bind."""

import pytest
from httpx import AsyncClient


async def test_generate_link(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /api/telegram/link возвращает deep_link, token и expires_at."""
    resp = await client.post("/api/telegram/link", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "deep_link" in data
    assert "token" in data
    assert "expires_at" in data
    assert data["token"] in data["deep_link"]


async def test_generate_link_requires_auth(client: AsyncClient) -> None:
    """Генерация deep-link без авторизации возвращает 401."""
    resp = await client.post("/api/telegram/link")
    assert resp.status_code == 401


async def test_unlink_telegram(
    client: AsyncClient, auth_headers: dict
) -> None:
    """POST /api/telegram/unlink возвращает 204."""
    resp = await client.post("/api/telegram/unlink", headers=auth_headers)
    assert resp.status_code == 204


async def test_internal_bind_telegram(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Внутренний эндпоинт /api/internal/telegram/bind привязывает аккаунт."""
    # Сначала генерируем токен
    link_resp = await client.post("/api/telegram/link", headers=auth_headers)
    token = link_resp.json()["token"]

    # Привязываем через внутренний API
    resp = await client.post(
        "/api/internal/telegram/bind",
        json={"token": token, "telegram_user_id": 123456789, "chat_id": 987654321},
        headers={"X-Internal-Token": "change-me-internal-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data

    # После привязки telegram_linked=true
    me_resp = await client.get("/api/me", headers=auth_headers)
    assert me_resp.json()["telegram_linked"] is True


async def test_internal_bind_wrong_token(client: AsyncClient) -> None:
    """Привязка с несуществующим токеном возвращает 404."""
    resp = await client.post(
        "/api/internal/telegram/bind",
        json={"token": "nonexistent", "telegram_user_id": 1, "chat_id": 1},
        headers={"X-Internal-Token": "change-me-internal-token"},
    )
    assert resp.status_code == 404


async def test_internal_requires_token(client: AsyncClient) -> None:
    """Внутренний API без X-Internal-Token возвращает 403."""
    resp = await client.post(
        "/api/internal/telegram/bind",
        json={"token": "x", "telegram_user_id": 1, "chat_id": 1},
    )
    assert resp.status_code == 403
