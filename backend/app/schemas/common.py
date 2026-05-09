"""Общие схемы: ошибки, пагинация."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Детали ошибки."""

    code: str
    message: str


class ErrorEnvelope(BaseModel):
    """Конверт ошибки согласно §2.1 контракта.

    Example::

        {"error": {"code": "NOT_FOUND", "message": "Ресурс не найден"}}
    """

    error: ErrorDetail


class Pagination(BaseModel):
    """Параметры пагинации в ответе."""

    total: int
    page: int
    page_size: int
