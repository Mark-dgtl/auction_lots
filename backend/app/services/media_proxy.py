"""Локальный кэш изображений лотов (папка проекта data/lot_images)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

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


def cache_path_for_url(url: str) -> Path:
    """Путь к файлам кэша для URL (без расширения — рядом .bin и .meta)."""
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return settings.resolved_media_cache_dir() / key[:2] / key


def is_image_cached(url: str) -> bool:
    """True, если изображение уже лежит на диске."""
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


async def prefetch_image_url(url: str) -> bool:
    """Скачивает изображение в локальный кэш. Не бросает исключения наружу."""
    if not is_allowed_image_url(url):
        return False
    if is_image_cached(url):
        return True

    cache = cache_path_for_url(url)
    try:
        body, content_type = await _download_image(url)
        _write_cache(cache, body, content_type)
        return True
    except Exception as exc:
        logger.warning("Не удалось закэшировать %s: %s", url, exc)
        return False


async def fetch_cached_image(url: str) -> tuple[bytes, str]:
    """Отдаёт изображение с диска или качает с источника (для /api/media/image)."""
    if not is_allowed_image_url(url):
        raise Forbidden("URL изображения не разрешён")

    cache = cache_path_for_url(url)
    cached = _read_cache(cache)
    if cached is not None:
        return cached

    try:
        body, content_type = await _download_image(url)
    except httpx.HTTPError as exc:
        logger.warning("Прокси изображения: ошибка загрузки %s: %s", url, exc)
        raise UpstreamError("Не удалось загрузить изображение") from exc

    try:
        _write_cache(cache, body, content_type)
    except OSError as exc:
        logger.warning("Не удалось записать кэш %s: %s", cache, exc)

    return body, content_type
