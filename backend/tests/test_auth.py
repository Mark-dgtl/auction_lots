"""Тесты аутентификации: регистрация, вход, refresh, logout."""

import pytest
from httpx import AsyncClient


async def test_register_success(client: AsyncClient) -> None:
    """Регистрация нового пользователя возвращает 201 с id и email."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "securepass"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert "id" in data


async def test_register_email_lowercased(client: AsyncClient) -> None:
    """Email приводится к нижнему регистру при регистрации."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "UPPER@EXAMPLE.COM", "password": "securepass"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "upper@example.com"


async def test_register_duplicate_email(client: AsyncClient) -> None:
    """Повторная регистрация с тем же email возвращает 409 CONFLICT."""
    payload = {"email": "dup@example.com", "password": "securepass"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_register_short_password(client: AsyncClient) -> None:
    """Пароль короче 8 символов возвращает 422 VALIDATION_ERROR."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "short"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login_success(client: AsyncClient) -> None:
    """Успешный вход возвращает access_token и cookie refresh_token."""
    await client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "securepass"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "securepass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    # cookie refresh_token установлен
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password(client: AsyncClient) -> None:
    """Неверный пароль возвращает 401 UNAUTHORIZED."""
    await client.post(
        "/api/auth/register",
        json={"email": "wp@example.com", "password": "correctpass"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "wp@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_login_unknown_email(client: AsyncClient) -> None:
    """Вход с несуществующим email возвращает 401."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "somepass"},
    )
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient) -> None:
    """Refresh-токен из cookie обновляет access-токен."""
    await client.post(
        "/api/auth/register",
        json={"email": "ref@example.com", "password": "securepass"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "ref@example.com", "password": "securepass"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.cookies.get("refresh_token")
    assert refresh_token

    resp = await client.post(
        "/api/auth/refresh",
        cookies={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_refresh_without_cookie(client: AsyncClient) -> None:
    """Refresh без cookie возвращает 401."""
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 401


async def test_logout(client: AsyncClient, auth_headers: dict) -> None:
    """Logout отзывает refresh-токен."""
    # Логинимся повторно чтобы получить cookie
    from tests.conftest import CATEGORIES_SEED

    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    refresh_token = login_resp.cookies.get("refresh_token")

    resp = await client.post(
        "/api/auth/logout",
        cookies={"refresh_token": refresh_token},
    )
    assert resp.status_code == 204

    # После logout refresh-токен уже не работает
    resp2 = await client.post(
        "/api/auth/refresh",
        cookies={"refresh_token": refresh_token},
    )
    assert resp2.status_code == 401


async def test_get_me(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/me возвращает данные текущего пользователя."""
    resp = await client.get("/api/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["telegram_linked"] is False
    assert "id" in data


async def test_get_me_unauthorized(client: AsyncClient) -> None:
    """GET /api/me без токена возвращает 401."""
    resp = await client.get("/api/me")
    assert resp.status_code == 401
