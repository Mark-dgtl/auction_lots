"""Модель избранного (связь пользователь ↔ лот)."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Favorite(Base):
    """Запись об избранном лоте пользователя.

    Attributes:
        user_id: FK на пользователя (часть составного PK).
        lot_id: FK на лот (часть составного PK).
        created_at: Когда лот был добавлен в избранное.
    """

    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        _BIG,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lot_id: Mapped[int] = mapped_column(
        _BIG,
        ForeignKey("lots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
