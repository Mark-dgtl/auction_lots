"""Прокси изображений лотов (кэш на диске, превью WebP)."""

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, Response

from app.core.errors import BadRequest
from app.services.media_proxy import (
    cache_response_headers,
    ensure_thumbnail,
    fetch_cached_image,
    is_allowed_image_url,
    thumb_path_for_url,
)

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/image")
async def proxy_image(
    url: str = Query(..., min_length=8, max_length=4096, description="Исходный HTTPS URL"),
    variant: str = Query(
        "thumb",
        pattern="^(thumb|full)$",
        description="thumb — превью для ленты, full — оригинал",
    ),
) -> Response:
    """Отдаёт изображение с доверенного хоста через локальный кэш (FileResponse)."""
    if not is_allowed_image_url(url):
        raise BadRequest("Некорректный URL изображения")

    headers = cache_response_headers()

    if variant == "thumb":
        thumb = thumb_path_for_url(url)
        if thumb.is_file():
            return FileResponse(
                thumb,
                media_type="image/webp",
                headers=headers,
            )

    body, content_type, file_path = await fetch_cached_image(url)
    ensure_thumbnail(url, body)

    if variant == "thumb":
        thumb = thumb_path_for_url(url)
        if thumb.is_file():
            return FileResponse(thumb, media_type="image/webp", headers=headers)

    if file_path and file_path.is_file():
        return FileResponse(file_path, media_type=content_type, headers=headers)

    return Response(content=body, media_type=content_type, headers=headers)
