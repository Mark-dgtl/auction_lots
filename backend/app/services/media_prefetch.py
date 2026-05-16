"""Фоновая предзагрузка изображений лотов в локальный кэш."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.lot import Lot
from app.services.media_proxy import prefetch_image_url

logger = logging.getLogger("app.media.prefetch")

_warm_lock = asyncio.Lock()
_warm_running = False


def _unique_urls(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in urls:
        url = (raw or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


async def prefetch_urls(urls: list[str]) -> tuple[int, int]:
    """Скачивает URL в локальный кэш. Возвращает (успех, ошибка)."""
    unique = _unique_urls(urls)
    if not unique:
        return 0, 0

    sem = asyncio.Semaphore(max(1, settings.MEDIA_PREFETCH_CONCURRENCY))
    ok = 0
    fail = 0

    async def _one(url: str) -> None:
        nonlocal ok, fail
        async with sem:
            if await prefetch_image_url(url):
                ok += 1
            else:
                fail += 1

    await asyncio.gather(*(_one(u) for u in unique))
    return ok, fail


def schedule_prefetch_urls(urls: list[str]) -> None:
    """Ставит предзагрузку в фон (не блокирует ingest/API)."""
    unique = _unique_urls(urls)
    if not unique:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _run() -> None:
        ok, fail = await prefetch_urls(unique)
        if ok or fail:
            logger.debug(
                "Предзагрузка %d URL: ok=%d, fail=%d", len(unique), ok, fail
            )

    loop.create_task(_run(), name="media_prefetch_batch")


async def warm_all_lot_images() -> None:
    """Проходит по всем лотам в БД и кэширует изображения на диск."""
    global _warm_running

    async with _warm_lock:
        if _warm_running:
            logger.info("Прогрев кэша изображений уже выполняется — пропуск")
            return
        _warm_running = True

    total_ok = 0
    total_fail = 0
    lots_done = 0
    batch_size = settings.MEDIA_WARM_BATCH_SIZE
    offset = 0

    logger.info(
        "Старт прогрева кэша изображений (каталог: %s)", settings.resolved_media_cache_dir()
    )

    try:
        while True:
            async with async_session_maker() as session:
                rows = (
                    await session.execute(
                        select(Lot.images)
                        .order_by(Lot.id)
                        .offset(offset)
                        .limit(batch_size)
                    )
                ).all()

            if not rows:
                break

            batch_urls: list[str] = []
            for (images,) in rows:
                if images:
                    batch_urls.extend(str(u) for u in images)

            ok, fail = await prefetch_urls(batch_urls)
            total_ok += ok
            total_fail += fail
            lots_done += len(rows)
            offset += batch_size

            logger.info(
                "Прогрев кэша: обработано лотов %d, URL ok=%d fail=%d",
                lots_done,
                total_ok,
                total_fail,
            )
    finally:
        async with _warm_lock:
            _warm_running = False

    logger.info(
        "Прогрев кэша завершён: лотов %d, URL ok=%d, fail=%d",
        lots_done,
        total_ok,
        total_fail,
    )


def schedule_warm_all_lots(*, delay_seconds: float = 15.0) -> None:
    """Запускает полный прогрев через delay_seconds после старта приложения."""
    if not settings.MEDIA_WARM_ON_STARTUP:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _delayed() -> None:
        await asyncio.sleep(delay_seconds)
        try:
            await warm_all_lot_images()
        except Exception as exc:
            logger.error("Ошибка прогрева кэша изображений: %s", exc)

    loop.create_task(_delayed(), name="media_warm_all_lots")
