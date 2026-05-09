"""Тесты внутреннего API (X-Internal-Token): bind, outbox get/ack."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.outbox import Outbox
from app.models.user import User

_INTERNAL_TOKEN = settings.INTERNAL_API_TOKEN
_HEADERS = {"X-Internal-Token": _INTERNAL_TOKEN}


# ---------------------------------------------------------------------------
# /api/internal/telegram/bind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bind_requires_internal_header(client: AsyncClient, registered_user):
    """Запрос без X-Internal-Token должен вернуть 403."""
    resp = await client.post(
        "/api/internal/telegram/bind",
        json={"token": "any", "telegram_user_id": 1, "chat_id": 1},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bind_invalid_token(client: AsyncClient):
    """Несуществующий токен привязки → 404."""
    resp = await client.post(
        "/api/internal/telegram/bind",
        json={"token": "invalid-token-xyz", "telegram_user_id": 999, "chat_id": 999},
        headers=_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bind_valid_token(client: AsyncClient, db_session: AsyncSession, registered_user):
    """Валидный токен привязки → 200 + telegram_user_id записан в БД."""
    from sqlalchemy import select

    # Выдаём токен через API
    auth_resp = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    token = auth_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    link_resp = await client.post("/api/telegram/link", headers=headers)
    assert link_resp.status_code == 200
    link_token = link_resp.json()["token"]

    # Привязываем через внутренний API
    bind_resp = await client.post(
        "/api/internal/telegram/bind",
        json={
            "token": link_token,
            "telegram_user_id": 7777777,
            "chat_id": 7777777,
        },
        headers=_HEADERS,
    )
    assert bind_resp.status_code == 200
    assert bind_resp.json()["user_id"] == registered_user["id"]

    # Проверяем в БД
    user = await db_session.scalar(
        select(User).where(User.id == registered_user["id"])
    )
    # Сессия в тесте отдельная от сессии HTTP-клиента; делаем refresh
    await db_session.refresh(user)
    assert user.telegram_user_id == 7777777


# ---------------------------------------------------------------------------
# /api/internal/outbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outbox_get_unsent(client: AsyncClient, db_session: AsyncSession, registered_user):
    """GET /api/internal/outbox возвращает только неотправленные сообщения."""
    # Создаём 2 outbox-записи: одну неотправленную, одну отправленную
    db_session.add(
        Outbox(
            user_id=registered_user["id"],
            chat_id=100,
            text="Не отправлено",
            lot_ids=[],
        )
    )
    db_session.add(
        Outbox(
            user_id=registered_user["id"],
            chat_id=100,
            text="Уже отправлено",
            lot_ids=[],
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    resp = await client.get("/api/internal/outbox?limit=10", headers=_HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["text"] == "Не отправлено"


@pytest.mark.asyncio
async def test_outbox_requires_internal_header(client: AsyncClient):
    """Запрос без заголовка → 403."""
    resp = await client.get("/api/internal/outbox")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_outbox_ack(client: AsyncClient, db_session: AsyncSession, registered_user):
    """POST /api/internal/outbox/{id}/ack проставляет sent_at."""
    from sqlalchemy import select

    msg = Outbox(
        user_id=registered_user["id"],
        chat_id=200,
        text="Нужно подтвердить",
        lot_ids=[],
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    resp = await client.post(
        f"/api/internal/outbox/{msg.id}/ack",
        json={"status": "sent"},
        headers=_HEADERS,
    )
    assert resp.status_code == 204

    await db_session.refresh(msg)
    assert msg.sent_at is not None
    assert msg.status == "sent"
