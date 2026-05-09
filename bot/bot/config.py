"""Конфигурация Telegram-бота через pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота из переменных окружения / .env.

    Attributes:
        TELEGRAM_BOT_TOKEN: Токен бота из @BotFather. Если пуст — бот не запускается.
        BACKEND_INTERNAL_URL: Базовый URL backend (без trailing slash).
        INTERNAL_API_TOKEN: Shared secret для X-Internal-Token заголовка.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TELEGRAM_BOT_TOKEN: str = ""
    BACKEND_INTERNAL_URL: str = "http://localhost:8000"
    INTERNAL_API_TOKEN: str = "change-me-internal-token"


settings = Settings()
