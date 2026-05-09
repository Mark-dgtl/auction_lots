"""Сервис настроек уведомлений пользователя."""

import logging
import re
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, ValidationFailed
from app.models.user import User

logger = logging.getLogger("app.notifications")

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class NotificationService:
    """Сервис управления настройками дайджеста и уведомлений.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_settings(self, user_id: int) -> dict:
        """Возвращает текущие настройки уведомлений пользователя.

        Args:
            user_id: ID пользователя.

        Returns:
            Словарь с digest_time (HH:MM или None) и telegram_linked.

        Raises:
            NotFound: Если пользователь не найден.
        """
        user = await self._db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise NotFound("Пользователь не найден")
        return {
            "digest_time": (
                str(user.digest_time)[:5] if user.digest_time else None
            ),
            "telegram_linked": user.telegram_user_id is not None,
        }

    async def update_settings(
        self, user_id: int, digest_time: str | None
    ) -> dict:
        """Обновляет время отправки дайджеста.

        Args:
            user_id: ID пользователя.
            digest_time: Время в формате "HH:MM" или null для отключения.

        Returns:
            Словарь с обновлённым digest_time.

        Raises:
            NotFound: Если пользователь не найден.
            ValidationFailed: При неверном формате времени.
        """
        user = await self._db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise NotFound("Пользователь не найден")

        if digest_time is not None:
            if not _TIME_RE.match(digest_time):
                raise ValidationFailed("Формат времени должен быть HH:MM")
            h, m = map(int, digest_time.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValidationFailed("Недопустимое значение времени")
            user.digest_time = time(h, m)
        else:
            user.digest_time = None

        await self._db.commit()
        logger.info(
            "Обновлено время дайджеста для пользователя id=%s: %s",
            user_id,
            digest_time,
        )
        return {"digest_time": digest_time}
