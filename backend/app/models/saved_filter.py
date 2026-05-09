"""Модель сохранённого поискового фильтра."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SavedFilter(Base):
    """Сохранённый поисковый фильтр пользователя.

    Attributes:
        id: Первичный ключ.
        user_id: FK на пользователя.
        name: Пользовательское название фильтра.
        filter: JSONB-объект с параметрами фильтрации.
        notify_enabled: Включены ли push-уведомления по фильтру.
        created_at: Дата создания.
    """

    __tablename__ = "saved_filters"

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        _BIG,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    filter: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    notify_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
