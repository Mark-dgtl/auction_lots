"""Прокси изображений лотов (кэш на диске, один origin для фронта)."""

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.errors import BadRequest
from app.services.media_proxy import fetch_cached_image, is_allowed_image_url

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/image")
async def proxy_image(
    url: str = Query(..., min_length=8, max_length=4096, description="Исходный HTTPS URL"),
) -> Response:
    """Отдаёт изображение с доверенного хоста через локальный кэш.

    Повторные запросы по тому же URL читаются с диска — браузер не ходит
  на медленные внешние площадки.
    """
    if not is_allowed_image_url(url):
        raise BadRequest("Некорректный URL изображения")

    body, content_type = await fetch_cached_image(url)
    return Response(
        content=body,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=604800, immutable",
        },
    )
