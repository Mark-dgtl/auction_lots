"""Журнал запусков парсера."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import DateTime as SADateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_BIG = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ParserRun(Base):
    """Запись о запуске парсера (для мониторинга и отладки).

    Attributes:
        id: Первичный ключ.
        source: Имя источника ('efrsb', 'torgi_gov').
        started_at: Время начала запуска.
        finished_at: Время окончания (NULL — ещё выполняется).
        status: Статус ('running', 'ok', 'error').
        lots_seen: Сколько лотов обработано.
        lots_new: Сколько новых лотов добавлено.
        lots_updated: Сколько лотов обновлено.
        pages_fetched: Сколько страниц источника успешно получено.
        expected_total_elements: Сколько элементов ожидал источник (если отдаёт API).
        yielded_total: Сколько лотов источник сгенерировал до ingestion.
        skipped_invalid: Сколько лотов/записей отброшено как невалидные.
        full_scan_completed: Пройден ли источник до конца (а не остановлен лимитом/ошибкой).
        triggered_by: Кто инициировал запуск ('schedule', 'admin').
        triggered_by_user_id: FK на пользователя-администратора (если запуск ручной).
        error: Текст ошибки при статусе 'error'.
    """

    __tablename__ = "parser_runs"

    id: Mapped[int] = mapped_column(_BIG, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        SADateTime(timezone=True), nullable=False, default=_utcnow
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        SADateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    lots_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lots_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lots_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expected_total_elements: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    yielded_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_invalid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    full_scan_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    triggered_by: Mapped[str] = mapped_column(
        String(16), nullable=False, default="schedule"
    )
    triggered_by_user_id: Mapped[Optional[int]] = mapped_column(
        _BIG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
