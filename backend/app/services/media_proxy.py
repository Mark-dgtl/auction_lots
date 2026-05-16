"""Локальный кэш изображений лотов (полный файл + WebP-превью для ленты)."""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings
from app.core.errors import Forbidden, UpstreamError

logger = logging.getLogger("app.media")

_ALLOWED_HOST_SUFFIXES: tuple[str, ...] = (
    "torgi.gov.ru",
    "bankrot.fedresurs.ru",
    "fedresurs.ru",
)

_MAX_IMAGE_BYTES = 12 * 1024 * 1024
_CACHE_HEADERS = {"Cache-Control": "public, max-age=604800, immutable"}


def is_allowed_image_url(url: str) -> bool:
    """Проверяет, что URL — https и с доверенного хоста."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in _ALLOWED_HOST_SUFFIXES
    )


def cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def cache_path_for_url(url: str) -> Path:
    """Базовый путь кэша без расширения: data/lot_images/ab/<hash>."""
    key = cache_key(url)
    return settings.resolved_media_cache_dir() / key[:2] / key


def thumb_path_for_url(url: str) -> Path:
    base = cache_path_for_url(url)
    return base.parent / f"{base.name}.thumb.webp"


def public_thumb_url(url: str) -> str:
    """Прямой URL для nginx (без Python), отдаёт .thumb.webp."""
    key = cache_key(url)
    return f"/media/cache/{key[:2]}/{key}.thumb.webp"


def public_api_image_url(url: str, *, variant: str = "thumb") -> str:
    return f"/api/media/image?url={quote(url, safe='')}&variant={variant}"


def resolve_feed_thumbnail(external_url: str | None) -> str | None:
    """URL превью для ленты: статика nginx, если файл уже в кэше."""
    if not external_url:
        return None
    url = external_url.strip()
    if not url:
        return None
    if not is_allowed_image_url(url):
        return url
    if thumb_path_for_url(url).is_file():
        return public_thumb_url(url)
    return public_api_image_url(url, variant="thumb")


def is_image_cached(url: str) -> bool:
    if not is_allowed_image_url(url):
        return False
    path = cache_path_for_url(url)
    return path.with_suffix(".bin").is_file() and path.with_suffix(".meta").is_file()


def _read_cache(path: Path) -> tuple[bytes, str] | None:
    meta = path.with_suffix(".meta")
    data = path.with_suffix(".bin")
    if not meta.is_file() or not data.is_file():
        return None
    try:
        content_type = meta.read_text(encoding="utf-8").strip()
        body = data.read_bytes()
        if body:
            return body, content_type or "application/octet-stream"
    except OSError as exc:
        logger.warning("Не удалось прочитать кэш %s: %s", path, exc)
    return None


def _write_cache(path: Path, body: bytes, content_type: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = path.with_suffix(".bin")
    meta = path.with_suffix(".meta")
    tmp_data = data.with_suffix(".bin.tmp")
    tmp_meta = meta.with_suffix(".meta.tmp")
    try:
        tmp_data.write_bytes(body)
        tmp_meta.write_text(content_type, encoding="utf-8")
        tmp_data.replace(data)
        tmp_meta.replace(meta)
    except OSError:
        for p in (tmp_data, tmp_meta):
            p.unlink(missing_ok=True)
        raise


def ensure_thumbnail(url: str, body: bytes | None = None) -> bool:
    """Создаёт WebP-превью (~420px) для ленты. Возвращает True при успехе."""
    thumb = thumb_path_for_url(url)
    if thumb.is_file() and thumb.stat().st_size > 0:
        return True

    if body is None:
        cached = _read_cache(cache_path_for_url(url))
        if cached is None:
            return False
        body, _ = cached

    try:
        from PIL import Image

        with Image.open(io.BytesIO(body)) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")
            max_w = settings.MEDIA_THUMB_MAX_WIDTH
            img.thumbnail((max_w, max_w * 2), Image.Resampling.LANCZOS)
            thumb.parent.mkdir(parents=True, exist_ok=True)
            tmp = thumb.with_suffix(".thumb.webp.tmp")
            img.save(
                tmp,
                "WEBP",
                quality=settings.MEDIA_THUMB_QUALITY,
                method=4,
            )
            tmp.replace(thumb)
        return True
    except Exception as exc:
        logger.warning("Не удалось создать превью для %s: %s", url, exc)
        return False


async def _download_image(url: str) -> tuple[bytes, str]:
    timeout = httpx.Timeout(settings.MEDIA_PROXY_TIMEOUT_SECONDS)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; TendersAggregator/1.0; +https://localhost)"
        ),
        "Accept": "image/*,*/*;q=0.8",
    }
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise UpstreamError("Ответ источника не является изображением")

    body = resp.content
    if len(body) > _MAX_IMAGE_BYTES:
        raise UpstreamError("Изображение слишком большое")
    if not body:
        raise UpstreamError("Пустой ответ источника")
    return body, content_type


def store_image(url: str, body: bytes, content_type: str) -> None:
    """Сохраняет полный файл и генерирует превью."""
    cache = cache_path_for_url(url)
    _write_cache(cache, body, content_type)
    ensure_thumbnail(url, body)


async def prefetch_image_url(url: str) -> bool:
    """Скачивает изображение в локальный кэш. Не бросает исключения наружу."""
    if not is_allowed_image_url(url):
        return False
    if is_image_cached(url):
        ensure_thumbnail(url)
        return True

    cache = cache_path_for_url(url)
    try:
        body, content_type = await _download_image(url)
        store_image(url, body, content_type)
        return True
    except Exception as exc:
        logger.warning("Не удалось закэшировать %s: %s", url, exc)
        return False


async def fetch_cached_image(url: str) -> tuple[bytes, str, Path | None]:
    """Возвращает (тело, content-type, путь_к_файлу_или_None для FileResponse)."""
    if not is_allowed_image_url(url):
        raise Forbidden("URL изображения не разрешён")

    cache = cache_path_for_url(url)
    cached = _read_cache(cache)
    if cached is not None:
        return cached[0], cached[1], cache.with_suffix(".bin")

    try:
        body, content_type = await _download_image(url)
    except httpx.HTTPError as exc:
        logger.warning("Прокси изображения: ошибка загрузки %s: %s", url, exc)
        raise UpstreamError("Не удалось загрузить изображение") from exc

    try:
        store_image(url, body, content_type)
    except OSError as exc:
        logger.warning("Не удалось записать кэш %s: %s", cache, exc)

    return body, content_type, cache.with_suffix(".bin")


def cache_response_headers() -> dict[str, str]:
    return dict(_CACHE_HEADERS)
