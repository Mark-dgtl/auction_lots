"""Очередь исходящих сообщений для Telegram-бота."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, String, Text
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Outbox(Base):
    """Исходящее сообщение в очереди для Telegram-бота.

    Attributes:
        id: Первичный ключ.
        user_id: FK на пользователя-получателя.
        chat_id: Telegram chat_id для отправки.
        text: Текст сообщения.
        parse_mode: Режим форматирования ('html', 'markdown' или NULL).
        lot_ids: Список ID лотов в сообщении (JSONB array).
        status: Статус доставки ('pending', 'sent', 'failed').
        attempt_count: Количество попыток доставки.
        last_error: Текст последней ошибки доставки.
        source: Источник сообщения ('digest', 'admin', 'test').
        created_at: Когда сообщение было создано.
        sent_at: Когда бот подтвердил доставку (NULL — ещё не отправлено).
    """

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        _BIG, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[int] = mapped_column(_BIG, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    lot_ids: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="digest")
    created_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
