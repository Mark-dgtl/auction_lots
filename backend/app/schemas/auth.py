"""Схемы аутентификации и данных пользователя."""

from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Тело запроса регистрации."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """Проверяет минимальную длину пароля."""
        if len(v) < 8:
            raise ValueError("Пароль должен содержать не менее 8 символов")
        return v


class LoginRequest(BaseModel):
    """Тело запроса входа."""

    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    """Ответ на успешную регистрацию."""

    id: int
    email: str


class TokenResponse(BaseModel):
    """Ответ с access-токеном."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # секунды до истечения access-токена


class MeResponse(BaseModel):
    """Данные текущего пользователя (GET /api/me)."""

    id: int
    email: str
    telegram_linked: bool
    digest_time: Optional[str]  # "HH:MM" или null
    is_admin: bool = False
