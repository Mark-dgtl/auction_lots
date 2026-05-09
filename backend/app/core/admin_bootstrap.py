"""Автоматическое создание первого администратора при старте.

Запускается один раз в lifespan FastAPI перед стартом планировщика.
Идемпотентно — никогда не понижает права существующих администраторов.
"""

import logging

from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger("app.admin.bootstrap")
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def bootstrap_admin_if_needed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Создаёт или повышает первого администратора, если его ещё нет.

    Проверяет настройки ADMIN_BOOTSTRAP_ENABLED, ADMIN_EMAIL, ADMIN_PASSWORD.
    Если ни одного администратора в БД нет — создаёт или повышает пользователя.
    Никогда не понижает уже существующих администраторов.

    Args:
        session_factory: Фабрика асинхронных сессий SQLAlchemy.
    """
    if not settings.ADMIN_BOOTSTRAP_ENABLED:
        logger.info("Bootstrap администратора отключён (ADMIN_BOOTSTRAP_ENABLED=false)")
        return

    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        logger.info(
            "Bootstrap администратора пропущен: ADMIN_EMAIL или ADMIN_PASSWORD не заданы"
        )
        return

    async with session_factory() as session:
        admin_count = await session.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        if admin_count and admin_count > 0:
            logger.info(
                "Bootstrap администратора пропущен: в системе уже есть %d администратор(ов)",
                admin_count,
            )
            return

        existing = await session.scalar(
            select(User).where(User.email == settings.ADMIN_EMAIL.lower())
        )

        if existing:
            existing.is_admin = True
            await session.commit()
            logger.info(
                "Bootstrap: пользователь '%s' (id=%d) повышен до администратора",
                settings.ADMIN_EMAIL,
                existing.id,
            )
        else:
            pw_hash = _pwd_ctx.hash(settings.ADMIN_PASSWORD)
            new_admin = User(
                email=settings.ADMIN_EMAIL.lower(),
                password_hash=pw_hash,
                is_admin=True,
            )
            session.add(new_admin)
            await session.commit()
            logger.info(
                "Bootstrap: создан новый администратор '%s'",
                settings.ADMIN_EMAIL,
            )
