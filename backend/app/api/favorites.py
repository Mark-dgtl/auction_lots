"""Роутер избранного."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.favorite import FavoriteListResponse
from app.services.favorite_service import FavoriteService

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=FavoriteListResponse)
async def list_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteListResponse:
    """Список избранных лотов текущего пользователя."""
    svc = FavoriteService(db)
    items, total = await svc.list_favorites(user.id)
    return FavoriteListResponse(items=items, total=total)


@router.post("/{lot_id}", status_code=204)
async def add_favorite(
    lot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Добавляет лот в избранное. Идемпотентен.

    Args:
        lot_id: ID лота.
    """
    svc = FavoriteService(db)
    await svc.add(user.id, lot_id)


@router.delete("/{lot_id}", status_code=204)
async def remove_favorite(
    lot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Удаляет лот из избранного.

    Args:
        lot_id: ID лота.
    """
    svc = FavoriteService(db)
    await svc.remove(user.id, lot_id)
