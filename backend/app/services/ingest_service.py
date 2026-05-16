"""Сервис ingestion лотов от парсера в базу данных.

Принимает ParsedLot от источников, нормализует регион/категорию
и выполняет upsert в таблицу lots.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from parser.base import CATEGORY_SLUGS, BaseSource, ParsedLot

from app.models.lot import Lot
from app.models.parser_run import ParserRun
from app.models.region import Region
from app.services.media_prefetch import schedule_prefetch_urls

logger = logging.getLogger("app.ingest")

IngestResult = Literal["new", "updated", "skipped"]


@dataclass
class ParserRunReport:
    """Отчёт об одном запуске источника парсера.

    Attributes:
        source: Идентификатор источника.
        lots_seen: Всего обработано лотов.
        lots_new: Новых лотов добавлено.
        lots_updated: Лотов обновлено.
        lots_skipped: Лотов без изменений.
        status: Статус завершения ('ok' или 'error').
        error: Текст ошибки, если status == 'error'.
    """

    source: str
    lots_seen: int = 0
    lots_new: int = 0
    lots_updated: int = 0
    lots_skipped: int = 0
    pages_fetched: int = 0
    expected_total_elements: int | None = None
    yielded_total: int = 0
    skipped_invalid: int = 0
    full_scan_completed: bool = False
    status: str = "ok"
    error: str | None = None


class IngestService:
    """Сервис ingestion: приём лотов от парсера и сохранение в БД.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def ingest_lot(self, lot: ParsedLot) -> IngestResult:
        """Upsert одного лота по ключу (source, source_lot_id).

        Нормализует регион и категорию. Если лот новый — INSERT.
        Если существует и изменились ключевые поля — UPDATE. Иначе — SKIPPED.

        Args:
            lot: Нормализованный лот от парсера.

        Returns:
            'new', 'updated' или 'skipped'.
        """
        existing = await self._db.scalar(
            select(Lot).where(
                Lot.source == lot.source,
                Lot.source_lot_id == lot.source_lot_id,
            )
        )

        region_code = await self._resolve_region(lot.region)
        category = lot.category if lot.category in CATEGORY_SLUGS else None
        images = [str(img) for img in lot.images]

        if existing is None:
            new_lot = Lot(
                source=lot.source,
                source_lot_id=lot.source_lot_id,
                title=lot.title,
                description=lot.description,
                category=category,
                region_code=region_code,
                price=lot.price,
                price_step=lot.price_step,
                source_url=str(lot.source_url),
                auction_date=lot.auction_date,
                published_at=lot.published_at,
                status=lot.status,
                images=images,
                raw=lot.raw,
            )
            self._db.add(new_lot)
            await self._db.commit()
            logger.info("Добавлен новый лот: %s/%s", lot.source, lot.source_lot_id)
            if images:
                schedule_prefetch_urls(images)
            return "new"

        existing_images = existing.images or []
        changed = (
            existing.title != lot.title
            or existing.description != lot.description
            or existing.price != lot.price
            or existing.price_step != lot.price_step
            or existing.auction_date != lot.auction_date
            or existing.status != lot.status
            or existing_images != images
        )

        if changed:
            existing.title = lot.title
            existing.description = lot.description
            existing.category = category
            existing.region_code = region_code
            existing.price = lot.price
            existing.price_step = lot.price_step
            existing.source_url = str(lot.source_url)
            existing.auction_date = lot.auction_date
            existing.published_at = lot.published_at
            existing.status = lot.status
            existing.images = images
            existing.raw = lot.raw
            existing.updated_at = datetime.now(timezone.utc)
            await self._db.commit()
            logger.info("Обновлён лот: %s/%s", lot.source, lot.source_lot_id)
            if images:
                schedule_prefetch_urls(images)
            return "updated"

        logger.debug("Лот без изменений: %s/%s", lot.source, lot.source_lot_id)
        return "skipped"

    async def _resolve_region(self, region: str | None) -> str | None:
        """Нормализует код или название региона в ОКАТО-код из справочника.

        - Числовая строка → поиск по prefix кода (torgi_gov — 2-значный subjectRFCode).
        - Строка с буквами → регистронезависимый поиск по подстроке в regions.name.
        - Если не найдено → None (fallback).

        Args:
            region: Значение региона от парсера.

        Returns:
            ОКАТО-код или None.
        """
        if not region:
            return None

        region = region.strip()

        if region.isdigit():
            result = await self._db.scalar(
                select(Region.code)
                .where(Region.code.like(region + "%"))
                .order_by(func.length(Region.code))
                .limit(1)
            )
            return result

        if self._is_postgresql():
            # PostgreSQL: ILIKE — полностью регистронезависимо
            result = await self._db.scalar(
                select(Region.code)
                .where(Region.name.ilike(f"%{region}%"))
                .limit(1)
            )
        else:
            # SQLite: lower() не работает с кириллицей, используем LIKE напрямую
            result = await self._db.scalar(
                select(Region.code)
                .where(Region.name.like(f"%{region}%"))
                .limit(1)
            )
        return result

    def _is_postgresql(self) -> bool:
        """Определяет, используется ли PostgreSQL в текущей сессии."""
        try:
            return self._db.sync_session.get_bind().dialect.name == "postgresql"
        except Exception:
            return False

    async def run_source(
        self,
        source: BaseSource,
        since: datetime | None = None,
        limit: int | None = None,
        *,
        triggered_by: str = "schedule",
        triggered_by_user_id: int | None = None,
    ) -> ParserRunReport:
        """Запускает источник: перебирает все лоты и вызывает ingest_lot для каждого.

        Создаёт запись в parser_runs до старта и обновляет её по завершении.
        Ошибки отдельных лотов логируются WARNING и не прерывают обработку.

        Args:
            source: Экземпляр источника (EfrsbSource, TorgiSource и т.д.).
            since: Взять лоты не ранее этой даты (если источник поддерживает).
            limit: Максимальное число лотов (None — без ограничений).

        Returns:
            Отчёт о запуске с количеством обработанных, новых, обновлённых лотов.
        """
        run = ParserRun(
            source=source.name,
            status="running",
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
        )
        self._db.add(run)
        await self._db.commit()
        await self._db.refresh(run)

        report = ParserRunReport(source=source.name)

        try:
            async for lot in source.fetch_lots(since=since, limit=limit):
                report.lots_seen += 1
                try:
                    result = await self.ingest_lot(lot)
                    if result == "new":
                        report.lots_new += 1
                    elif result == "updated":
                        report.lots_updated += 1
                    else:
                        report.lots_skipped += 1
                except Exception as exc:
                    logger.warning(
                        "Ошибка при ingestion лота %s/%s: %s",
                        lot.source,
                        lot.source_lot_id,
                        exc,
                    )

            telemetry = source.get_run_telemetry() if hasattr(source, "get_run_telemetry") else {}
            report.pages_fetched = int(telemetry.get("pages_fetched") or 0)
            report.expected_total_elements = telemetry.get("expected_total_elements")
            report.yielded_total = int(telemetry.get("yielded_total") or report.lots_seen)
            report.skipped_invalid = int(telemetry.get("skipped_invalid") or 0)
            report.full_scan_completed = bool(telemetry.get("full_scan_completed"))

            run.finished_at = datetime.now(timezone.utc)
            run.status = "ok"
            run.lots_seen = report.lots_seen
            run.lots_new = report.lots_new
            run.lots_updated = report.lots_updated
            run.pages_fetched = report.pages_fetched
            run.expected_total_elements = report.expected_total_elements
            run.yielded_total = report.yielded_total
            run.skipped_invalid = report.skipped_invalid
            run.full_scan_completed = report.full_scan_completed
            await self._db.commit()

            logger.info(
                "Источник %s завершён: просмотрено=%d, новых=%d, обновлено=%d",
                source.name,
                report.lots_seen,
                report.lots_new,
                report.lots_updated,
            )
        except Exception as exc:
            report.status = "error"
            report.error = str(exc)
            telemetry = source.get_run_telemetry() if hasattr(source, "get_run_telemetry") else {}
            report.pages_fetched = int(telemetry.get("pages_fetched") or 0)
            report.expected_total_elements = telemetry.get("expected_total_elements")
            report.yielded_total = int(telemetry.get("yielded_total") or report.lots_seen)
            report.skipped_invalid = int(telemetry.get("skipped_invalid") or 0)
            report.full_scan_completed = bool(telemetry.get("full_scan_completed"))
            run.finished_at = datetime.now(timezone.utc)
            run.status = "error"
            run.error = str(exc)
            run.pages_fetched = report.pages_fetched
            run.expected_total_elements = report.expected_total_elements
            run.yielded_total = report.yielded_total
            run.skipped_invalid = report.skipped_invalid
            run.full_scan_completed = report.full_scan_completed
            await self._db.commit()
            logger.error(
                "Критическая ошибка источника %s: %s", source.name, exc
            )

        return report
