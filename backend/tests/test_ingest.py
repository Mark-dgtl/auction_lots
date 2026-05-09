"""Тесты IngestService: upsert лотов, нормализация региона/категории."""

from datetime import datetime
from decimal import Decimal
from typing import AsyncIterator

import pytest
from pydantic import HttpUrl
from sqlalchemy import select

from app.models.lot import Lot
from app.services.ingest_service import IngestService
from parser.base import BaseSource, ParseFilters, ParsedLot


def _make_lot(**kwargs) -> ParsedLot:
    """Создаёт тестовый ParsedLot с дефолтными значениями."""
    defaults = dict(
        source="efrsb",
        source_lot_id="test-001",
        title="Тестовый лот",
        source_url=HttpUrl("https://efrsb.ru/lot/1"),
        images=[],
        raw={},
    )
    defaults.update(kwargs)
    return ParsedLot(**defaults)


@pytest.mark.asyncio
async def test_ingest_new_lot(db_session):
    """Новый лот должен быть добавлен в БД со статусом 'new'."""
    svc = IngestService(db_session)
    lot = _make_lot(title="Квартира в центре", price=Decimal("5000000"))

    result = await svc.ingest_lot(lot)

    assert result == "new"
    db_lot = await db_session.scalar(
        select(Lot).where(Lot.source == "efrsb", Lot.source_lot_id == "test-001")
    )
    assert db_lot is not None
    assert db_lot.title == "Квартира в центре"
    assert db_lot.price == Decimal("5000000")


@pytest.mark.asyncio
async def test_ingest_update_lot(db_session):
    """Существующий лот с изменённой ценой должен обновиться, статус 'updated'."""
    svc = IngestService(db_session)
    lot = _make_lot(price=Decimal("1000000"))
    await svc.ingest_lot(lot)

    lot_updated = _make_lot(price=Decimal("900000"))
    result = await svc.ingest_lot(lot_updated)

    assert result == "updated"
    db_lot = await db_session.scalar(select(Lot).where(Lot.source_lot_id == "test-001"))
    assert db_lot.price == Decimal("900000")


@pytest.mark.asyncio
async def test_ingest_skip_unchanged(db_session):
    """Лот без изменений не должен обновляться, статус 'skipped'."""
    svc = IngestService(db_session)
    lot = _make_lot(price=Decimal("1500000"))
    await svc.ingest_lot(lot)

    result = await svc.ingest_lot(lot)
    assert result == "skipped"


@pytest.mark.asyncio
async def test_ingest_region_okato_match(db_session):
    """Числовой код '45' должен совпасть с регионом '45' в справочнике."""
    from app.models.region import Region

    db_session.add(Region(code="45", name="Москва"))
    await db_session.commit()

    svc = IngestService(db_session)
    lot = _make_lot(region="45")
    await svc.ingest_lot(lot)

    db_lot = await db_session.scalar(select(Lot).where(Lot.source_lot_id == "test-001"))
    assert db_lot.region_code == "45"


@pytest.mark.asyncio
async def test_ingest_region_name_match(db_session):
    """Название 'Москва' должно совпасть с регионом с кодом '45'."""
    from app.models.region import Region

    db_session.add(Region(code="45", name="Москва"))
    await db_session.commit()

    svc = IngestService(db_session)
    lot = _make_lot(region="Москва")
    await svc.ingest_lot(lot)

    db_lot = await db_session.scalar(select(Lot).where(Lot.source_lot_id == "test-001"))
    assert db_lot.region_code == "45"


@pytest.mark.asyncio
async def test_ingest_unknown_category(db_session):
    """Неизвестная категория должна стать NULL, не 'other'."""
    svc = IngestService(db_session)
    lot = _make_lot(category="unknown_xyz")
    await svc.ingest_lot(lot)

    db_lot = await db_session.scalar(select(Lot).where(Lot.source_lot_id == "test-001"))
    assert db_lot.category is None


@pytest.mark.asyncio
async def test_ingest_known_category_preserved(db_session):
    """Известная категория должна сохраниться как есть."""
    svc = IngestService(db_session)
    lot = _make_lot(category="real_estate")
    await svc.ingest_lot(lot)

    db_lot = await db_session.scalar(select(Lot).where(Lot.source_lot_id == "test-001"))
    assert db_lot.category == "real_estate"


@pytest.mark.asyncio
async def test_ingest_none_category_stays_null(db_session):
    """category=None должна сохраниться как NULL, не заменяться на 'other'."""
    svc = IngestService(db_session)
    lot = _make_lot(category=None)
    await svc.ingest_lot(lot)

    db_lot = await db_session.scalar(select(Lot).where(Lot.source_lot_id == "test-001"))
    assert db_lot.category is None


class _FakeSource(BaseSource):
    name = "fake_source"

    async def fetch_lots(
        self,
        since: datetime | None = None,
        filters: ParseFilters | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[ParsedLot]:
        yield _make_lot(source=self.name, source_lot_id="fake-001")

    def get_run_telemetry(self) -> dict:
        return {
            "pages_fetched": 12,
            "expected_total_elements": 345,
            "yielded_total": 321,
            "skipped_invalid": 4,
            "full_scan_completed": True,
        }


@pytest.mark.asyncio
async def test_run_source_persists_telemetry(db_session):
    svc = IngestService(db_session)
    report = await svc.run_source(_FakeSource())

    assert report.pages_fetched == 12
    assert report.expected_total_elements == 345
    assert report.yielded_total == 321
    assert report.skipped_invalid == 4
    assert report.full_scan_completed is True
