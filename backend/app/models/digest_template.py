"""Пользовательский шаблон регулярного дайджеста (singleton)."""

from datetime import datetime, timezone

from sqlalchemy import SmallInteger, Text
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DigestTemplate(Base):
    """Хранилище шаблона регулярного дайджеста (одна строка, id=1)."""

    __tablename__ = "digest_template"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    template_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
