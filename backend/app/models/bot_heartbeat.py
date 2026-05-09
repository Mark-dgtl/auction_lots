"""Heartbeat бота — одна строка, обновляется ботом каждые 30 сек."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, SmallInteger, String
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BotHeartbeat(Base):
    """Состояние heartbeat Telegram-бота (всегда одна строка с id=1).

    Attributes:
        id: Всегда 1 (синглтон).
        last_seen_at: Время последнего heartbeat.
        polling_ok: Работает ли polling бота.
        version: Версия бота.
    """

    __tablename__ = "bot_heartbeat"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    last_seen_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
    polling_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
