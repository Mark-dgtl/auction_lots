"""Роутер сохранённых поисковых фильтров."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.filter import (
    SavedFilterCreate,
    SavedFilterListResponse,
    SavedFilterResponse,
    SavedFilterUpdate,
)
from app.services.filter_service import FilterService

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("", response_model=SavedFilterListResponse)
async def list_filters(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedFilterListResponse:
    """Список всех сохранённых фильтров текущего пользователя."""
    svc = FilterService(db)
    filters = await svc.list_filters(user.id)
    return SavedFilterListResponse(items=filters)


@router.post("", response_model=SavedFilterResponse, status_code=201)
async def create_filter(
    body: SavedFilterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedFilterResponse:
    """Создаёт новый сохранённый фильтр.

    Args:
        body: Название, параметры фильтра и флаг уведомлений.
    """
    svc = FilterService(db)
    # mode='json' конвертирует Decimal в строки для совместимости с JSON
    sf = await svc.create_filter(
        user_id=user.id,
        name=body.name,
        filter_data=body.filter.model_dump(mode="json"),
        notify_enabled=body.notify_enabled,
    )
    return sf


@router.put("/{filter_id}", response_model=SavedFilterResponse)
async def update_filter(
    filter_id: int,
    body: SavedFilterUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedFilterResponse:
    """Обновляет сохранённый фильтр (partial update).

    Args:
        filter_id: ID фильтра.
        body: Поля для обновления (все опциональны).
    """
    svc = FilterService(db)
    data: dict = {}
    if "name" in body.model_fields_set and body.name is not None:
        data["name"] = body.name
    if "filter" in body.model_fields_set and body.filter is not None:
        data["filter"] = body.filter.model_dump(mode="json")
    if "notify_enabled" in body.model_fields_set:
        data["notify_enabled"] = body.notify_enabled
    return await svc.update_filter(user.id, filter_id, data)


@router.delete("/{filter_id}", status_code=204)
async def delete_filter(
    filter_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Удаляет сохранённый фильтр.

    Args:
        filter_id: ID фильтра.
    """
    svc = FilterService(db)
    await svc.delete_filter(user.id, filter_id)
