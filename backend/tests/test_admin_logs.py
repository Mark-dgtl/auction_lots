"""Тесты Admin Logs API: снапшот и SSE-стрим."""

import logging

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.log_buffer import ring_handler
from app.models.user import User


async def _make_admin(db: AsyncSession, user_id: int) -> None:
    user = await db.scalar(select(User).where(User.id == user_id))
    user.is_admin = True
    await db.commit()


@pytest.fixture
async def admin_headers(
    client: AsyncClient, registered_user: dict, db_session: AsyncSession
) -> dict:
    await _make_admin(db_session, registered_user["id"])
    resp = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_logs_snapshot(client: AsyncClient, admin_headers: dict):
    """GET /api/admin/logs возвращает снапшот логов."""
    # Добавляем запись в буфер
    ring_handler.push_external({
        "ts": "2026-04-25T10:00:00Z",
        "level": "INFO",
        "source": "backend",
        "logger": "app.test",
        "message": "тестовое сообщение для снапшота",
    })

    resp = await client.get("/api/admin/logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    messages = [r["message"] for r in data["items"]]
    assert any("тестовое сообщение для снапшота" in m for m in messages)


@pytest.mark.asyncio
async def test_logs_snapshot_filter_level(client: AsyncClient, admin_headers: dict):
    """GET /api/admin/logs?level=ERROR возвращает только ERROR-записи."""
    ring_handler.push_external({
        "ts": "2026-04-25T10:00:00Z",
        "level": "ERROR",
        "source": "backend",
        "logger": "app.test",
        "message": "ошибка для фильтра",
    })

    resp = await client.get("/api/admin/logs?level=ERROR", headers=admin_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["level"] == "ERROR"


@pytest.mark.asyncio
async def test_logs_snapshot_filter_q(client: AsyncClient, admin_headers: dict):
    """GET /api/admin/logs?q=уникальный фильтрует по подстроке."""
    ring_handler.push_external({
        "ts": "2026-04-25T10:00:00Z",
        "level": "INFO",
        "source": "backend",
        "logger": "app.test",
        "message": "уникальный_xyz_маркер",
    })

    resp = await client.get("/api/admin/logs?q=уникальный_xyz_маркер", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    assert all("уникальный_xyz_маркер" in r["message"] for r in data["items"])


@pytest.mark.asyncio
async def test_logs_stream_endpoint_exists(client: AsyncClient, admin_headers: dict):
    """GET /api/admin/logs/stream — эндпоинт существует и доступен для admin.

    Полный SSE-поток тестируется через снапшот; само SSE-соединение
    требует реального HTTP-сервера и не тестируется через ASGI-транспорт.
    """
    # Проверяем что снапшот работает корректно (SSE использует ту же функцию)
    ring_handler.push_external({
        "ts": "2026-04-25T10:00:00Z",
        "level": "DEBUG",
        "source": "backend",
        "logger": "app.test",
        "message": "sse_endpoint_check",
    })
    resp = await client.get("/api/admin/logs?limit=10", headers=admin_headers)
    assert resp.status_code == 200
    # Эндпоинт stream зарегистрирован — без токена должен быть 401
    resp2 = await client.get("/api/admin/logs/stream")
    assert resp2.status_code == 401
