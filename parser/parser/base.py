"""Базовые типы и абстракции парсер-пакета.

Этот модуль является источником правды по формату данных между парсером
и backend. Любые изменения согласовываются через оркестратор и документ
``docs/CONTRACTS.md``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncIterator

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


CATEGORY_SLUGS: dict[str, str] = {
    "real_estate": "Недвижимость",
    "vehicle": "Транспорт",
    "equipment": "Оборудование",
    "land": "Земельные участки",
    "rights": "Права требования",
    "securities": "Ценные бумаги",
    "inventory": "ТМЦ и материалы",
    "other": "Прочее",
}
"""Словарь допустимых slug-ов категорий. Парсер обязан приводить
исходные категории источника к одному из этих значений либо к ``None``."""


class ParseFilters(BaseModel):
    """Фильтры запроса к источнику.

    Атрибуты:
        query: Поисковая строка (по заголовку/описанию, если поддерживается).
        category: Slug категории из :data:`CATEGORY_SLUGS`.
        region: Код ОКАТО региона или его часть.
        price_from: Нижняя граница цены (рубли).
        price_to: Верхняя граница цены (рубли).
    """

    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    category: str | None = None
    region: str | None = None
    price_from: Decimal | None = None
    price_to: Decimal | None = None


class ParsedLot(BaseModel):
    """Нормализованный лот, который парсер передаёт backend.

    Все timezone-aware поля должны быть в UTC. Цены — в рублях.
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., description="Идентификатор источника, например 'efrsb'.")
    source_lot_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=1000)
    description: str | None = None
    category: str | None = Field(
        default=None,
        description="Slug из CATEGORY_SLUGS или None, если категория не определена.",
    )
    region: str | None = Field(
        default=None,
        description="Код ОКАТО или название региона (нормализуется backend).",
    )
    price: Decimal | None = None
    price_step: Decimal | None = None
    source_url: HttpUrl
    auction_date: datetime | None = None
    published_at: datetime | None = None
    status: str | None = None
    images: list[HttpUrl] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class BaseSource(ABC):
    """Абстракция источника лотов.

    Каждая реализация отвечает за:
      * получение страниц источника (HTTP/JSON/HTML);
      * извлечение и нормализацию полей;
      * постраничный обход списка лотов с учётом ``since``/``filters``;
      * логирование на русском языке (см. ``docs/CONTRACTS.md`` §1.5).
    """

    #: Уникальное имя источника; используется как значение ``ParsedLot.source``.
    name: str

    @abstractmethod
    def fetch_lots(
        self,
        since: datetime | None = None,
        filters: ParseFilters | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[ParsedLot]:
        """Асинхронный генератор лотов.

        Args:
            since: Если задано, источник должен вернуть только лоты, обновлённые
                после этой даты (если источник позволяет так фильтровать).
            filters: Дополнительные фильтры (см. :class:`ParseFilters`).
            limit: Жёсткий верхний предел количества возвращённых лотов. ``None``
                означает «без ограничения».

        Yields:
            ParsedLot: Очередной нормализованный лот.
        """
        raise NotImplementedError

    def get_run_telemetry(self) -> dict[str, Any]:
        """Возвращает телеметрию последнего запуска источника.

        Источник может вернуть пустой словарь, если телеметрия не поддерживается.
        Ожидаемые ключи для UI/мониторинга:
        - pages_fetched
        - expected_total_elements
        - yielded_total
        - skipped_invalid
        - full_scan_completed
        """
        return {}
