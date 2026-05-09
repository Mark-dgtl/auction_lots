"""Эндпоинты /api/admin/lots/* — управление лотами."""

import logging
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import NotFound
from app.db.session import get_db
from app.models.lot import Lot
from app.models.user import User
from app.services.audit_service import get_audit_writer

router = APIRouter()
logger = logging.getLogger("app.admin.lots")


def _lot_short(lot: Lot) -> dict:
    return {
        "id": lot.id,
        "source": lot.source,
        "title": lot.title,
        "category": lot.category,
        "region_code": lot.region_code,
        "price": str(lot.price) if lot.price is not None else None,
        "auction_date": lot.auction_date.strftime("%Y-%m-%dT%H:%M:%SZ") if lot.auction_date else None,
        "thumbnail": lot.images[0] if lot.images else None,
        "status": lot.status,
    }


@router.get("/lots")
async def list_lots(
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает список лотов для администратора."""
    stmt = select(Lot)
    if source:
        stmt = stmt.where(Lot.source == source)
    if status:
        stmt = stmt.where(Lot.status == status)
    if q:
        stmt = stmt.where(Lot.title.ilike(f"%{q}%"))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    lots = await db.scalars(
        stmt.order_by(Lot.first_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [_lot_short(l) for l in lots.all()],
        "total": total,
    }


@router.delete("/lots/{lot_id}", status_code=204)
async def delete_lot(
    lot_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> None:
    """Удаляет лот."""
    lot = await db.scalar(select(Lot).where(Lot.id == lot_id))
    if not lot:
        raise NotFound("Лот не найден")

    await audit("LOT_DELETE", target_type="lot", target_id=str(lot_id))
    await db.delete(lot)
    await db.commit()
    logger.info("Администратор удалил лот id=%d", lot_id)


@router.post("/lots/{lot_id}/refresh")
async def refresh_lot(
    lot_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Принудительно обновляет лот из источника (заглушка, re-fetch не реализован)."""
    lot = await db.scalar(select(Lot).where(Lot.id == lot_id))
    if not lot:
        raise NotFound("Лот не найден")

    logger.info("Администратор запросил обновление лота id=%d", lot_id)
    # Возвращаем текущий LotDetail (в рамках M4 re-fetch у источника не реализован)
    return {
        "id": lot.id,
        "source": lot.source,
        "title": lot.title,
        "description": lot.description,
        "category": lot.category,
        "region_code": lot.region_code,
        "price": str(lot.price) if lot.price is not None else None,
        "price_step": str(lot.price_step) if lot.price_step is not None else None,
        "source_url": lot.source_url,
        "auction_date": lot.auction_date.strftime("%Y-%m-%dT%H:%M:%SZ") if lot.auction_date else None,
        "published_at": lot.published_at.strftime("%Y-%m-%dT%H:%M:%SZ") if lot.published_at else None,
        "status": lot.status,
        "images": lot.images,
        "updated_at": lot.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") if lot.updated_at else None,
    }
