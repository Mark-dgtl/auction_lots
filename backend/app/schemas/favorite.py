"""Схемы избранного."""

from pydantic import BaseModel

from app.schemas.lot import LotShort


class FavoriteListResponse(BaseModel):
    """Ответ со списком избранных лотов пользователя."""

    items: list[LotShort]
    total: int
