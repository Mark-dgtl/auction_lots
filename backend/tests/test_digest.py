"""Тесты DigestService: дайджест уведомлений пользователям."""

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.notification_log import NotificationLog
from app.models.outbox import Outbox
from app.models.saved_filter import SavedFilter
from app.models.user import User
from app.services.digest_service import DigestService


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _user_with_digest(digest_time: time) -> User:
    """Создаёт пользователя с заданным digest_time и привязанным Telegram."""
    return User(
        email="digest@example.com",
        password_hash="x",
        digest_time=digest_time,
        digest_tz="UTC",
        telegram_user_id=123456,
        telegram_chat_id=123456,
    )


@pytest.mark.asyncio
async def test_digest_tick_no_users(db_session):
    """Тик без пользователей с digest_time → 0 сообщений."""
    svc = DigestService(db_session)
    count = await svc.tick()
    assert count == 0


@pytest.mark.asyncio
async def test_digest_tick_creates_outbox(db_session):
    """Один пользователь, один фильтр, 3 новых лота → 1 outbox-запись, 3 notification_log."""
    from app.models.lot import Lot
    from app.models.region import Region

    # Регион
    db_session.add(Region(code="45", name="Москва"))

    # Пользователь с digest_time = текущая минута UTC
    now = _now_utc()
    user_time = time(now.hour, now.minute)
    user = _user_with_digest(user_time)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Сохранённый фильтр с уведомлениями
    sf = SavedFilter(
        user_id=user.id,
        name="Тест",
        filter={"category": "real_estate"},
        notify_enabled=True,
    )
    db_session.add(sf)
    await db_session.commit()
    await db_session.refresh(sf)

    # 3 лота с категорией real_estate
    for i in range(3):
        db_session.add(
            Lot(
                source="efrsb",
                source_lot_id=f"lot-d-{i}",
                title=f"Квартира {i}",
                category="real_estate",
                source_url=f"https://efrsb.ru/lot/{i}",
                images=[],
                raw={},
            )
        )
    await db_session.commit()

    svc = DigestService(db_session)
    count = await svc.tick()

    assert count == 1

    outbox_count = await db_session.scalar(
        select(Outbox).where(Outbox.user_id == user.id)
    )
    assert outbox_count is not None

    logs = (
        await db_session.scalars(
            select(NotificationLog).where(NotificationLog.user_id == user.id)
        )
    ).all()
    assert len(logs) == 3


@pytest.mark.asyncio
async def test_digest_skip_already_sent_today(db_session):
    """Второй тик за день не создаёт новых outbox-записей."""
    from app.models.lot import Lot

    now = _now_utc()
    user_time = time(now.hour, now.minute)
    user = _user_with_digest(user_time)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    sf = SavedFilter(
        user_id=user.id,
        name="Дублирующий",
        filter={},
        notify_enabled=True,
    )
    db_session.add(sf)

    db_session.add(
        Lot(
            source="efrsb",
            source_lot_id="lot-dup-1",
            title="Лот дублирующий",
            source_url="https://efrsb.ru/lot/d1",
            images=[],
            raw={},
        )
    )
    await db_session.commit()
    await db_session.refresh(sf)

    svc = DigestService(db_session)
    first = await svc.tick()
    assert first >= 1

    # Имитируем отправку outbox-записи «недавно» — уже есть в БД
    second = await svc.tick()
    assert second == 0


@pytest.mark.asyncio
async def test_digest_no_telegram_skipped(db_session):
    """Пользователь без telegram_chat_id не получает дайджест."""
    from app.models.lot import Lot

    now = _now_utc()
    user = User(
        email="notelegram@example.com",
        password_hash="x",
        digest_time=time(now.hour, now.minute),
        digest_tz="UTC",
        telegram_chat_id=None,
    )
    db_session.add(user)
    db_session.add(
        Lot(
            source="efrsb",
            source_lot_id="lot-nt-1",
            title="Лот без telegram",
            source_url="https://efrsb.ru/lot/nt1",
            images=[],
            raw={},
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    sf = SavedFilter(
        user_id=user.id, name="Нет telegram", filter={}, notify_enabled=True
    )
    db_session.add(sf)
    await db_session.commit()

    svc = DigestService(db_session)
    count = await svc.tick()
    assert count == 0
