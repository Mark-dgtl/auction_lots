"""Сервис поиска и получения лотов."""

import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models.favorite import Favorite
from app.models.lot import Lot
from app.models.region import Region

logger = logging.getLogger("app.lots")

VALID_SORTS = frozenset({"date_desc", "price_asc", "price_desc", "random"})


class LotService:
    """Сервис работы с лотами: поиск, фильтрация, детальная карточка.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search(
        self,
        *,
        query: Optional[str] = None,
        category: Optional[str] = None,
        region: Optional[str] = None,
        price_from: Optional[Decimal] = None,
        price_to: Optional[Decimal] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sort: str = "date_desc",
        shuffle_seed: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Ищет лоты с фильтрами, сортировкой и пагинацией.

        Full-text поиск работает только в PostgreSQL (TSVECTOR/plainto_tsquery).
        В SQLite (тестовый режим) поиск по title через LIKE.

        Args:
            query: Строка поиска.
            category: Slug категории.
            region: Код ОКАТО региона.
            price_from: Нижняя граница цены.
            price_to: Верхняя граница цены.
            date_from: Начало диапазона auction_date.
            date_to: Конец диапазона auction_date.
            sort: Сортировка (date_desc | price_asc | price_desc | random).
            shuffle_seed: Сид для random (стабильный порядок между страницами).
            page: Номер страницы (с 1).
            page_size: Размер страницы (1–100).
            user_id: ID пользователя для определения is_favorite.

        Returns:
            Кортеж (список dict-ов LotShort, total count).
        """
        stmt = select(Lot, Region.name.label("region_name")).outerjoin(
            Region, Lot.region_code == Region.code
        )

        if query:
            if self._is_postgresql():
                tsquery = func.plainto_tsquery("russian", query)
                stmt = stmt.where(Lot.search_tsv.op("@@")(tsquery))
            else:
                # SQLite: LIKE без регистро-зависимости для кириллицы через lower()
                stmt = stmt.where(
                    func.lower(Lot.title).like(f"%{query.lower()}%")
                )

        if category:
            stmt = stmt.where(Lot.category == category)
        if region:
            stmt = stmt.where(Lot.region_code == region)
        if price_from is not None:
            stmt = stmt.where(Lot.price >= price_from)
        if price_to is not None:
            stmt = stmt.where(Lot.price <= price_to)
        if date_from is not None:
            stmt = stmt.where(Lot.auction_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Lot.auction_date <= date_to)

        # Подсчёт total (отдельный запрос)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._db.scalar(count_stmt)) or 0

        if sort == "random" and not self._is_postgresql():
            stmt = await self._apply_random_sqlite(
                stmt, shuffle_seed, page, page_size
            )
            if stmt is None:
                return [], total
        else:
            stmt = self._apply_sort(stmt, sort, shuffle_seed)
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        rows = (await self._db.execute(stmt)).all()

        # Получаем избранные лоты пользователя
        fav_set: set[int] = set()
        if user_id:
            fav_ids = await self._db.scalars(
                select(Favorite.lot_id).where(Favorite.user_id == user_id)
            )
            fav_set = set(fav_ids.all())

        items = [
            self._lot_to_short(lot, region_name, lot.id in fav_set)
            for lot, region_name in rows
        ]
        return items, total

    async def get_by_id(
        self, lot_id: int, user_id: Optional[int] = None
    ) -> dict[str, Any]:
        """Возвращает детальное представление лота.

        Args:
            lot_id: Первичный ключ лота.
            user_id: ID пользователя для определения is_favorite.

        Returns:
            Словарь с данными LotDetail.

        Raises:
            NotFound: Если лот не найден.
        """
        row = (
            await self._db.execute(
                select(Lot, Region.name.label("region_name"))
                .outerjoin(Region, Lot.region_code == Region.code)
                .where(Lot.id == lot_id)
            )
        ).first()

        if not row:
            raise NotFound(f"Лот с id={lot_id} не найден")

        lot, region_name = row

        is_fav = False
        if user_id:
            fav = await self._db.scalar(
                select(Favorite).where(
                    Favorite.user_id == user_id,
                    Favorite.lot_id == lot_id,
                )
            )
            is_fav = fav is not None

        return self._lot_to_detail(lot, region_name, is_fav)

    async def _apply_random_sqlite(
        self,
        stmt,
        shuffle_seed: Optional[str],
        page: int,
        page_size: int,
    ):
        """Стабильный random для SQLite (тесты): сортировка id по md5(id:seed)."""
        seed = (shuffle_seed or "0")[:64]
        sub = stmt.subquery()
        id_result = await self._db.scalars(select(sub.c.id))
        ids = sorted(
            id_result.all(),
            key=lambda i: hashlib.md5(f"{i}:{seed}".encode()).hexdigest(),
        )
        page_ids = ids[(page - 1) * page_size : page * page_size]
        if not page_ids:
            return None
        order_case = case(
            {lot_id: idx for idx, lot_id in enumerate(page_ids)},
            value=Lot.id,
        )
        return stmt.where(Lot.id.in_(page_ids)).order_by(order_case)

    def _apply_sort(self, stmt, sort: str, shuffle_seed: Optional[str]):
        """Применяет ORDER BY; random — псевдослучайный порядок, стабильный по seed."""
        if sort == "price_asc":
            return stmt.order_by(Lot.price.asc().nulls_last())
        if sort == "price_desc":
            return stmt.order_by(Lot.price.desc().nulls_last())
        if sort == "random":
            seed = (shuffle_seed or "0")[:64]
            if self._is_postgresql():
                return stmt.order_by(
                    func.md5(func.concat(cast(Lot.id, String), seed))
                )
            return stmt.order_by(func.random())
        return stmt.order_by(Lot.first_seen_at.desc())

    def _is_postgresql(self) -> bool:
        """Определяет, используется ли PostgreSQL в текущей сессии."""
        try:
            sync_session = self._db.sync_session
            engine = sync_session.get_bind()
            return engine.dialect.name == "postgresql"
        except Exception:
            return False

    def _price_str(self, price: Optional[Decimal]) -> Optional[str]:
        """Конвертирует Decimal-цену в строку для JSON-ответа."""
        if price is None:
            return None
        return str(price)

    def _lot_to_short(
        self, lot: Lot, region_name: Optional[str], is_favorite: bool
    ) -> dict[str, Any]:
        """Формирует словарь LotShort из ORM-объекта."""
        images = lot.images or []
        thumbnail = images[0] if images else None
        return {
            "id": lot.id,
            "source": lot.source,
            "title": lot.title,
            "category": lot.category,
            "region_code": lot.region_code,
            "region_name": region_name,
            "price": self._price_str(lot.price),
            "auction_date": lot.auction_date,
            "thumbnail": thumbnail,
            "is_favorite": is_favorite,
        }

    def _lot_to_detail(
        self, lot: Lot, region_name: Optional[str], is_favorite: bool
    ) -> dict[str, Any]:
        """Формирует словарь LotDetail из ORM-объекта."""
        data = self._lot_to_short(lot, region_name, is_favorite)
        images = lot.images or []
        data.update(
            {
                "description": lot.description,
                "price_step": self._price_str(lot.price_step),
                "source_url": lot.source_url,
                "images": [str(img) for img in images],
                "status": lot.status,
                "published_at": lot.published_at,
                "updated_at": lot.updated_at,
            }
        )
        return data
