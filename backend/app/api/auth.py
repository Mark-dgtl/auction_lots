"""Роутер аутентификации: регистрация, вход, обновление и выход."""

import logging

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import Unauthorized
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.auth")

_REFRESH_COOKIE = "refresh_token"
_REFRESH_COOKIE_PATH = "/api/auth"


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Регистрирует нового пользователя.

    Args:
        body: Email и пароль (минимум 8 символов).

    Returns:
        id и email созданного пользователя.
    """
    svc = AuthService(db)
    user = await svc.register(body.email, body.password)
    return RegisterResponse(id=user.id, email=str(user.email))


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Выполняет вход в систему.

    Устанавливает HttpOnly cookie refresh_token (SameSite=Lax, Path=/api/auth).

    Args:
        body: Email и пароль.
        response: FastAPI Response для установки cookie.

    Returns:
        access_token, token_type и expires_in.
    """
    svc = AuthService(db)
    _user, access_token, refresh_token, _expires = await svc.login(
        body.email, body.password
    )

    max_age = settings.JWT_REFRESH_TTL_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=max_age,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TTL_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Выдаёт новый access-токен по refresh-токену из cookie.

    Args:
        refresh_token: Значение cookie refresh_token.

    Returns:
        Новый access_token и expires_in.
    """
    if not refresh_token:
        raise Unauthorized("Refresh-токен не найден")

    svc = AuthService(db)
    access_token, _ = await svc.refresh(refresh_token)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TTL_MINUTES * 60,
    )


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Выход из системы. Отзывает refresh-токен и удаляет cookie.

    Args:
        response: FastAPI Response для удаления cookie.
        refresh_token: Значение cookie refresh_token.
    """
    if refresh_token:
        svc = AuthService(db)
        await svc.logout(refresh_token)

    response.delete_cookie(key=_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)
