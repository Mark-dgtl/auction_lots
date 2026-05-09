"""Сервис дайджестов — формирует и ставит в очередь уведомления по расписанию.

Логика: раз в DIGEST_CHECK_INTERVAL_MINUTES проверяем пользователей,
у которых digest_time попадает в текущее окно (±1 мин в их таймзоне),
и которым ещё не отправлялся дайджест за последние 23 часа.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from string import Formatter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.lot import Lot
from app.models.digest_template import DigestTemplate
from app.models.notification_log import NotificationLog
from app.models.outbox import Outbox
from app.models.saved_filter import SavedFilter
from app.models.user import User

logger = logging.getLogger("app.digest")

_MAX_LOTS_PER_FILTER = 10
_DEFAULT_DIGEST_TEMPLATE = (
    "Новые лоты по фильтру «{filter_name}» ({lots_count}):\n\n"
    "{lots}"
)
_DIGEST_TEMPLATE_KEYS = {"filter_name", "lots_count", "lots"}


class DigestService:
    """Сервис формирования дайджестов и постановки в очередь outbox.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def tick(self, *, force: bool = False) -> int:
        """Выполняет один тик дайджеста.

        Находит пользователей с digest_time в текущем минутном окне (±1 мин),
        у которых Telegram привязан и не было дайджеста за последние 23 часа.
        Для каждого формирует сообщения по каждому фильтру с notify_enabled=True
        и сохраняет в outbox + notification_log.

        Returns:
            Количество созданных записей в outbox.
        """
        now_utc = datetime.now(timezone.utc)

        users = (
            await self._db.scalars(select(User).where(User.digest_time.is_not(None)))
        ).all()
        template = await self.get_template()

        created = 0

        for user in users:
            if not await self._should_send(user, now_utc, force=force):
                continue

            filters = (
                await self._db.scalars(
                    select(SavedFilter).where(
                        SavedFilter.user_id == user.id,
                        SavedFilter.notify_enabled == True,
                    )
                )
            ).all()

            for saved_filter in filters:
                lots = await self._find_new_lots(saved_filter, user.id)
                if not lots:
                    continue

                text = self._format_message(saved_filter.name, lots, template=template)

                outbox = Outbox(
                    user_id=user.id,
                    chat_id=user.telegram_chat_id or 0,
                    text=text,
                    lot_ids=[lot.id for lot in lots],
                )
                self._db.add(outbox)

                for lot in lots:
                    log = NotificationLog(
                        user_id=user.id,
                        filter_id=saved_filter.id,
                        lot_id=lot.id,
                    )
                    self._db.add(log)

                created += 1

        if created > 0:
            await self._db.commit()
            logger.info("Создано %d сообщений дайджеста", created)

        return created

    async def _should_send(self, user: User, now_utc: datetime, *, force: bool) -> bool:
        """Проверяет, подходит ли пользователь для отправки дайджеста прямо сейчас.

        Args:
            user: Пользователь системы.
            now_utc: Текущее время UTC.

        Returns:
            True если digest_time в окне ±1 мин и Telegram привязан
            и дайджест не отправлялся за последние 23 часа.
        """
        if user.digest_time is None or user.telegram_chat_id is None:
            return False
        if force:
            return True

        try:
            tz = ZoneInfo(user.digest_tz or "Europe/Moscow")
        except (ZoneInfoNotFoundError, Exception):
            tz = ZoneInfo("Europe/Moscow")

        now_local = now_utc.astimezone(tz)
        now_minutes = now_local.hour * 60 + now_local.minute
        user_minutes = user.digest_time.hour * 60 + user.digest_time.minute

        diff = abs(now_minutes - user_minutes)
        diff = min(diff, 24 * 60 - diff)  # Переход через полночь

        if diff > 1:
            return False

        # Проверка: не было ли уже дайджеста за последние 23 часа
        recent = await self._db.scalar(
            select(func.count(Outbox.id)).where(
                Outbox.user_id == user.id,
                Outbox.created_at >= now_utc - timedelta(hours=23),
            )
        )
        return (recent or 0) == 0

    async def get_template(self) -> str:
        """Возвращает пользовательский шаблон дайджеста или шаблон по умолчанию."""
        row = await self._db.scalar(select(DigestTemplate).where(DigestTemplate.id == 1))
        if row and row.template_text.strip():
            return row.template_text
        return _DEFAULT_DIGEST_TEMPLATE

    async def update_template(self, template: str) -> str:
        """Сохраняет шаблон дайджеста после валидации."""
        cleaned = (template or "").strip()
        if not cleaned:
            cleaned = _DEFAULT_DIGEST_TEMPLATE
        self.validate_template(cleaned)

        row = await self._db.scalar(select(DigestTemplate).where(DigestTemplate.id == 1))
        if row is None:
            row = DigestTemplate(id=1, template_text=cleaned)
            self._db.add(row)
        else:
            row.template_text = cleaned
            row.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        return cleaned

    async def _find_new_lots(
        self, saved_filter: SavedFilter, user_id: int
    ) -> list[Lot]:
        """Ищет лоты, подходящие под фильтр, которые ещё не логировались как уведомлённые.

        Args:
            saved_filter: Сохранённый фильтр пользователя.
            user_id: ID пользователя.

        Returns:
            Список лотов (не более _MAX_LOTS_PER_FILTER).
        """
        params: dict[str, Any] = saved_filter.filter or {}

        already_sent = select(NotificationLog.lot_id).where(
            NotificationLog.user_id == user_id,
            NotificationLog.filter_id == saved_filter.id,
        )

        stmt = select(Lot).where(Lot.id.not_in(already_sent))

        if params.get("category"):
            stmt = stmt.where(Lot.category == params["category"])
        if params.get("region"):
            stmt = stmt.where(Lot.region_code == params["region"])
        if params.get("price_from") is not None:
            stmt = stmt.where(Lot.price >= Decimal(str(params["price_from"])))
        if params.get("price_to") is not None:
            stmt = stmt.where(Lot.price <= Decimal(str(params["price_to"])))

        stmt = stmt.order_by(Lot.first_seen_at.desc()).limit(_MAX_LOTS_PER_FILTER)

        return list((await self._db.scalars(stmt)).all())

    @staticmethod
    def validate_template(template: str) -> None:
        """Проверяет допустимость плейсхолдеров шаблона."""
        used_keys = {
            field_name
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name
        }
        unknown = sorted(used_keys - _DIGEST_TEMPLATE_KEYS)
        if unknown:
            raise ValueError(
                "Неизвестные плейсхолдеры: "
                + ", ".join("{" + x + "}" for x in unknown)
            )

    def _format_message(self, filter_name: str, lots: list[Lot], *, template: str) -> str:
        """Форматирует текст сообщения для Telegram.

        Args:
            filter_name: Название фильтра пользователя.
            lots: Список новых лотов.

        Returns:
            Многострочный текст, совместимый с Telegram MarkdownV1.
        """
        lines: list[str] = []

        for i, lot in enumerate(lots, 1):
            if lot.price is not None:
                price_str = f"{lot.price:,.2f} ₽".replace(",", " ")
            else:
                price_str = "Цена не указана"

            lot_url = f"{settings.FRONTEND_BASE_URL}/lot.html?id={lot.id}"
            lines.append(f"{i}. {lot.title}")
            lines.append(f"   {price_str}")
            lines.append(f"   {lot_url}")
            lines.append("")

        lots_block = "\n".join(lines).rstrip()
        return template.format(
            filter_name=filter_name,
            lots_count=len(lots),
            lots=lots_block,
        ).rstrip()
