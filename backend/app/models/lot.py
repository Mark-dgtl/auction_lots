"""Модель лота торгов."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger, ForeignKey, Integer, JSON, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lot(Base):
    """Лот торгов, полученный от парсера или загруженный вручную.

    Поля source + source_lot_id уникальны совместно (UNIQUE constraint).
    search_tsv заполняется триггером в PostgreSQL; в SQLite — NULL (тесты).

    Attributes:
        id: Первичный ключ.
        source: Идентификатор источника ('efrsb', 'torgi_gov').
        source_lot_id: ID лота в системе источника.
        title: Заголовок лота.
        description: Полное описание лота.
        category: Slug категории (FK → categories.slug).
        region_code: Код ОКАТО региона (FK → regions.code).
        price: Текущая цена в рублях.
        price_step: Шаг понижения цены.
        source_url: Прямая ссылка на карточку лота.
        auction_date: Дата проведения торгов (UTC).
        published_at: Дата публикации у источника (UTC).
        status: Текстовый статус у источника.
        images: Список URL изображений (JSONB array).
        raw: Сырые данные от источника.
        search_tsv: Вектор полнотекстового поиска (только PG).
        first_seen_at: Когда лот был впервые добавлен.
        updated_at: Когда запись последний раз обновлялась.
    """

    __tablename__ = "lots"
    __table_args__ = (UniqueConstraint("source", "source_lot_id"),)

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_lot_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("categories.slug"), nullable=True
    )
    region_code: Mapped[Optional[str]] = mapped_column(
        String(8), ForeignKey("regions.code"), nullable=True
    )
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    price_step: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    auction_date: Mapped[Optional[datetime]] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
    status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    images: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    raw: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    search_tsv: Mapped[Optional[Any]] = mapped_column(
        Text().with_variant(TSVECTOR(), "postgresql"),
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
