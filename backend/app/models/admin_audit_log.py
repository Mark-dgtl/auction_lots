"""Аудит-журнал административных действий."""

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


class AdminAuditLog(Base):
    """Запись аудита административного действия.

    Attributes:
        id: Первичный ключ.
        admin_user_id: FK на пользователя-администратора (SET NULL при удалении).
        action: Код действия (USER_DELETE, BOT_BROADCAST, DB_QUERY и т.д.).
        target_type: Тип объекта действия (user, lot, outbox, sql и т.д.).
        target_id: ID объекта или fingerprint (для SQL — sha256[:16]).
        payload: Дополнительные данные о действии (JSONB).
        ip: IP-адрес администратора.
        user_agent: User-Agent браузера администратора.
        created_at: Время записи.
    """

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[Optional[int]] = mapped_column(
        _BIG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payload: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
