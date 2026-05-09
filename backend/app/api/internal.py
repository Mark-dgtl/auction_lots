"""Внутренний API для взаимодействия бот ↔ backend.

Все эндпоинты защищены заголовком X-Internal-Token.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_internal_token
from app.db.session import get_db
from app.models.bot_heartbeat import BotHeartbeat
from app.models.outbox import Outbox
from app.schemas.telegram import TelegramBindRequest, TelegramBindResponse
from app.services.telegram_service import TelegramService

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_token)],
)

logger = logging.getLogger("app.internal")


class AckBody(BaseModel):
    """Тело POST /api/internal/outbox/{id}/ack."""

    status: str  # "sent" | "failed"
    error: Optional[str] = None


class HeartbeatBody(BaseModel):
    """Тело POST /api/internal/bot/heartbeat."""

    polling_ok: bool
    version: Optional[str] = None


class LogRecord(BaseModel):
    """Одна запись лога бота."""

    ts: str
    level: str
    name: str
    message: str


class BotLogBody(BaseModel):
    """Тело POST /api/internal/bot/log."""

    records: list[LogRecord]


@router.post("/telegram/bind", response_model=TelegramBindResponse)
async def bind_telegram(
    body: TelegramBindRequest,
    db: AsyncSession = Depends(get_db),
) -> TelegramBindResponse:
    """Привязывает Telegram-аккаунт к пользователю по one-time токену.

    Вызывается из Telegram-бота при нажатии команды /start с токеном.

    Args:
        body: token, telegram_user_id и chat_id.

    Returns:
        user_id пользователя системы.
    """
    svc = TelegramService(db)
    user_id = await svc.bind_telegram(
        body.token, body.telegram_user_id, body.chat_id
    )
    logger.info(
        "Telegram id=%s успешно привязан через внутренний API", body.telegram_user_id
    )
    return TelegramBindResponse(user_id=user_id)


@router.get("/outbox")
async def get_outbox(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Возвращает pending-сообщения из очереди для бота.

    Args:
        limit: Максимальное число сообщений.
    """
    msgs = await db.scalars(
        select(Outbox)
        .where(Outbox.status == "pending")
        .order_by(Outbox.created_at)
        .limit(limit)
    )
    items = [
        {
            "id": m.id,
            "chat_id": m.chat_id,
            "text": m.text,
            "parse_mode": m.parse_mode,
            "lot_ids": m.lot_ids,
        }
        for m in msgs.all()
    ]
    return {"items": items}


@router.post("/outbox/{msg_id}/ack", status_code=204)
async def ack_outbox(
    msg_id: int,
    body: AckBody,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Подтверждает или фиксирует ошибку доставки сообщения из очереди.

    При status='sent': помечает как sent, проставляет sent_at.
    При status='failed': увеличивает attempt_count, сохраняет ошибку.
    После 3 неудач — status='failed', иначе возвращает в pending.

    Args:
        msg_id: ID сообщения в таблице outbox.
        body: Статус и опциональный текст ошибки.
    """
    msg = await db.scalar(select(Outbox).where(Outbox.id == msg_id))
    if not msg:
        return

    if body.status == "sent":
        msg.status = "sent"
        msg.sent_at = datetime.now(timezone.utc)
        logger.info("Сообщение outbox id=%s доставлено", msg_id)
    elif body.status == "failed":
        msg.attempt_count += 1
        msg.last_error = body.error
        if msg.attempt_count >= 3:
            msg.status = "failed"
            logger.warning(
                "Сообщение outbox id=%s окончательно не доставлено после %d попыток",
                msg_id,
                msg.attempt_count,
            )
        else:
            msg.status = "pending"
            msg.sent_at = None
            logger.warning(
                "Ошибка доставки outbox id=%s (попытка %d): %s",
                msg_id,
                msg.attempt_count,
                body.error,
            )

    await db.commit()


@router.post("/bot/heartbeat", status_code=204)
async def bot_heartbeat(
    body: HeartbeatBody,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Обновляет heartbeat бота.

    Args:
        body: polling_ok и опциональная версия бота.
    """
    hb = await db.scalar(select(BotHeartbeat).where(BotHeartbeat.id == 1))
    if hb is None:
        hb = BotHeartbeat(id=1)
        db.add(hb)

    hb.last_seen_at = datetime.now(timezone.utc)
    hb.polling_ok = body.polling_ok
    if body.version is not None:
        hb.version = body.version

    await db.commit()
    logger.debug("Heartbeat бота обновлён: polling_ok=%s", body.polling_ok)


@router.post("/bot/log", status_code=204)
async def bot_log(body: BotLogBody) -> None:
    """Принимает батч логов от бота и помещает в кольцевой буфер.

    Только в буфер, без записи в БД.

    Args:
        body: Список записей логов (до 200 за вызов).
    """
    from app.core.log_buffer import ring_handler

    records = body.records[:200]
    for rec in records:
        ring_handler.push_external(
            {
                "ts": rec.ts,
                "level": rec.level.upper(),
                "source": "bot",
                "logger": rec.name,
                "message": rec.message,
            }
        )
    logger.debug("Получено %d записей логов от бота", len(records))
