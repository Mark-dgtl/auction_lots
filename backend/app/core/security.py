"""Безопасность: хэши паролей и JWT-токены.

Использует passlib/bcrypt для паролей и python-jose для JWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    """Хэширует пароль через bcrypt.

    Args:
        plain: Открытый пароль.

    Returns:
        bcrypt-хэш пароля.
    """
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяет открытый пароль против bcrypt-хэша.

    Args:
        plain: Открытый пароль.
        hashed: bcrypt-хэш для сравнения.

    Returns:
        True если пароль совпадает.
    """
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(subject: int | str) -> tuple[str, datetime]:
    """Создаёт access JWT-токен.

    Args:
        subject: Идентификатор пользователя.

    Returns:
        Кортеж (токен, время истечения).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TTL_MINUTES
    )
    data: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "exp": expire,
    }
    token = jwt.encode(data, settings.JWT_SECRET, algorithm=ALGORITHM)
    return token, expire


def create_refresh_token(subject: int | str) -> tuple[str, str, datetime]:
    """Создаёт refresh JWT-токен.

    Args:
        subject: Идентификатор пользователя.

    Returns:
        Кортеж (токен, jti, время истечения).
    """
    jti = str(uuid4())
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TTL_DAYS
    )
    data: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "jti": jti,
        "exp": expire,
    }
    token = jwt.encode(data, settings.JWT_SECRET, algorithm=ALGORITHM)
    return token, jti, expire


def decode_token(token: str) -> dict[str, Any]:
    """Декодирует JWT-токен.

    Args:
        token: JWT-токен для декодирования.

    Returns:
        Payload токена.

    Raises:
        jose.JWTError: При невалидном или истёкшем токене.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
