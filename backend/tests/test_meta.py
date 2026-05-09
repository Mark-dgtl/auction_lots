"""Тесты метаданных: справочники категорий и регионов."""

import pytest
from httpx import AsyncClient

EXPECTED_CATEGORY_SLUGS = {
    "real_estate", "vehicle", "equipment", "land",
    "rights", "securities", "inventory", "other",
}


async def test_categories_list(client: AsyncClient) -> None:
    """GET /api/meta/categories возвращает все 8 категорий."""
    resp = await client.get("/api/meta/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    slugs = {item["slug"] for item in data["items"]}
    assert slugs == EXPECTED_CATEGORY_SLUGS
    # Каждый элемент имеет slug и name
    for item in data["items"]:
        assert "slug" in item
        assert "name" in item
        assert len(item["name"]) > 0


async def test_regions_list(client: AsyncClient) -> None:
    """GET /api/meta/regions возвращает регионы с кодами и названиями."""
    resp = await client.get("/api/meta/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    codes = {item["code"] for item in data["items"]}
    # Москва и СПб присутствуют
    assert "45" in codes
    assert "40" in codes
    for item in data["items"]:
        assert "code" in item
        assert "name" in item


async def test_categories_no_auth_required(client: AsyncClient) -> None:
    """Справочники доступны без авторизации."""
    resp = await client.get("/api/meta/categories")
    assert resp.status_code == 200

    resp2 = await client.get("/api/meta/regions")
    assert resp2.status_code == 200
