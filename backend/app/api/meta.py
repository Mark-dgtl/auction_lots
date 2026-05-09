"""Роутер метаданных: справочники категорий и регионов."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.category import Category
from app.models.region import Region
from app.schemas.meta import CategoryListResponse, RegionListResponse

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> CategoryListResponse:
    """Справочник категорий лотов."""
    cats = await db.scalars(select(Category).order_by(Category.name))
    return CategoryListResponse(items=list(cats.all()))


@router.get("/regions", response_model=RegionListResponse)
async def list_regions(
    db: AsyncSession = Depends(get_db),
) -> RegionListResponse:
    """Справочник регионов РФ (ОКАТО)."""
    regs = await db.scalars(select(Region).order_by(Region.name))
    return RegionListResponse(items=list(regs.all()))
