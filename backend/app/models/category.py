"""Справочник категорий лотов."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Category(Base):
    """Категория лотов торгов.

    Attributes:
        slug: Уникальный идентификатор категории (PRIMARY KEY).
        name: Читаемое название на русском языке.
    """

    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
