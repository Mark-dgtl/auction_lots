"""Тесты эндпоинта POST /api/notifications/test."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox
from app.models.user import User


@pytest.mark.asyncio
async def test_send_test_notification(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, registered_user
):
    """Пользователь с привязанным Telegram → 204 + запись в outbox."""
    # Ставим telegram_chat_id напрямую в БД
    user = await db_session.scalar(
        select(User).where(User.id == registered_user["id"])
    )
    user.telegram_chat_id = 555555
    user.telegram_user_id = 555555
    await db_session.commit()

    resp = await client.post("/api/notifications/test", headers=auth_headers)
    assert resp.status_code == 204

    msgs = (
        await db_session.scalars(
            select(Outbox).where(Outbox.user_id == registered_user["id"])
        )
    ).all()
    assert len(msgs) == 1
    assert "Тестовое уведомление" in msgs[0].text


@pytest.mark.asyncio
async def test_send_test_notification_no_telegram(
    client: AsyncClient, auth_headers: dict
):
    """Пользователь без Telegram → 409 TELEGRAM_NOT_LINKED."""
    resp = await client.post("/api/notifications/test", headers=auth_headers)
    assert resp.status_code == 409
    data = resp.json()
    assert data["error"]["code"] == "TELEGRAM_NOT_LINKED"


@pytest.mark.asyncio
async def test_send_test_notification_unauthorized(client: AsyncClient):
    """Запрос без авторизации → 401."""
    resp = await client.post("/api/notifications/test")
    assert resp.status_code == 401
