"""Тесты лотов: поиск, фильтрация, пагинация."""

import pytest
from httpx import AsyncClient


async def test_lots_list_empty(client: AsyncClient) -> None:
    """Пустой список лотов при отсутствии данных."""
    resp = await client.get("/api/lots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


async def test_lots_list(client: AsyncClient, sample_lots: list[int]) -> None:
    """Список лотов возвращает созданные лоты."""
    resp = await client.get("/api/lots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


async def test_lots_pagination(client: AsyncClient, sample_lots: list[int]) -> None:
    """Пагинация ограничивает количество лотов в ответе."""
    resp = await client.get("/api/lots?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 2

    resp2 = await client.get("/api/lots?page=2&page_size=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["items"]) == 1


async def test_lots_filter_by_category(
    client: AsyncClient, sample_lots: list[int]
) -> None:
    """Фильтрация по категории возвращает только лоты этой категории."""
    resp = await client.get("/api/lots?category=real_estate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "real_estate"


async def test_lots_filter_by_region(
    client: AsyncClient, sample_lots: list[int]
) -> None:
    """Фильтрация по коду региона работает корректно."""
    resp = await client.get("/api/lots?region=45")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["region_code"] == "45"


async def test_lots_filter_by_price(
    client: AsyncClient, sample_lots: list[int]
) -> None:
    """Фильтрация по диапазону цен возвращает лоты в диапазоне."""
    resp = await client.get("/api/lots?price_from=400000&price_to=1500000")
    assert resp.status_code == 200
    data = resp.json()
    # Должны быть лоты с ценой 500000 и 1200000
    assert data["total"] == 2
    prices = [float(item["price"]) for item in data["items"]]
    assert all(400000 <= p <= 1500000 for p in prices)


async def test_lots_invalid_page_size(client: AsyncClient) -> None:
    """Размер страницы больше 100 возвращает 422."""
    resp = await client.get("/api/lots?page_size=200")
    assert resp.status_code == 422


async def test_lot_detail(
    client: AsyncClient, sample_lots: list[int]
) -> None:
    """Детальная карточка лота возвращает полные данные."""
    lot_id = sample_lots[0]
    resp = await client.get(f"/api/lots/{lot_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == lot_id
    assert "source_url" in data
    assert "images" in data
    assert "updated_at" in data
    assert data["is_favorite"] is False


async def test_lot_not_found(client: AsyncClient) -> None:
    """Несуществующий лот возвращает 404 NOT_FOUND."""
    resp = await client.get("/api/lots/99999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_lot_is_favorite_for_auth_user(
    client: AsyncClient,
    auth_headers: dict,
    sample_lots: list[int],
) -> None:
    """is_favorite=true для авторизованного пользователя, добавившего лот в избранное."""
    lot_id = sample_lots[0]
    await client.post(f"/api/favorites/{lot_id}", headers=auth_headers)

    resp = await client.get("/api/lots", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    fav_items = [i for i in items if i["id"] == lot_id]
    assert len(fav_items) == 1
    assert fav_items[0]["is_favorite"] is True


async def test_lots_sort_random_vehicle_first_unfiltered(
    client: AsyncClient, sample_lots: list[int]
) -> None:
    """Без фильтров sort=random отдаёт транспорт раньше остальных категорий."""
    resp = await client.get(
        "/api/lots?sort=random&shuffle_seed=vehicleboost&page_size=3"
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 3
    vehicle_idx = next(
        (i for i, it in enumerate(items) if it["category"] == "vehicle"),
        None,
    )
    assert vehicle_idx is not None
    for i, it in enumerate(items):
        if it["category"] != "vehicle":
            assert i > vehicle_idx


async def test_lots_sort_random_stable(
    client: AsyncClient, sample_lots: list[int]
) -> None:
    """sort=random с одним shuffle_seed даёт одинаковый порядок на разных страницах."""
    resp = await client.get(
        "/api/lots?sort=random&shuffle_seed=testseed&page=1&page_size=2"
    )
    assert resp.status_code == 200
    ids_p1 = [i["id"] for i in resp.json()["items"]]

    resp2 = await client.get(
        "/api/lots?sort=random&shuffle_seed=testseed&page=1&page_size=2"
    )
    assert [i["id"] for i in resp2.json()["items"]] == ids_p1

    resp3 = await client.get(
        "/api/lots?sort=random&shuffle_seed=other&page=1&page_size=2"
    )
    assert resp3.status_code == 200
    assert len(resp3.json()["items"]) >= 1


async def test_lots_search_by_query(
    client: AsyncClient, sample_lots: list[int]
) -> None:
    """Поиск по строке query через LIKE (SQLite) находит лот по ASCII-подстроке.

    SQLite lower() работает только для ASCII, поэтому ищем 'BMW' — ASCII-слово
    из заголовка 'Автомобиль BMW X5'.
    """
    resp = await client.get("/api/lots?query=BMW")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    titles = [i["title"] for i in data["items"]]
    assert any("BMW" in t for t in titles)
