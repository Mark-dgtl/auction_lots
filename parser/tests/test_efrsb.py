"""Интеграционные тесты :class:`parser.sources.efrsb.EfrsbSource`."""

from __future__ import annotations

import httpx
import pytest
import respx

from parser.base import ParseFilters
from parser.sources.efrsb import EfrsbSource


_API = "https://bankrot.fedresurs.ru/backend/trademsg/search"


@pytest.mark.asyncio
async def test_fetch_lots_basic(efrsb_list_page, empty_efrsb_page) -> None:
    """Проверяем, что по одной полной странице + пустой мы возвращаем все лоты."""
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API)
        route.side_effect = [
            httpx.Response(200, json=efrsb_list_page),
            httpx.Response(200, json=empty_efrsb_page),
        ]

        async with httpx.AsyncClient() as client:
            source = EfrsbSource(client=client)
            lots = [lot async for lot in source.fetch_lots()]

    # В фикстуре 3 сообщения: 2+1+1 лотов = 4
    assert len(lots) == 4
    first = lots[0]
    assert first.source == "efrsb"
    assert first.source_lot_id.startswith("d3f1a8b0-1111-4c22-9a01-aaaaaaaa0001")
    assert first.title.startswith("Квартира 52.3")
    assert first.category == "real_estate"
    assert first.price is not None and float(first.price) == 3500000.0
    assert first.price_step is not None and float(first.price_step) == 175000.0
    assert str(first.source_url).startswith("https://bankrot.fedresurs.ru/")
    assert first.published_at is not None
    assert first.published_at.utcoffset().total_seconds() == 0
    # картинки должны быть абсолютными HttpUrl
    assert [str(u) for u in first.images] == [
        "https://example-cdn.example/efrsb/1.jpg",
        "https://example-cdn.example/efrsb/2.jpg",
    ]


@pytest.mark.asyncio
async def test_fetch_lots_respects_limit(efrsb_list_page) -> None:
    """limit обрывает генератор не добирая следующую страницу."""
    async with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith=_API).mock(
            return_value=httpx.Response(200, json=efrsb_list_page)
        )
        async with httpx.AsyncClient() as client:
            source = EfrsbSource(client=client)
            lots = [lot async for lot in source.fetch_lots(limit=2)]

    assert len(lots) == 2


@pytest.mark.asyncio
async def test_categories_inferred(efrsb_list_page, empty_efrsb_page) -> None:
    """Категории выводятся из текста лота через rule-based."""
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API)
        route.side_effect = [
            httpx.Response(200, json=efrsb_list_page),
            httpx.Response(200, json=empty_efrsb_page),
        ]
        async with httpx.AsyncClient() as client:
            source = EfrsbSource(client=client)
            lots = [lot async for lot in source.fetch_lots()]

    cats = {lot.source_lot_id: lot.category for lot in lots}
    # По первому сообщению: квартира + автомобиль
    assert any(v == "real_estate" for v in cats.values())
    assert any(v == "vehicle" for v in cats.values())
    # Земельный участок во втором сообщении
    assert any(v == "land" for v in cats.values())
    # Станок в третьем
    assert any(v == "equipment" for v in cats.values())


@pytest.mark.asyncio
async def test_filters_passed_in_query(efrsb_list_page, empty_efrsb_page) -> None:
    """Фильтры должны попадать в query-параметры запроса."""
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API)
        route.side_effect = [
            httpx.Response(200, json=efrsb_list_page),
            httpx.Response(200, json=empty_efrsb_page),
        ]
        async with httpx.AsyncClient() as client:
            source = EfrsbSource(client=client)
            filters = ParseFilters(query="квартира", region="45", price_from=100, price_to=5000000)
            lots = [lot async for lot in source.fetch_lots(filters=filters, limit=1)]

    assert lots  # хотя бы один
    called_url = str(route.calls[0].request.url)
    assert "searchString=%D0%BA%D0%B2%D0%B0%D1%80%D1%82%D0%B8%D1%80%D0%B0" in called_url
    assert "region=45" in called_url
    assert "priceFrom=100" in called_url
    assert "priceTo=5000000" in called_url


@pytest.mark.asyncio
async def test_retries_on_5xx(efrsb_list_page) -> None:
    """5xx приводит к ретраям (tenacity, 3 попытки)."""
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=_API)
        route.side_effect = [
            httpx.Response(503, text="gateway busy"),
            httpx.Response(503, text="still busy"),
            httpx.Response(200, json=efrsb_list_page),
        ]
        async with httpx.AsyncClient() as client:
            source = EfrsbSource(client=client)
            lots = [lot async for lot in source.fetch_lots()]

    assert len(lots) == 4
    # 2 неудачные + 1 успешная попытка на странице 0, далее len<page_size → выход.
    assert route.call_count == 3


@pytest.mark.asyncio
async def test_empty_fields_do_not_crash() -> None:
    """Пустые/отсутствующие поля в лоте не валят генератор."""
    payload = {
        "pageData": [
            {
                "guid": "empty-guid-0000",
                "publishDate": None,
                "debtor": {},
                "trade": {
                    "lots": [
                        {"lotNumber": 1, "lotName": "", "description": "", "priceStart": None}
                    ]
                },
            }
        ],
        "found": 1,
    }
    async with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith=_API).mock(return_value=httpx.Response(200, json=payload))
        async with httpx.AsyncClient() as client:
            source = EfrsbSource(client=client)
            lots = [lot async for lot in source.fetch_lots(limit=1)]

    assert len(lots) == 1
    assert lots[0].title  # заполнился заглушкой
    assert lots[0].price is None
