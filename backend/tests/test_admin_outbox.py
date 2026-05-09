"""Тесты Admin Outbox API и internal ack-механизма."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.outbox import Outbox
from app.models.user import User

_INTERNAL_HEADERS = {"X-Internal-Token": settings.INTERNAL_API_TOKEN}


async def _make_admin(db: AsyncSession, user_id: int) -> None:
    user = await db.scalar(select(User).where(User.id == user_id))
    user.is_admin = True
    await db.commit()


@pytest.fixture
async def admin_headers(client: AsyncClient, registered_user: dict, db_session: AsyncSession) -> dict:
    await _make_admin(db_session, registered_user["id"])
    resp = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def outbox_msg(db_session: AsyncSession, registered_user: dict) -> Outbox:
    """Создаёт тестовое сообщение в outbox."""
    msg = Outbox(
        user_id=registered_user["id"],
        chat_id=12345,
        text="Тест",
        lot_ids=[],
        status="failed",
        attempt_count=3,
        last_error="Connection refused",
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    return msg


@pytest.mark.asyncio
async def test_retry_resets_outbox(
    client: AsyncClient,
    admin_headers: dict,
    outbox_msg: Outbox,
    db_session: AsyncSession,
):
    """POST /api/admin/outbox/{id}/retry сбрасывает статус в pending."""
    resp = await client.post(
        f"/api/admin/outbox/{outbox_msg.id}/retry",
        headers=admin_headers,
    )
    assert resp.status_code == 204

    await db_session.refresh(outbox_msg)
    assert outbox_msg.status == "pending"
    assert outbox_msg.attempt_count == 0
    assert outbox_msg.last_error is None
    assert outbox_msg.sent_at is None


@pytest.mark.asyncio
async def test_ack_failed_increments_attempt_count(
    client: AsyncClient,
    registered_user: dict,
    db_session: AsyncSession,
):
    """POST /api/internal/outbox/{id}/ack с status=failed увеличивает attempt_count."""
    msg = Outbox(
        user_id=registered_user["id"],
        chat_id=999,
        text="Test",
        lot_ids=[],
        status="pending",
        attempt_count=0,
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    resp = await client.post(
        f"/api/internal/outbox/{msg.id}/ack",
        json={"status": "failed", "error": "Telegram timeout"},
        headers=_INTERNAL_HEADERS,
    )
    assert resp.status_code == 204

    await db_session.refresh(msg)
    assert msg.attempt_count == 1
    assert msg.last_error == "Telegram timeout"
    assert msg.status == "pending"  # ещё не финальный


@pytest.mark.asyncio
async def test_ack_failed_3_times_marks_failed(
    client: AsyncClient,
    registered_user: dict,
    db_session: AsyncSession,
):
    """После 3 неудачных попыток status становится failed."""
    msg = Outbox(
        user_id=registered_user["id"],
        chat_id=999,
        text="Test",
        lot_ids=[],
        status="pending",
        attempt_count=2,
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    resp = await client.post(
        f"/api/internal/outbox/{msg.id}/ack",
        json={"status": "failed", "error": "Final error"},
        headers=_INTERNAL_HEADERS,
    )
    assert resp.status_code == 204

    await db_session.refresh(msg)
    assert msg.attempt_count == 3
    assert msg.status == "failed"


@pytest.mark.asyncio
async def test_list_outbox_admin(
    client: AsyncClient,
    admin_headers: dict,
    outbox_msg: Outbox,
):
    """GET /api/admin/outbox возвращает список сообщений."""
    resp = await client.get("/api/admin/outbox", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_delete_outbox_admin(
    client: AsyncClient,
    admin_headers: dict,
    outbox_msg: Outbox,
    db_session: AsyncSession,
):
    """DELETE /api/admin/outbox/{id} удаляет сообщение."""
    resp = await client.delete(
        f"/api/admin/outbox/{outbox_msg.id}", headers=admin_headers
    )
    assert resp.status_code == 204

    deleted = await db_session.scalar(
        select(Outbox).where(Outbox.id == outbox_msg.id)
    )
    assert deleted is None
