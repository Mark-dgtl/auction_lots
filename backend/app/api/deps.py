"""Зависимости (dependencies) FastAPI для повторного использования."""

import logging

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger("app.deps")

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Извлекает текущего пользователя из Bearer-токена.

    Обязательная зависимость — выбрасывает Unauthorized если токен отсутствует или невалиден.

    Args:
        credentials: HTTP Authorization credentials.
        db: Сессия базы данных.

    Returns:
        Объект User текущего пользователя.

    Raises:
        Unauthorized: Если токен отсутствует, невалиден или пользователь не найден.
    """
    if not credentials:
        raise Unauthorized("Требуется авторизация")

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise Unauthorized("Недействительный access-токен")

    if payload.get("type") != "access":
        raise Unauthorized("Недействительный тип токена")

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise Unauthorized("Недействительный payload токена")

    svc = AuthService(db)
    user = await svc.get_user_by_id(user_id)
    if not user:
        raise Unauthorized("Пользователь не найден")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Извлекает текущего пользователя если передан Bearer-токен, иначе возвращает None.

    Используется для эндпоинтов с опциональной авторизацией (GET /api/lots).

    Args:
        credentials: HTTP Authorization credentials (опционально).
        db: Сессия базы данных.

    Returns:
        Объект User или None.
    """
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        user_id = int(payload["sub"])
        svc = AuthService(db)
        return await svc.get_user_by_id(user_id)
    except (JWTError, KeyError, ValueError):
        return None


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Проверяет, что текущий пользователь является администратором.

    Args:
        user: Текущий пользователь из Bearer-токена.

    Returns:
        Пользователь-администратор.

    Raises:
        Forbidden: Если пользователь заблокирован (USER_BLOCKED) или не является администратором (NOT_ADMIN).
    """
    if user.is_blocked:
        raise Forbidden("Пользователь заблокирован", code="USER_BLOCKED")
    if not user.is_admin:
        raise Forbidden("Требуются права администратора", code="NOT_ADMIN")
    return user


async def require_internal_token(
    x_internal_token: str | None = Header(
        default=None, alias="X-Internal-Token"
    ),
) -> None:
    """Проверяет shared secret для внутреннего API /api/internal/*.

    Args:
        x_internal_token: Значение заголовка X-Internal-Token.

    Raises:
        Forbidden: Если токен отсутствует или неверен.
    """
    if x_internal_token != settings.INTERNAL_API_TOKEN:
        raise Forbidden("Недействительный внутренний токен")
