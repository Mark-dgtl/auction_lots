"""Пакет парсинга лотов с электронных торговых площадок.

Содержит абстрактный интерфейс :class:`BaseSource` и его реализации
(`EfrsbSource`, `TorgiSource`). Все источники возвращают лоты в едином
формате :class:`ParsedLot`, который потом принимает backend.
"""

from parser.base import BaseSource, ParsedLot, ParseFilters, CATEGORY_SLUGS

__all__ = [
    "BaseSource",
    "ParsedLot",
    "ParseFilters",
    "CATEGORY_SLUGS",
]
