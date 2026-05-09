"""Сервис управления сохранёнными поисковыми фильтрами."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound
from app.models.saved_filter import SavedFilter

logger = logging.getLogger("app.filters")


class FilterService:
    """CRUD-сервис для сохранённых фильтров пользователей.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_filters(self, user_id: int) -> list[SavedFilter]:
        """Возвращает все фильтры пользователя, от новых к старым.

        Args:
            user_id: ID пользователя.

        Returns:
            Список объектов SavedFilter.
        """
        result = await self._db.scalars(
            select(SavedFilter)
            .where(SavedFilter.user_id == user_id)
            .order_by(SavedFilter.created_at.desc())
        )
        return list(result.all())

    async def create_filter(
        self,
        user_id: int,
        name: str,
        filter_data: dict[str, Any],
        notify_enabled: bool,
    ) -> SavedFilter:
        """Создаёт новый фильтр для пользователя.

        Args:
            user_id: ID пользователя.
            name: Название фильтра.
            filter_data: Параметры фильтрации в виде словаря.
            notify_enabled: Включены ли уведомления.

        Returns:
            Созданный объект SavedFilter.
        """
        sf = SavedFilter(
            user_id=user_id,
            name=name,
            filter=filter_data,
            notify_enabled=notify_enabled,
        )
        self._db.add(sf)
        await self._db.commit()
        await self._db.refresh(sf)
        logger.info(
            "Создан фильтр id=%s для пользователя id=%s", sf.id, user_id
        )
        return sf

    async def update_filter(
        self, user_id: int, filter_id: int, data: dict[str, Any]
    ) -> SavedFilter:
        """Обновляет поля существующего фильтра.

        Args:
            user_id: ID пользователя (проверка владельца).
            filter_id: ID фильтра.
            data: Словарь обновляемых полей.

        Returns:
            Обновлённый объект SavedFilter.

        Raises:
            NotFound: Если фильтр не найден.
            Forbidden: Если фильтр принадлежит другому пользователю.
        """
        sf = await self._get_filter(user_id, filter_id)
        for key, value in data.items():
            setattr(sf, key, value)
        await self._db.commit()
        await self._db.refresh(sf)
        logger.info("Обновлён фильтр id=%s", filter_id)
        return sf

    async def delete_filter(self, user_id: int, filter_id: int) -> None:
        """Удаляет фильтр пользователя.

        Args:
            user_id: ID пользователя (проверка владельца).
            filter_id: ID фильтра.

        Raises:
            NotFound: Если фильтр не найден.
            Forbidden: Если фильтр принадлежит другому пользователю.
        """
        sf = await self._get_filter(user_id, filter_id)
        await self._db.delete(sf)
        await self._db.commit()
        logger.info("Удалён фильтр id=%s пользователя id=%s", filter_id, user_id)

    async def _get_filter(self, user_id: int, filter_id: int) -> SavedFilter:
        """Возвращает фильтр с проверкой принадлежности пользователю."""
        sf = await self._db.scalar(
            select(SavedFilter).where(SavedFilter.id == filter_id)
        )
        if not sf:
            raise NotFound(f"Фильтр с id={filter_id} не найден")
        if sf.user_id != user_id:
            raise Forbidden("Недостаточно прав для доступа к этому фильтру")
        return sf
