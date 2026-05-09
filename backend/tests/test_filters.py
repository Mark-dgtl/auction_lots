"""Тесты сохранённых фильтров: CRUD."""

import pytest
from httpx import AsyncClient

FILTER_PAYLOAD = {
    "name": "Квартиры в Москве",
    "filter": {
        "query": "квартира",
        "category": "real_estate",
        "region": "45",
        "price_from": None,
        "price_to": 5000000,
    },
    "notify_enabled": False,
}


async def test_filters_empty(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Пустой список фильтров при отсутствии данных."""
    resp = await client.get("/api/filters", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_create_filter(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Создание фильтра возвращает 201 с данными фильтра."""
    resp = await client.post(
        "/api/filters", json=FILTER_PAYLOAD, headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == FILTER_PAYLOAD["name"]
    assert data["filter"]["category"] == "real_estate"
    assert data["notify_enabled"] is False
    assert "id" in data
    assert "created_at" in data


async def test_list_filters(
    client: AsyncClient, auth_headers: dict
) -> None:
    """После создания фильтр появляется в списке."""
    await client.post("/api/filters", json=FILTER_PAYLOAD, headers=auth_headers)
    resp = await client.get("/api/filters", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


async def test_update_filter(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Обновление фильтра изменяет его поля."""
    create_resp = await client.post(
        "/api/filters", json=FILTER_PAYLOAD, headers=auth_headers
    )
    filter_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/filters/{filter_id}",
        json={"name": "Обновлённое название", "notify_enabled": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Обновлённое название"
    assert data["notify_enabled"] is True


async def test_delete_filter(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Удаление фильтра возвращает 204."""
    create_resp = await client.post(
        "/api/filters", json=FILTER_PAYLOAD, headers=auth_headers
    )
    filter_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/filters/{filter_id}", headers=auth_headers
    )
    assert resp.status_code == 204

    list_resp = await client.get("/api/filters", headers=auth_headers)
    assert list_resp.json()["items"] == []


async def test_delete_not_found(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Удаление несуществующего фильтра возвращает 404."""
    resp = await client.delete("/api/filters/99999", headers=auth_headers)
    assert resp.status_code == 404


async def test_filters_isolation(client: AsyncClient, engine) -> None:
    """Фильтры одного пользователя не видны другому."""
    # Регистрируем двух пользователей
    await client.post(
        "/api/auth/register",
        json={"email": "user1@example.com", "password": "password1"},
    )
    await client.post(
        "/api/auth/register",
        json={"email": "user2@example.com", "password": "password2"},
    )

    resp1 = await client.post(
        "/api/auth/login",
        json={"email": "user1@example.com", "password": "password1"},
    )
    headers1 = {"Authorization": f"Bearer {resp1.json()['access_token']}"}

    resp2 = await client.post(
        "/api/auth/login",
        json={"email": "user2@example.com", "password": "password2"},
    )
    headers2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

    # User1 создаёт фильтр
    await client.post("/api/filters", json=FILTER_PAYLOAD, headers=headers1)

    # User2 не видит фильтр User1
    list_resp = await client.get("/api/filters", headers=headers2)
    assert list_resp.json()["items"] == []


async def test_filters_requires_auth(client: AsyncClient) -> None:
    """Доступ к фильтрам без токена возвращает 401."""
    resp = await client.get("/api/filters")
    assert resp.status_code == 401
