"""Роутер лотов: поиск и детальная карточка."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.models.user import User
from app.schemas.lot import LotDetail, LotListResponse
from app.services.lot_service import LotService

router = APIRouter(prefix="/lots", tags=["lots"])
logger = logging.getLogger("app.lots")


@router.get("", response_model=LotListResponse)
async def search_lots(
    query: Optional[str] = Query(None, description="Поисковый запрос"),
    category: Optional[str] = Query(None, description="Slug категории"),
    region: Optional[str] = Query(None, description="Код ОКАТО региона"),
    price_from: Optional[Decimal] = Query(None, description="Цена от (руб.)"),
    price_to: Optional[Decimal] = Query(None, description="Цена до (руб.)"),
    date_from: Optional[datetime] = Query(None, description="Дата торгов от"),
    date_to: Optional[datetime] = Query(None, description="Дата торгов до"),
    sort: str = Query(
        "date_desc",
        pattern="^(date_desc|price_asc|price_desc)$",
        description="Сортировка",
    ),
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> LotListResponse:
    """Список лотов с полнотекстовым поиском и фильтрацией.

    Доступен без авторизации. При наличии Bearer-токена заполняет is_favorite.
    """
    svc = LotService(db)
    items, total = await svc.search(
        query=query,
        category=category,
        region=region,
        price_from=price_from,
        price_to=price_to,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
        user_id=user.id if user else None,
    )
    return LotListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{lot_id}", response_model=LotDetail)
async def get_lot(
    lot_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> LotDetail:
    """Детальная карточка лота.

    Args:
        lot_id: Первичный ключ лота.
    """
    svc = LotService(db)
    return await svc.get_by_id(lot_id, user.id if user else None)
