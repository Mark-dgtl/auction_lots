"""Тесты прокси изображений."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.media_proxy import is_allowed_image_url


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://torgi.gov.ru/new/file-store/v1/abc", True),
        ("https://bankrot.fedresurs.ru/path/pic.jpg", True),
        ("https://cdn.example.com/x.jpg", False),
        ("http://torgi.gov.ru/x.jpg", False),
    ],
)
def test_is_allowed_image_url(url: str, ok: bool) -> None:
    assert is_allowed_image_url(url) is ok


@pytest.mark.asyncio
async def test_proxy_image_rejects_bad_host(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/media/image",
        params={"url": "https://evil.example/1.jpg"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_proxy_image_serves_cached(client: AsyncClient) -> None:
    url = "https://torgi.gov.ru/new/file-store/v1/test-id"
    fake_body = b"\xff\xd8\xff fake jpeg"
    with patch(
        "app.api.media.fetch_cached_image",
        new=AsyncMock(return_value=(fake_body, "image/jpeg")),
    ):
        resp = await client.get("/api/media/image", params={"url": url})
    assert resp.status_code == 200
    assert resp.content == fake_body
    assert resp.headers["content-type"].startswith("image/jpeg")
    assert "max-age" in resp.headers.get("cache-control", "")
