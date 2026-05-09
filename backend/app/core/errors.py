"""Классы бизнес-исключений приложения.

Каждый класс соответствует HTTP-коду и error code из контракта §2.1.
"""


class AppError(Exception):
    """Базовый класс бизнес-исключения приложения."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    default_message: str = "Внутренняя ошибка"

    def __init__(self, message: str | None = None, code: str | None = None) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class NotFound(AppError):
    """Ресурс не найден."""

    code = "NOT_FOUND"
    status_code = 404
    default_message = "Ресурс не найден"


class Unauthorized(AppError):
    """Не авторизован или невалидные учётные данные."""

    code = "UNAUTHORIZED"
    status_code = 401
    default_message = "Требуется авторизация"


class Forbidden(AppError):
    """Доступ запрещён."""

    code = "FORBIDDEN"
    status_code = 403
    default_message = "Доступ запрещён"


class Conflict(AppError):
    """Конфликт данных (например, дубликат email)."""

    code = "CONFLICT"
    status_code = 409
    default_message = "Конфликт данных"


class ValidationFailed(AppError):
    """Ошибка валидации входных данных."""

    code = "VALIDATION_ERROR"
    status_code = 422
    default_message = "Ошибка валидации"


class BadRequest(AppError):
    """Некорректный запрос (400)."""

    code = "VALIDATION_ERROR"
    status_code = 400
    default_message = "Некорректный запрос"


class RequestTimeout(AppError):
    """Превышено время ожидания (408)."""

    code = "SQL_TIMEOUT"
    status_code = 408
    default_message = "Превышено время выполнения запроса"
