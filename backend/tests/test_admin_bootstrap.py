"""Тесты bootstrap администратора."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_bootstrap import bootstrap_admin_if_needed
from app.core.config import settings
from app.models.user import User


@pytest.mark.asyncio
async def test_bootstrap_creates_admin(engine):
    """Bootstrap создаёт нового администратора, если в БД нет ни одного."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    settings.ADMIN_BOOTSTRAP_ENABLED = True
    settings.ADMIN_EMAIL = "bootstrap@example.com"
    settings.ADMIN_PASSWORD = "bootstrap_password_123"

    factory = async_sessionmaker(engine, expire_on_commit=False)
    await bootstrap_admin_if_needed(factory)

    async with factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "bootstrap@example.com")
        )
        assert user is not None
        assert user.is_admin is True

    # Сброс настроек
    settings.ADMIN_EMAIL = None
    settings.ADMIN_PASSWORD = None


@pytest.mark.asyncio
async def test_bootstrap_idempotent(engine):
    """Повторный вызов bootstrap не создаёт второго администратора."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    settings.ADMIN_BOOTSTRAP_ENABLED = True
    settings.ADMIN_EMAIL = "idem@example.com"
    settings.ADMIN_PASSWORD = "password_12345"

    factory = async_sessionmaker(engine, expire_on_commit=False)
    await bootstrap_admin_if_needed(factory)
    await bootstrap_admin_if_needed(factory)

    async with factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        assert count == 1

    settings.ADMIN_EMAIL = None
    settings.ADMIN_PASSWORD = None


@pytest.mark.asyncio
async def test_bootstrap_promotes_existing_user(engine):
    """Bootstrap повышает существующего пользователя до admin."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from passlib.context import CryptContext

    settings.ADMIN_BOOTSTRAP_ENABLED = True
    settings.ADMIN_EMAIL = "existing@example.com"
    settings.ADMIN_PASSWORD = "password_12345"

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Создаём обычного пользователя заранее
    async with factory() as session:
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password_12345")
        session.add(User(email="existing@example.com", password_hash=pwd))
        await session.commit()

    await bootstrap_admin_if_needed(factory)

    async with factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "existing@example.com")
        )
        assert user.is_admin is True

    settings.ADMIN_EMAIL = None
    settings.ADMIN_PASSWORD = None


@pytest.mark.asyncio
async def test_bootstrap_does_not_demote(engine):
    """Bootstrap не понижает уже существующих администраторов."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from passlib.context import CryptContext

    settings.ADMIN_BOOTSTRAP_ENABLED = True
    settings.ADMIN_EMAIL = "new_admin@example.com"
    settings.ADMIN_PASSWORD = "password_12345"

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Создаём существующего администратора
    async with factory() as session:
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("pass")
        session.add(User(email="original@example.com", password_hash=pwd, is_admin=True))
        await session.commit()

    # Bootstrap не должен ничего делать (уже есть admin)
    await bootstrap_admin_if_needed(factory)

    async with factory() as session:
        original = await session.scalar(
            select(User).where(User.email == "original@example.com")
        )
        assert original.is_admin is True

        # Новый пользователь не должен быть создан
        new_user = await session.scalar(
            select(User).where(User.email == "new_admin@example.com")
        )
        assert new_user is None

    settings.ADMIN_EMAIL = None
    settings.ADMIN_PASSWORD = None
