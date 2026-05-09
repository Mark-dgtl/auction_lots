"""Сервис Telegram-интеграции: генерация deep-link и привязка аккаунтов."""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFound, Unauthorized
from app.models.user import User

logger = logging.getLogger("app.telegram")


class TelegramService:
    """Сервис генерации one-time ссылок и привязки Telegram-аккаунтов.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def generate_link(self, user_id: int) -> dict:
        """Генерирует one-time deep-link для привязки Telegram.

        Токен действителен 1 час. Предыдущий токен перезаписывается.

        Args:
            user_id: ID пользователя.

        Returns:
            Словарь с deep_link, token и expires_at.

        Raises:
            NotFound: Если пользователь не найден.
        """
        user = await self._db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise NotFound("Пользователь не найден")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        user.telegram_link_token = token
        user.telegram_token_expires_at = expires_at
        await self._db.commit()

        deep_link = (
            f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"
        )
        logger.info("Сгенерирован deep-link для пользователя id=%s", user_id)
        return {"deep_link": deep_link, "token": token, "expires_at": expires_at}

    async def unlink(self, user_id: int) -> None:
        """Отвязывает Telegram-аккаунт от пользователя.

        Args:
            user_id: ID пользователя.

        Raises:
            NotFound: Если пользователь не найден.
        """
        user = await self._db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise NotFound("Пользователь не найден")

        user.telegram_user_id = None
        user.telegram_chat_id = None
        user.telegram_link_token = None
        user.telegram_token_expires_at = None
        await self._db.commit()
        logger.info("Telegram-аккаунт отвязан от пользователя id=%s", user_id)

    async def bind_telegram(
        self, token: str, telegram_user_id: int, chat_id: int
    ) -> int:
        """Привязывает Telegram-аккаунт по one-time токену.

        Вызывается из внутреннего API при нажатии /start в боте.

        Args:
            token: One-time токен, полученный из deep-link.
            telegram_user_id: Telegram user ID.
            chat_id: Telegram chat ID.

        Returns:
            ID пользователя системы.

        Raises:
            NotFound: Если токен не найден.
            Unauthorized: Если токен истёк.
        """
        user = await self._db.scalar(
            select(User).where(User.telegram_link_token == token)
        )
        if not user:
            raise NotFound("Токен привязки не найден или уже использован")

        if user.telegram_token_expires_at:
            exp = user.telegram_token_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                raise Unauthorized("Токен привязки истёк")

        user.telegram_user_id = telegram_user_id
        user.telegram_chat_id = chat_id
        user.telegram_link_token = None
        user.telegram_token_expires_at = None
        await self._db.commit()

        logger.info(
            "Telegram id=%s привязан к пользователю id=%s",
            telegram_user_id,
            user.id,
        )
        return user.id
