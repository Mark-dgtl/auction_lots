"""Схемы Telegram-интеграции."""

from datetime import datetime

from pydantic import BaseModel


class TelegramLinkResponse(BaseModel):
    """Ответ с deep-link для привязки Telegram-аккаунта."""

    deep_link: str
    token: str
    expires_at: datetime


class TelegramBindRequest(BaseModel):
    """Тело запроса привязки Telegram (внутренний API)."""

    token: str
    telegram_user_id: int
    chat_id: int


class TelegramBindResponse(BaseModel):
    """Ответ на привязку Telegram (внутренний API)."""

    user_id: int
