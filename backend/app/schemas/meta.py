"""Схемы метаданных: категории и регионы."""

from pydantic import BaseModel, ConfigDict


class CategoryItem(BaseModel):
    """Элемент справочника категорий."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class RegionItem(BaseModel):
    """Элемент справочника регионов."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str


class CategoryListResponse(BaseModel):
    """Ответ со списком категорий."""

    items: list[CategoryItem]


class RegionListResponse(BaseModel):
    """Ответ со списком регионов."""

    items: list[RegionItem]
