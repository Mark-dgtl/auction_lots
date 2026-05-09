"""Эндпоинты /api/admin/outbox/* — управление очередью сообщений."""

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.errors import NotFound
from app.db.session import get_db
from app.models.outbox import Outbox
from app.models.user import User
from app.services.audit_service import get_audit_writer

router = APIRouter()
logger = logging.getLogger("app.admin.outbox")


def _outbox_item(msg: Outbox, user_email: Optional[str] = None) -> dict:
    return {
        "id": msg.id,
        "user_id": msg.user_id,
        "user_email": user_email,
        "chat_id": msg.chat_id,
        "text": msg.text,
        "lot_ids": msg.lot_ids,
        "status": msg.status,
        "attempt_count": msg.attempt_count,
        "error": msg.last_error,
        "created_at": msg.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if msg.created_at else None,
        "sent_at": msg.sent_at.strftime("%Y-%m-%dT%H:%M:%SZ") if msg.sent_at else None,
    }


@router.get("/outbox")
async def list_outbox(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """Возвращает список сообщений очереди outbox."""
    stmt = select(Outbox)
    if status:
        stmt = stmt.where(Outbox.status == status)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    msgs = await db.scalars(
        stmt.order_by(Outbox.created_at.desc()).offset(offset).limit(limit)
    )

    items = []
    for m in msgs.all():
        user = await db.scalar(select(User).where(User.id == m.user_id))
        items.append(_outbox_item(m, user_email=str(user.email) if user else None))

    return {"items": items, "total": total}


@router.post("/outbox/{msg_id}/retry", status_code=204)
async def retry_outbox(
    msg_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> None:
    """Сбрасывает ошибку сообщения и возвращает его в очередь."""
    msg = await db.scalar(select(Outbox).where(Outbox.id == msg_id))
    if not msg:
        raise NotFound("Сообщение не найдено")

    msg.status = "pending"
    msg.attempt_count = 0
    msg.last_error = None
    msg.sent_at = None
    await db.commit()

    await audit("OUTBOX_RETRY", target_type="outbox", target_id=str(msg_id))
    await db.commit()
    logger.info("Администратор сбросил статус сообщения outbox id=%d", msg_id)


@router.delete("/outbox/{msg_id}", status_code=204)
async def delete_outbox(
    msg_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> None:
    """Удаляет сообщение из outbox."""
    msg = await db.scalar(select(Outbox).where(Outbox.id == msg_id))
    if not msg:
        raise NotFound("Сообщение не найдено")

    await audit("OUTBOX_DELETE", target_type="outbox", target_id=str(msg_id))
    await db.delete(msg)
    await db.commit()
    logger.info("Администратор удалил сообщение outbox id=%d", msg_id)
