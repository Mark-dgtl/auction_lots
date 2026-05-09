"""Модель refresh-токена пользователя."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RefreshToken(Base):
    """Refresh-токен пользователя (хранится в БД для поддержки отзыва).

    Attributes:
        id: Первичный ключ.
        user_id: FK на пользователя.
        jti: JWT ID — уникальный идентификатор токена.
        expires_at: Время истечения токена.
        revoked_at: Время отзыва токена (NULL — активный).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        _BIG,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
