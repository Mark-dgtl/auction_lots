"""Базовый класс для всех SQLAlchemy-моделей."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый декларативный класс ORM.

    Все модели приложения наследуются от этого класса.
    """
