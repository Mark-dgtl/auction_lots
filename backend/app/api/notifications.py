"""Роутер настроек и тестирования уведомлений."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import Conflict
from app.db.session import get_db
from app.models.outbox import Outbox
from app.models.user import User
from app.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse:
    """Возвращает настройки уведомлений текущего пользователя."""
    svc = NotificationService(db)
    return await svc.get_settings(user.id)


@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    body: NotificationSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Обновляет время отправки дайджеста.

    Args:
        body: digest_time в формате "HH:MM" или null для отключения.
    """
    svc = NotificationService(db)
    await svc.update_settings(user.id, body.digest_time)
    return await svc.get_settings(user.id)


@router.post("/test", status_code=204)
async def send_test_notification(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Отправляет тестовое уведомление в Telegram текущего пользователя.

    Кладёт одну запись в таблицу outbox с тестовым текстом.
    Бот заберёт её при следующем опросе.

    Returns:
        204 No Content.

    Raises:
        Conflict: Если Telegram-аккаунт не привязан к профилю.
    """
    if user.telegram_chat_id is None:
        raise Conflict(
            "Telegram не привязан к аккаунту",
            code="TELEGRAM_NOT_LINKED",
        )

    msg = Outbox(
        user_id=user.id,
        chat_id=user.telegram_chat_id,
        text="Тестовое уведомление от агрегатора торгов! Всё работает корректно.",
        lot_ids=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    await db.commit()
