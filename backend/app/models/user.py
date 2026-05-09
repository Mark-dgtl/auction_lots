"""Модель пользователя системы."""

from datetime import datetime, time, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Text, Time
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Пользователь системы.

    Attributes:
        id: Первичный ключ (BIGSERIAL в PG, INTEGER в SQLite).
        email: Email (CITEXT — без учёта регистра в PostgreSQL).
        password_hash: bcrypt-хэш пароля.
        full_name: Полное имя пользователя (опционально).
        is_admin: Признак администратора системы.
        is_blocked: Признак заблокированного пользователя.
        telegram_user_id: Telegram user_id после привязки.
        telegram_chat_id: Telegram chat_id для отправки сообщений.
        telegram_link_token: One-time токен для привязки аккаунта.
        telegram_token_expires_at: Время истечения токена привязки.
        digest_time: Локальное время отправки дайджеста.
        digest_tz: Таймзона пользователя (по умолчанию Europe/Moscow).
        created_at: Дата регистрации.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        Text().with_variant(CITEXT(), "postgresql"),
        nullable=False,
        unique=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(
        _BIG, unique=True, nullable=True
    )
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(_BIG, nullable=True)
    telegram_link_token: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True
    )
    telegram_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
    digest_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    digest_tz: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Europe/Moscow"
    )
    created_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
