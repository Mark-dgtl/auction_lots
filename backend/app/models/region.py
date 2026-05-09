"""Справочник регионов РФ (ОКАТО)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Region(Base):
    """Регион РФ по ОКАТО-коду.

    Attributes:
        code: Двузначный код ОКАТО (PRIMARY KEY).
        name: Полное название региона.
    """

    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
