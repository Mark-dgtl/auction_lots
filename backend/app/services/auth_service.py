"""Сервис аутентификации и управления пользователями."""

import logging
from datetime import datetime, timezone

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger("app.auth")


class AuthService:
    """Сервис регистрации, входа и управления токенами.

    Args:
        db: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def register(self, email: str, password: str) -> User:
        """Регистрирует нового пользователя.

        Args:
            email: Email пользователя (будет приведён к нижнему регистру).
            password: Открытый пароль (минимум 8 символов).

        Returns:
            Созданный объект пользователя.

        Raises:
            Conflict: Если пользователь с таким email уже существует.
        """
        lower_email = email.lower()
        existing = await self._db.scalar(
            select(User).where(User.email == lower_email)
        )
        if existing:
            raise Conflict("Пользователь с таким email уже существует")

        user = User(email=lower_email, password_hash=hash_password(password))
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        logger.info("Зарегистрирован новый пользователь id=%s", user.id)
        return user

    async def login(
        self, email: str, password: str
    ) -> tuple[User, str, str, datetime]:
        """Выполняет вход пользователя в систему.

        Args:
            email: Email пользователя.
            password: Открытый пароль.

        Returns:
            Кортеж (пользователь, access_token, refresh_token, refresh_expires_at).

        Raises:
            Unauthorized: При неверных учётных данных.
        """
        user = await self._db.scalar(
            select(User).where(User.email == email.lower())
        )
        if not user or not verify_password(password, user.password_hash):
            raise Unauthorized("Неверный email или пароль")

        access_token, _ = create_access_token(user.id)
        refresh_token_str, jti, expires_at = create_refresh_token(user.id)

        rt = RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at)
        self._db.add(rt)
        await self._db.commit()

        logger.info("Пользователь id=%s выполнил вход", user.id)
        return user, access_token, refresh_token_str, expires_at

    async def refresh(self, refresh_token_str: str) -> tuple[str, datetime]:
        """Выдаёт новый access-токен по действующему refresh-токену.

        Args:
            refresh_token_str: Refresh JWT-токен.

        Returns:
            Кортеж (новый access_token, expires_at).

        Raises:
            Unauthorized: Если токен невалидный, отозван или истёк.
        """
        try:
            payload = decode_token(refresh_token_str)
        except JWTError:
            raise Unauthorized("Недействительный refresh-токен")

        if payload.get("type") != "refresh":
            raise Unauthorized("Недействительный тип токена")

        jti = payload.get("jti")
        rt = await self._db.scalar(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )

        if not rt or rt.revoked_at is not None:
            raise Unauthorized("Токен отозван или не существует")

        if rt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise Unauthorized("Refresh-токен истёк")

        access_token, expires_at = create_access_token(rt.user_id)
        logger.info("Обновлён access-токен для пользователя id=%s", rt.user_id)
        return access_token, expires_at

    async def logout(self, refresh_token_str: str) -> None:
        """Отзывает refresh-токен (выход из системы).

        Args:
            refresh_token_str: Refresh JWT-токен для отзыва.
        """
        try:
            payload = decode_token(refresh_token_str)
            jti = payload.get("jti")
            if jti:
                rt = await self._db.scalar(
                    select(RefreshToken).where(RefreshToken.jti == jti)
                )
                if rt and rt.revoked_at is None:
                    rt.revoked_at = datetime.now(timezone.utc)
                    await self._db.commit()
        except JWTError:
            pass  # Уже невалидный токен — просто игнорируем
        logger.info("Выполнен выход из системы")

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Возвращает пользователя по первичному ключу.

        Args:
            user_id: ID пользователя.

        Returns:
            Объект User или None, если не найден.
        """
        return await self._db.scalar(select(User).where(User.id == user_id))
