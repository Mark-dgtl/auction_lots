"""Тесты избранного: добавление, удаление, список."""

import pytest
from httpx import AsyncClient


async def test_favorites_empty(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Пустой список избранного при отсутствии данных."""
    resp = await client.get("/api/favorites", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_add_favorite(
    client: AsyncClient, auth_headers: dict, sample_lots: list[int]
) -> None:
    """Добавление лота в избранное возвращает 204."""
    lot_id = sample_lots[0]
    resp = await client.post(f"/api/favorites/{lot_id}", headers=auth_headers)
    assert resp.status_code == 204


async def test_add_favorite_idempotent(
    client: AsyncClient, auth_headers: dict, sample_lots: list[int]
) -> None:
    """Повторное добавление в избранное не вызывает ошибки."""
    lot_id = sample_lots[0]
    await client.post(f"/api/favorites/{lot_id}", headers=auth_headers)
    resp = await client.post(f"/api/favorites/{lot_id}", headers=auth_headers)
    assert resp.status_code == 204


async def test_favorites_list_after_add(
    client: AsyncClient, auth_headers: dict, sample_lots: list[int]
) -> None:
    """После добавления лот появляется в списке избранного."""
    lot_id = sample_lots[0]
    await client.post(f"/api/favorites/{lot_id}", headers=auth_headers)

    resp = await client.get("/api/favorites", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == lot_id
    assert data["items"][0]["is_favorite"] is True


async def test_remove_favorite(
    client: AsyncClient, auth_headers: dict, sample_lots: list[int]
) -> None:
    """Удаление лота из избранного возвращает 204."""
    lot_id = sample_lots[0]
    await client.post(f"/api/favorites/{lot_id}", headers=auth_headers)
    resp = await client.delete(f"/api/favorites/{lot_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp2 = await client.get("/api/favorites", headers=auth_headers)
    assert resp2.json()["total"] == 0


async def test_remove_nonexistent_favorite(
    client: AsyncClient, auth_headers: dict, sample_lots: list[int]
) -> None:
    """Удаление лота не из избранного возвращает 404."""
    lot_id = sample_lots[0]
    resp = await client.delete(f"/api/favorites/{lot_id}", headers=auth_headers)
    assert resp.status_code == 404


async def test_add_favorite_nonexistent_lot(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Добавление несуществующего лота возвращает 404."""
    resp = await client.post("/api/favorites/99999", headers=auth_headers)
    assert resp.status_code == 404


async def test_favorites_requires_auth(client: AsyncClient) -> None:
    """Доступ к избранному без токена возвращает 401."""
    resp = await client.get("/api/favorites")
    assert resp.status_code == 401
