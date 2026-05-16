"""Тесты предзагрузки изображений."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.media_prefetch import prefetch_urls
from app.services.media_proxy import is_image_cached, prefetch_image_url


@pytest.fixture
def media_cache_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "lot_images"
    monkeypatch.setattr(settings, "MEDIA_CACHE_DIR", str(cache))
    return cache


@pytest.mark.asyncio
async def test_prefetch_image_url_caches_file(media_cache_tmp: Path) -> None:
    url = "https://torgi.gov.ru/new/file-store/v1/abc"
    body = b"\xff\xd8\xff"
    with patch(
        "app.services.media_proxy._download_image",
        new=AsyncMock(return_value=(body, "image/jpeg")),
    ):
        assert await prefetch_image_url(url) is True
    assert is_image_cached(url)


@pytest.mark.asyncio
async def test_prefetch_urls_skips_already_cached(media_cache_tmp: Path) -> None:
    url = "https://torgi.gov.ru/new/file-store/v1/cached"
    body = b"\x89PNG"
    with patch(
        "app.services.media_proxy._download_image",
        new=AsyncMock(return_value=(body, "image/png")),
    ):
        assert await prefetch_image_url(url) is True
        download = AsyncMock(return_value=(body, "image/png"))
        with patch("app.services.media_proxy._download_image", new=download):
            ok, fail = await prefetch_urls([url, url])
    assert ok == 1
    assert fail == 0
    download.assert_not_called()
