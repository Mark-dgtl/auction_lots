"""Схемы настроек уведомлений."""

from typing import Optional

from pydantic import BaseModel


class NotificationSettingsUpdate(BaseModel):
    """Тело запроса обновления настроек уведомлений."""

    digest_time: Optional[str]  # "HH:MM" или null для отключения


class NotificationSettingsResponse(BaseModel):
    """Текущие настройки уведомлений пользователя."""

    digest_time: Optional[str]  # "HH:MM" или null
    telegram_linked: bool
