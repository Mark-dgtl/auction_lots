"""Сервис управления избранными лотами."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.favorite import Favorite
from app.models.lot import Lot
from app.models.region import Region
from app.services.lot_service import LotService

logger = logging.getLogger("app.favorites")


class FavoriteService:
    """Сервис добавления, удаления и чтения избранных лотов.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(self, user_id: int, lot_id: int) -> None:
        """Добавляет лот в избранное пользователя.

        Операция идемпотентна: повторное добавление не вызывает ошибки.

        Args:
            user_id: ID пользователя.
            lot_id: ID лота.

        Raises:
            NotFound: Если лот не существует.
        """
        lot = await self._db.scalar(select(Lot).where(Lot.id == lot_id))
        if not lot:
            raise NotFound(f"Лот с id={lot_id} не найден")

        existing = await self._db.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id, Favorite.lot_id == lot_id
            )
        )
        if existing:
            return  # Уже в избранном — идемпотентно

        self._db.add(Favorite(user_id=user_id, lot_id=lot_id))
        await self._db.commit()
        logger.info(
            "Пользователь id=%s добавил лот id=%s в избранное", user_id, lot_id
        )

    async def remove(self, user_id: int, lot_id: int) -> None:
        """Удаляет лот из избранного пользователя.

        Args:
            user_id: ID пользователя.
            lot_id: ID лота.

        Raises:
            NotFound: Если лот не найден в избранном.
        """
        fav = await self._db.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id, Favorite.lot_id == lot_id
            )
        )
        if not fav:
            raise NotFound("Лот не найден в избранном")

        await self._db.delete(fav)
        await self._db.commit()
        logger.info(
            "Пользователь id=%s удалил лот id=%s из избранного", user_id, lot_id
        )

    async def list_favorites(
        self, user_id: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Возвращает список избранных лотов пользователя.

        Args:
            user_id: ID пользователя.

        Returns:
            Кортеж (список dict-ов LotShort, total count).
        """
        stmt = (
            select(Lot, Region.name.label("region_name"))
            .outerjoin(Region, Lot.region_code == Region.code)
            .join(Favorite, Favorite.lot_id == Lot.id)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        rows = (await self._db.execute(stmt)).all()
        svc = LotService(self._db)
        items = [
            svc._lot_to_short(lot, region_name, True)
            for lot, region_name in rows
        ]
        return items, len(items)
