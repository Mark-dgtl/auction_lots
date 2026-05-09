"""Интеграционные тесты :class:`parser.sources.torgi.TorgiSource`."""

from __future__ import annotations

import httpx
import pytest
import respx

from parser.base import ParseFilters
from parser.sources.torgi import TorgiSource


_API = "https://torgi.gov.ru/new/api/public/lotcards/search"


@pytest.mark.asyncio
async def test_fetch_lots_basic(torgi_search_response, empty_torgi_page) -> None:
    """Базовый обход одной страницы + пустая."""
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API)
        route.side_effect = [
            httpx.Response(200, json=torgi_search_response),
            httpx.Response(200, json=empty_torgi_page),
        ]
        async with httpx.AsyncClient() as client:
            source = TorgiSource(client=client)
            lots = [lot async for lot in source.fetch_lots()]

    # В фикстуре 3 лота
    assert len(lots) == 3
    lot = lots[0]
    assert lot.source == "torgi_gov"
    assert lot.source_lot_id
    assert lot.title
    assert str(lot.source_url).startswith("https://torgi.gov.ru/new/public/lots/lot/")
    assert lot.images, "ожидаем непустой список изображений"
    assert str(lot.images[0]).startswith("https://torgi.gov.ru/new/file-store/")
    # price берём из priceMinExact
    assert lot.price is not None


@pytest.mark.asyncio
async def test_limit(torgi_search_response) -> None:
    async with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith=_API).mock(
            return_value=httpx.Response(200, json=torgi_search_response)
        )
        async with httpx.AsyncClient() as client:
            source = TorgiSource(client=client)
            lots = [lot async for lot in source.fetch_lots(limit=2)]

    assert len(lots) == 2


@pytest.mark.asyncio
async def test_category_mapping(torgi_search_response, empty_torgi_page) -> None:
    """Коды категорий torgi маппятся на наши slug-и."""
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API)
        route.side_effect = [
            httpx.Response(200, json=torgi_search_response),
            httpx.Response(200, json=empty_torgi_page),
        ]
        async with httpx.AsyncClient() as client:
            source = TorgiSource(client=client)
            lots = [lot async for lot in source.fetch_lots()]

    # В реальной фикстуре есть code="100001" (Легковые автомобили) → vehicle
    # и "11" (Нежилые помещения) → real_estate.
    cats = {lot.category for lot in lots if lot.category}
    assert "vehicle" in cats or "real_estate" in cats or "land" in cats


@pytest.mark.asyncio
async def test_filters(empty_torgi_page) -> None:
    """Фильтры конвертируются в query-параметры API."""
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API).mock(
            return_value=httpx.Response(200, json=empty_torgi_page)
        )
        async with httpx.AsyncClient() as client:
            source = TorgiSource(client=client)
            filters = ParseFilters(
                query="автомобиль",
                category="vehicle",
                region="77",
                price_from=50000,
                price_to=1000000,
            )
            _ = [lot async for lot in source.fetch_lots(filters=filters, limit=5)]

    assert route.call_count == 1
    url = str(route.calls[0].request.url)
    assert "text=" in url
    assert "dynSubjRF=77" in url
    assert "priceMin=50000" in url
    assert "priceMax=1000000" in url
    # vehicle → catCode должен содержать хотя бы один из кодов автомобилей
    assert "catCode=" in url


@pytest.mark.asyncio
async def test_retry_on_5xx(torgi_search_response, empty_torgi_page) -> None:
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API)
        route.side_effect = [
            httpx.Response(502),
            httpx.Response(200, json=torgi_search_response),
            httpx.Response(200, json=empty_torgi_page),
        ]
        async with httpx.AsyncClient() as client:
            source = TorgiSource(client=client)
            lots = [lot async for lot in source.fetch_lots()]

    assert len(lots) == 3
    # 502 → retry → 200 для page=0; затем page=1 (пустой content) — выход.
    assert route.call_count == 3


@pytest.mark.asyncio
async def test_empty_lot_safe() -> None:
    """Отсутствующие поля не роняют парсер."""
    payload = {
        "content": [
            {
                "id": "empty_1",
                "lotName": None,
                "lotDescription": None,
                "priceMinExact": None,
                "priceStep": None,
                "subjectRFCode": None,
                "category": None,
                "lotImages": [],
                "createDate": None,
            }
        ],
        "totalElements": 1,
        "last": True,
        "size": 20,
        "number": 0,
        "empty": False,
    }
    async with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith=_API).mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with httpx.AsyncClient() as client:
            source = TorgiSource(client=client)
            lots = [lot async for lot in source.fetch_lots(limit=1)]

    assert len(lots) == 1
    lot = lots[0]
    assert lot.title  # заглушка сформирована
    assert lot.price is None
    assert lot.images == []
    assert lot.region is None
