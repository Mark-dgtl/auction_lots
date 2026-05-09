"""Схемы лотов торгов."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LotShort(BaseModel):
    """Краткое представление лота для списков.

    Цены передаются строкой для сохранения точности Decimal.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    title: str
    category: Optional[str]
    region_code: Optional[str]
    region_name: Optional[str]
    price: Optional[str]  # Decimal → str, согласно §4 контракта
    auction_date: Optional[datetime]
    thumbnail: Optional[str]
    is_favorite: bool = False


class LotDetail(LotShort):
    """Полное представление лота.

    Расширяет LotShort дополнительными полями согласно §2.3 контракта.
    """

    description: Optional[str]
    price_step: Optional[str]  # Decimal → str
    source_url: str
    images: list[str]
    status: Optional[str]
    published_at: Optional[datetime]
    updated_at: datetime


class LotListResponse(BaseModel):
    """Ответ со списком лотов и пагинацией."""

    items: list[LotShort]
    total: int
    page: int
    page_size: int
