"""Конфигурация приложения через pydantic-settings.

Читает все переменные из .env-файла или окружения.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень репозитория (родитель каталога backend/).
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Настройки приложения, читаемые из переменных окружения.

    Attributes:
        DATABASE_URL: URL подключения к PostgreSQL (asyncpg).
        JWT_SECRET: Секрет для подписи JWT-токенов.
        JWT_ACCESS_TTL_MINUTES: Время жизни access-токена в минутах.
        JWT_REFRESH_TTL_DAYS: Время жизни refresh-токена в днях.
        INTERNAL_API_TOKEN: Shared secret для внутреннего API бот↔backend.
        CORS_ORIGINS: Разрешённые CORS-источники через запятую.
        PARSER_INTERVAL_MINUTES: Интервал запуска парсера в минутах.
        PARSER_SOURCES: Список источников через запятую.
        TELEGRAM_BOT_USERNAME: Username Telegram-бота (без @).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://tenders:tenders@localhost:5432/tenders"
    JWT_SECRET: str = "change-me-in-production-please"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 14
    INTERNAL_API_TOKEN: str = "change-me-internal-token"
    CORS_ORIGINS: str = "http://localhost:8080,http://127.0.0.1:8080"
    PARSER_INTERVAL_MINUTES: int = 30
    PARSER_SOURCES: str = "efrsb,torgi_gov"
    TELEGRAM_BOT_USERNAME: str = "your_bot_username"
    SCHEDULER_ENABLED: bool = True
    DIGEST_CHECK_INTERVAL_MINUTES: int = 1
    FRONTEND_BASE_URL: str = "http://localhost:8080"

    # M4: Admin
    ADMIN_BOOTSTRAP_ENABLED: bool = True
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    ADMIN_LOG_BUFFER_SIZE: int = 2000
    ADMIN_BOT_OFFLINE_THRESHOLD_SECONDS: int = 120
    APP_VERSION: str = "1.0.0"

    # Локальный кэш фото лотов (по умолчанию <корень проекта>/data/lot_images)
    MEDIA_CACHE_DIR: str = "data/lot_images"
    MEDIA_PROXY_TIMEOUT_SECONDS: float = 25.0
    MEDIA_PREFETCH_CONCURRENCY: int = 6
    MEDIA_WARM_ON_STARTUP: bool = True
    MEDIA_WARM_STARTUP_DELAY_SECONDS: float = 20.0
    MEDIA_WARM_BATCH_SIZE: int = 80

    def resolved_media_cache_dir(self) -> Path:
        """Абсолютный путь к каталогу кэша изображений."""
        p = Path(self.MEDIA_CACHE_DIR)
        if p.is_absolute():
            return p
        return (_REPO_ROOT / p).resolve()


settings = Settings()
