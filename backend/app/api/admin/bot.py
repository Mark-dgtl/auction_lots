"""Эндпоинты /api/admin/bot/send и /api/admin/bot/broadcast."""

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import settings
from app.core.errors import Conflict
from app.db.session import get_db
from app.models.bot_heartbeat import BotHeartbeat
from app.models.outbox import Outbox
from app.models.user import User
from app.services.audit_service import get_audit_writer

router = APIRouter()
logger = logging.getLogger("app.admin.bot")


class SendBody(BaseModel):
    """Тело POST /api/admin/bot/send."""

    user_id: int
    text: str
    parse_mode: Optional[str] = None


class BroadcastAudience(BaseModel):
    """Фильтр аудитории для рассылки."""

    has_telegram: bool = True
    has_filter: Optional[bool] = None
    user_ids: Optional[list[int]] = None


class BroadcastBody(BaseModel):
    """Тело POST /api/admin/bot/broadcast."""

    text: str
    parse_mode: Optional[str] = None
    audience: BroadcastAudience


def _is_bot_online(hb: Optional[BotHeartbeat]) -> bool:
    """Проверяет, онлайн ли бот по последнему heartbeat."""
    if not hb:
        return False
    last = hb.last_seen_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last).total_seconds()
    return age < settings.ADMIN_BOT_OFFLINE_THRESHOLD_SECONDS


@router.post("/bot/send")
async def bot_send(
    body: SendBody,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> dict:
    """Отправляет личное сообщение пользователю через Telegram-бот."""
    user = await db.scalar(select(User).where(User.id == body.user_id))
    if not user:
        from app.core.errors import NotFound
        raise NotFound("Пользователь не найден")

    if not user.telegram_chat_id:
        raise Conflict("Telegram не привязан", code="TELEGRAM_NOT_LINKED")

    msg = Outbox(
        user_id=user.id,
        chat_id=user.telegram_chat_id,
        text=body.text,
        parse_mode=body.parse_mode,
        status="pending",
        source="admin",
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    await audit(
        "BOT_SEND",
        target_type="user",
        target_id=str(user.id),
        payload={"text_len": len(body.text), "parse_mode": body.parse_mode},
    )
    await db.commit()

    # Проверяем онлайн-статус бота
    hb = await db.scalar(select(BotHeartbeat).where(BotHeartbeat.id == 1))
    result: dict = {"outbox_id": msg.id}
    if not _is_bot_online(hb):
        result["warning"] = "BOT_OFFLINE"
        logger.warning("Сообщение поставлено в очередь, но бот оффлайн (id=%d)", msg.id)

    logger.info("Администратор отправил сообщение пользователю id=%d", user.id)
    return result


@router.post("/bot/broadcast")
async def bot_broadcast(
    body: BroadcastBody,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    audit: Callable = Depends(get_audit_writer),
) -> dict:
    """Отправляет рассылку по аудитории."""
    from sqlalchemy import func
    from app.models.saved_filter import SavedFilter

    stmt = select(User).where(User.telegram_chat_id.isnot(None))

    if body.audience.user_ids:
        stmt = stmt.where(User.id.in_(body.audience.user_ids))
    elif body.audience.has_filter is True:
        # Только пользователи с сохранёнными фильтрами
        users_with_filters = select(SavedFilter.user_id).distinct()
        stmt = stmt.where(User.id.in_(users_with_filters))
    elif body.audience.has_filter is False:
        users_with_filters = select(SavedFilter.user_id).distinct()
        stmt = stmt.where(User.id.notin_(users_with_filters))

    users = await db.scalars(stmt)
    user_list = users.all()

    queued = 0
    for u in user_list:
        if not u.telegram_chat_id:
            continue
        msg = Outbox(
            user_id=u.id,
            chat_id=u.telegram_chat_id,
            text=body.text,
            parse_mode=body.parse_mode,
            status="pending",
            source="admin",
        )
        db.add(msg)
        queued += 1

    await db.commit()

    await audit(
        "BOT_BROADCAST",
        target_type=None,
        payload={
            "text_len": len(body.text),
            "audience": body.audience.model_dump(),
            "queued": queued,
        },
    )
    await db.commit()
    logger.info("Администратор запустил рассылку: %d получателей", queued)
    return {"queued": queued}
