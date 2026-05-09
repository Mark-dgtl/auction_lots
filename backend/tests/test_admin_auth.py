"""Тесты аутентификации к Admin API: 401/403 без токена, 403 без прав, 200 для админа."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def _make_admin(db: AsyncSession, user_id: int) -> None:
    """Повышает пользователя до администратора напрямую в БД."""
    from sqlalchemy import select
    user = await db.scalar(select(User).where(User.id == user_id))
    user.is_admin = True
    await db.commit()


@pytest.mark.asyncio
async def test_admin_requires_token(client: AsyncClient):
    """GET /api/admin/health без токена → 401."""
    resp = await client.get("/api/admin/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_requires_admin_role(
    client: AsyncClient,
    registered_user: dict,
    auth_headers: dict,
):
    """GET /api/admin/health с токеном обычного пользователя → 403 NOT_ADMIN."""
    resp = await client.get("/api/admin/health", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_ADMIN"


@pytest.mark.asyncio
async def test_admin_ok_for_admin(
    client: AsyncClient,
    registered_user: dict,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """GET /api/admin/health для администратора → 200."""
    await _make_admin(db_session, registered_user["id"])
    resp = await client.get("/api/admin/health", headers=auth_headers)
    assert resp.status_code == 200
    assert "db" in resp.json()


@pytest.mark.asyncio
async def test_blocked_admin_gets_403(
    client: AsyncClient,
    registered_user: dict,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Заблокированный администратор получает 403 USER_BLOCKED."""
    from sqlalchemy import select
    user = await db_session.scalar(select(User).where(User.id == registered_user["id"]))
    user.is_admin = True
    user.is_blocked = True
    await db_session.commit()

    resp = await client.get("/api/admin/health", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "USER_BLOCKED"
