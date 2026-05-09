"""Журнал отправленных уведомлений (для идемпотентности)."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, ForeignKey, Integer, UniqueConstraint
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationLog(Base):
    """Запись о том, что уведомление по фильтру о конкретном лоте было отправлено.

    Уникальность (user_id, filter_id, lot_id) гарантирует идемпотентность.

    Attributes:
        id: Первичный ключ.
        user_id: FK на пользователя.
        filter_id: FK на сохранённый фильтр.
        lot_id: FK на лот.
        sent_at: Когда уведомление было отправлено.
    """

    __tablename__ = "notification_log"
    __table_args__ = (UniqueConstraint("user_id", "filter_id", "lot_id"),)

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        _BIG, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filter_id: Mapped[int] = mapped_column(
        _BIG, ForeignKey("saved_filters.id", ondelete="CASCADE"), nullable=False
    )
    lot_id: Mapped[int] = mapped_column(
        _BIG, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
