"""Тесты CRUD пользователей в Admin API."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def _make_admin(db: AsyncSession, user_id: int) -> None:
    user = await db.scalar(select(User).where(User.id == user_id))
    user.is_admin = True
    await db.commit()


@pytest.fixture
async def admin_user(client: AsyncClient, registered_user: dict, db_session: AsyncSession) -> dict:
    """Создаёт администратора и возвращает данные вместе с auth-заголовками."""
    await _make_admin(db_session, registered_user["id"])
    resp = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    token = resp.json()["access_token"]
    return {**registered_user, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, admin_user: dict):
    """GET /api/admin/users → список пользователей."""
    resp = await client.get("/api/admin/users", headers=admin_user["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient, admin_user: dict):
    """GET /api/admin/users/{id} → детальная информация о пользователе."""
    resp = await client.get(
        f"/api/admin/users/{admin_user['id']}", headers=admin_user["headers"]
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == admin_user["email"]
    assert "recent_outbox" in data
    assert "recent_filters" in data


@pytest.mark.asyncio
async def test_patch_user_full_name(
    client: AsyncClient, admin_user: dict, db_session: AsyncSession
):
    """PATCH /api/admin/users/{id} → обновление full_name."""
    resp = await client.patch(
        f"/api/admin/users/{admin_user['id']}",
        json={"full_name": "Иван Иванов"},
        headers=admin_user["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Иван Иванов"


@pytest.mark.asyncio
async def test_cannot_remove_own_admin(
    client: AsyncClient, admin_user: dict, db_session: AsyncSession
):
    """PATCH нельзя снять is_admin с самого себя → 409 ALREADY_ADMIN."""
    resp = await client.patch(
        f"/api/admin/users/{admin_user['id']}",
        json={"is_admin": False},
        headers=admin_user["headers"],
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_ADMIN"


@pytest.mark.asyncio
async def test_cannot_delete_last_admin(
    client: AsyncClient, admin_user: dict, db_session: AsyncSession
):
    """DELETE нельзя удалить последнего администратора → 409 ALREADY_ADMIN."""
    resp = await client.delete(
        f"/api/admin/users/{admin_user['id']}",
        headers=admin_user["headers"],
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALREADY_ADMIN"


@pytest.mark.asyncio
async def test_can_delete_regular_user(
    client: AsyncClient, admin_user: dict, db_session: AsyncSession
):
    """DELETE /api/admin/users/{id} успешно удаляет обычного пользователя."""
    # Регистрируем второго пользователя
    resp = await client.post(
        "/api/auth/register",
        json={"email": "todelete@example.com", "password": "password123"},
    )
    user_id = resp.json()["id"]

    del_resp = await client.delete(
        f"/api/admin/users/{user_id}", headers=admin_user["headers"]
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_block_user(
    client: AsyncClient, admin_user: dict, db_session: AsyncSession
):
    """PATCH is_blocked=true блокирует пользователя."""
    # Регистрируем второго пользователя
    resp = await client.post(
        "/api/auth/register",
        json={"email": "toblock@example.com", "password": "password123"},
    )
    user_id = resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_blocked": True},
        headers=admin_user["headers"],
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_blocked"] is True
