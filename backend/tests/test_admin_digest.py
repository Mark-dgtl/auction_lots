"""Тесты admin-управления шаблоном и ручным запуском дайджеста."""

from datetime import datetime, time, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox
from app.models.saved_filter import SavedFilter
from app.models.user import User


async def _make_admin(db: AsyncSession, user_id: int) -> None:
    user = await db.scalar(select(User).where(User.id == user_id))
    user.is_admin = True
    await db.commit()


@pytest.mark.asyncio
async def test_admin_digest_template_get_and_put(
    client: AsyncClient,
    registered_user: dict,
    auth_headers: dict,
    db_session: AsyncSession,
):
    await _make_admin(db_session, registered_user["id"])

    get_resp = await client.get("/api/admin/digest/template", headers=auth_headers)
    assert get_resp.status_code == 200
    assert "template" in get_resp.json()

    put_resp = await client.put(
        "/api/admin/digest/template",
        headers=auth_headers,
        json={"template": "Фильтр: {filter_name}\nЛотов: {lots_count}\n\n{lots}"},
    )
    assert put_resp.status_code == 200
    assert "{filter_name}" in put_resp.json()["template"]


@pytest.mark.asyncio
async def test_admin_digest_template_rejects_unknown_placeholder(
    client: AsyncClient,
    registered_user: dict,
    auth_headers: dict,
    db_session: AsyncSession,
):
    await _make_admin(db_session, registered_user["id"])

    resp = await client.put(
        "/api/admin/digest/template",
        headers=auth_headers,
        json={"template": "Bad {unknown_key}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_admin_digest_run_now_creates_outbox(
    client: AsyncClient,
    registered_user: dict,
    auth_headers: dict,
    db_session: AsyncSession,
):
    from app.models.lot import Lot

    await _make_admin(db_session, registered_user["id"])
    user = await db_session.scalar(select(User).where(User.id == registered_user["id"]))
    user.telegram_user_id = 123
    user.telegram_chat_id = 123
    user.digest_tz = "UTC"
    # Специально ставим время "далеко", чтобы обычный tick не сработал,
    # но ручной запуск с force=True должен сработать.
    user.digest_time = time((datetime.now(timezone.utc).hour + 5) % 24, 0)
    db_session.add(user)
    await db_session.commit()

    sf = SavedFilter(
        user_id=user.id,
        name="Тестовый фильтр",
        filter={"category": "real_estate"},
        notify_enabled=True,
    )
    db_session.add(sf)
    db_session.add(
        Lot(
            source="torgi_gov",
            source_lot_id="admin-digest-1",
            title="Тестовый лот",
            category="real_estate",
            source_url="https://example.com/lot/1",
            images=[],
            raw={},
        )
    )
    await db_session.commit()

    resp = await client.post("/api/admin/digest/run-now", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["created"] >= 1

    outbox_items = (
        await db_session.scalars(select(Outbox).where(Outbox.user_id == user.id))
    ).all()
    assert len(outbox_items) >= 1
