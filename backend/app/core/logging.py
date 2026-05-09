"""Настройка логирования приложения.

Все сообщения — на русском языке.
Формат: %(asctime)s %(levelname)s %(name)s: %(message)s
"""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Настраивает базовое логирование приложения.

    Args:
        level: Уровень логирования (по умолчанию INFO).
    """
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("app").setLevel(level)
    logging.getLogger("parser").setLevel(level)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)
