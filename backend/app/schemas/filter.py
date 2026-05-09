"""Схемы сохранённых фильтров поиска."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FilterParams(BaseModel):
    """Параметры поискового фильтра.

    Используется как внутри SavedFilter, так и в query-параметрах поиска.
    """

    query: Optional[str] = None
    category: Optional[str] = None
    region: Optional[str] = None
    price_from: Optional[Decimal] = None
    price_to: Optional[Decimal] = None


class SavedFilterCreate(BaseModel):
    """Тело запроса создания фильтра."""

    name: str
    filter: FilterParams
    notify_enabled: bool = False


class SavedFilterUpdate(BaseModel):
    """Тело запроса обновления фильтра. Все поля — опциональны."""

    name: Optional[str] = None
    filter: Optional[FilterParams] = None
    notify_enabled: Optional[bool] = None


class SavedFilterListResponse(BaseModel):
    """Ответ со списком сохранённых фильтров."""

    items: list["SavedFilterResponse"]


class SavedFilterResponse(BaseModel):
    """Ответ с данными сохранённого фильтра."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    filter: FilterParams
    notify_enabled: bool
    created_at: datetime
