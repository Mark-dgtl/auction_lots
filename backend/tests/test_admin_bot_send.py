"""Тесты Admin Bot Send: TELEGRAM_NOT_LINKED и happy path."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox
from app.models.user import User


async def _make_admin(db: AsyncSession, user_id: int) -> None:
    user = await db.scalar(select(User).where(User.id == user_id))
    user.is_admin = True
    await db.commit()


@pytest.fixture
async def admin_headers(
    client: AsyncClient, registered_user: dict, db_session: AsyncSession
) -> dict:
    await _make_admin(db_session, registered_user["id"])
    resp = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_bot_send_telegram_not_linked(
    client: AsyncClient,
    admin_headers: dict,
    registered_user: dict,
):
    """POST /api/admin/bot/send без Telegram → 409 TELEGRAM_NOT_LINKED."""
    resp = await client.post(
        "/api/admin/bot/send",
        json={"user_id": registered_user["id"], "text": "Привет!"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "TELEGRAM_NOT_LINKED"


@pytest.mark.asyncio
async def test_bot_send_happy_path(
    client: AsyncClient,
    admin_headers: dict,
    registered_user: dict,
    db_session: AsyncSession,
):
    """POST /api/admin/bot/send с привязанным Telegram создаёт outbox-запись."""
    # Привязываем Telegram к пользователю
    user = await db_session.scalar(select(User).where(User.id == registered_user["id"]))
    user.telegram_user_id = 123456789
    user.telegram_chat_id = 123456789
    await db_session.commit()

    resp = await client.post(
        "/api/admin/bot/send",
        json={
            "user_id": registered_user["id"],
            "text": "Тестовое сообщение",
            "parse_mode": "html",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "outbox_id" in data

    # Проверяем запись в outbox
    outbox_id = data["outbox_id"]
    msg = await db_session.scalar(select(Outbox).where(Outbox.id == outbox_id))
    assert msg is not None
    assert msg.text == "Тестовое сообщение"
    assert msg.source == "admin"
    assert msg.parse_mode == "html"
    assert msg.status == "pending"


@pytest.mark.asyncio
async def test_bot_send_bot_offline_warning(
    client: AsyncClient,
    admin_headers: dict,
    registered_user: dict,
    db_session: AsyncSession,
):
    """POST /api/admin/bot/send возвращает warning=BOT_OFFLINE если бот оффлайн."""
    # Привязываем Telegram
    user = await db_session.scalar(select(User).where(User.id == registered_user["id"]))
    user.telegram_user_id = 987654321
    user.telegram_chat_id = 987654321
    await db_session.commit()

    # Не создаём heartbeat — бот оффлайн
    resp = await client.post(
        "/api/admin/bot/send",
        json={"user_id": registered_user["id"], "text": "Оффлайн тест"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("warning") == "BOT_OFFLINE"
    assert "outbox_id" in data


@pytest.mark.asyncio
async def test_bot_broadcast_queues_messages(
    client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """POST /api/admin/bot/broadcast создаёт outbox для всех telegram-пользователей."""
    from app.models.user import User
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("pass")

    # Создаём пользователей с telegram
    for i in range(3):
        u = User(
            email=f"tg_user_{i}@example.com",
            password_hash=pwd,
            telegram_user_id=1000 + i,
            telegram_chat_id=1000 + i,
        )
        db_session.add(u)
    await db_session.commit()

    resp = await client.post(
        "/api/admin/bot/broadcast",
        json={
            "text": "Рассылка тест",
            "audience": {"has_telegram": True},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["queued"] >= 3
