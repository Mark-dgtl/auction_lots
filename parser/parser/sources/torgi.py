"""Источник лотов torgi.gov.ru (ГИС «Торги»).

Сайт отдаёт публичный JSON API поиска лотов:

    GET https://torgi.gov.ru/new/api/public/lotcards/search

Формат ответа — пагинированный ``Spring``-style:

.. code-block:: json

    {
      "content": [ { /* лот */ }, ... ],
      "totalElements": 12345,
      "totalPages": 1000,
      "size": 10,
      "number": 0,
      "first": true,
      "last": false
    }

Детальная карточка:

    GET https://torgi.gov.ru/new/api/public/lotcards/{id}

Источник пользуется только HTTP, никаких JS-браузеров не требуется.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Final

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from parser.base import BaseSource, ParsedLot, ParseFilters
from parser.normalizer import (
    guess_category,
    normalize_whitespace,
    parse_datetime,
    parse_okato,
    parse_price,
)


_logger = logging.getLogger("parser.torgi_gov")


_API_SEARCH: Final = "https://torgi.gov.ru/new/api/public/lotcards/search"
_LOT_PUBLIC_URL: Final = "https://torgi.gov.ru/new/public/lots/lot/{id}"
_IMAGE_URL: Final = "https://torgi.gov.ru/new/file-store/v1/{file_id}?disposition=inline"

_DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://torgi.gov.ru/new/public/lots/",
}

# Маппинг верхнеуровневых категорий torgi.gov.ru (code из category.code) → slug.
# Порядок не важен, ключ — строковый код, value — slug из CATEGORY_SLUGS.
# Коды из реальных ответов; недостающие ловим по эвристике guess_category().
_CATEGORY_CODE_MAP: Final[dict[str, str]] = {
    # Недвижимость
    "10": "real_estate",       # Недвижимость (зонтичная)
    "11": "real_estate",       # Нежилые помещения
    "12": "real_estate",       # Жилые помещения
    "14": "real_estate",       # Здания, сооружения
    # Транспорт
    "100001": "vehicle",        # Легковые автомобили
    "100002": "vehicle",        # Грузовые автомобили
    "100003": "vehicle",        # Автобусы
    "100004": "vehicle",        # Мототехника
    # Земля
    "20": "land",
    "21": "land",
    # Оборудование / ТМЦ
    "30": "equipment",
    "40": "inventory",
    # Ценные бумаги
    "50": "securities",
    # Права требования
    "60": "rights",
}

_PAGE_SIZE: Final = 20


def _is_retryable_error(exc: BaseException) -> bool:
    """Ретраим только сетевые ошибки и 5xx. 4xx — фатально."""
    if isinstance(exc, (httpx.TransportError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return False


class TorgiSource(BaseSource):
    """Источник лотов torgi.gov.ru (ГИС «Торги»).

    Attributes:
        name: ``"torgi_gov"`` — идентификатор источника.
    """

    name: str = "torgi_gov"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        api_url: str = _API_SEARCH,
        page_size: int = _PAGE_SIZE,
        request_timeout: float = 20.0,
    ) -> None:
        self._external_client = client is not None
        self._client = client
        self._api_url = api_url
        self._page_size = page_size
        self._request_timeout = request_timeout
        self._run_telemetry: dict[str, Any] = {}

    # --- Публичный API ----------------------------------------------------

    async def fetch_lots(
        self,
        since: datetime | None = None,
        filters: ParseFilters | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[ParsedLot]:
        """Асинхронный генератор лотов torgi.gov.ru.

        Args:
            since: Нижняя граница даты публикации (``published_at >= since``).
                Сайт поддерживает фильтр, но мы подстраховываемся проверкой
                уже на стороне клиента.
            filters: Дополнительные фильтры (категория → наш slug, регион → ОКАТО,
                диапазон цены, поисковая строка).
            limit: Жёсткий лимит количества лотов.

        Yields:
            ParsedLot: Очередной нормализованный лот.
        """
        client = self._client or httpx.AsyncClient(
            headers=_DEFAULT_HEADERS,
            timeout=self._request_timeout,
            follow_redirects=True,
        )
        yielded = 0
        skipped_invalid = 0
        pages_fetched = 0
        expected_total_elements: int | None = None
        full_scan_completed = False
        self._run_telemetry = {
            "pages_fetched": 0,
            "expected_total_elements": None,
            "yielded_total": 0,
            "skipped_invalid": 0,
            "full_scan_completed": False,
        }
        try:
            page_number = 0
            while True:
                page = await self._fetch_page(
                    client,
                    page_number=page_number,
                    since=since,
                    filters=filters,
                )
                items: list[dict[str, Any]] = page.get("content") or []
                pages_fetched += 1
                if expected_total_elements is None:
                    total = page.get("totalElements")
                    if isinstance(total, int):
                        expected_total_elements = total
                if not items:
                    _logger.info(
                        "torgi: пустая страница page=%s, завершаем обход",
                        page_number,
                    )
                    break

                _logger.info(
                    "torgi: страница %s, получено %d лотов",
                    page_number,
                    len(items),
                )

                for item in items:
                    lot = self._build_lot(item)
                    if lot is None:
                        skipped_invalid += 1
                        continue
                    if since and lot.published_at and lot.published_at < since:
                        continue
                    yield lot
                    yielded += 1
                    if limit is not None and yielded >= limit:
                        full_scan_completed = False
                        return

                # Нельзя ориентироваться на len(items) < self._page_size: API часто
                # игнорирует запрошенный pageSize и отдаёт, например, 10 записей —
                # тогда обход обрывался после первой страницы (lots_seen всегда ~10).
                if page.get("last") is True:
                    full_scan_completed = True
                    break
                total_pages = page.get("totalPages")
                page_idx = page.get("number")
                if (
                    isinstance(total_pages, int)
                    and isinstance(page_idx, int)
                    and total_pages > 0
                    and page_idx >= total_pages - 1
                ):
                    full_scan_completed = True
                    break
                page_number += 1
        finally:
            self._run_telemetry = {
                "pages_fetched": pages_fetched,
                "expected_total_elements": expected_total_elements,
                "yielded_total": yielded,
                "skipped_invalid": skipped_invalid,
                "full_scan_completed": full_scan_completed and limit is None,
            }
            if not self._external_client and self._client is None:
                await client.aclose()

    def get_run_telemetry(self) -> dict[str, Any]:
        return dict(self._run_telemetry)

    # --- Сетевой слой -----------------------------------------------------

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        *,
        page_number: int,
        since: datetime | None,
        filters: ParseFilters | None,
    ) -> dict[str, Any]:
        """Загружает одну страницу поиска.

        Retries: 3 попытки с экспоненциальным backoff для 5xx и сетевых
        ошибок. 4xx — фатально (мы неправильно сформировали запрос).
        """
        params: dict[str, Any] = {
            "pageNumber": page_number,
            "pageSize": self._page_size,
            "sort": "createDate,desc",
            "lotStatus": "APPLICATIONS_SUBMISSION,PUBLISHED",
        }
        if filters:
            if filters.query:
                params["text"] = filters.query
            if filters.region:
                # Ожидаем код региона (ОКАТО/subjectRFCode — 2 цифры);
                # если backend передал имя — всё равно отдаём: API обработает
                # или вернёт пустой список.
                params["dynSubjRF"] = filters.region
            if filters.price_from is not None:
                params["priceMin"] = str(filters.price_from)
            if filters.price_to is not None:
                params["priceMax"] = str(filters.price_to)
            if filters.category:
                # Маппим наш slug → коды torgi. Проще всего перечислить все
                # коды, которые у нас замаплены на этот slug.
                codes = [
                    code for code, slug in _CATEGORY_CODE_MAP.items() if slug == filters.category
                ]
                if codes:
                    params["catCode"] = ",".join(codes)

        if since is not None:
            # torgi ждёт ISO-8601; он сам разберётся с таймзоной.
            params["byFirstVersion.createDate"] = since.isoformat()

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception(_is_retryable_error),
            reraise=True,
        ):
            with attempt:
                _logger.debug(
                    "torgi: GET %s params=%s попытка=%d",
                    self._api_url,
                    params,
                    attempt.retry_state.attempt_number,
                )
                response = await client.get(self._api_url, params=params)
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code >= 400:
                    _logger.error(
                        "torgi: клиентская ошибка HTTP %s: %s",
                        response.status_code,
                        response.text[:500],
                    )
                    response.raise_for_status()
                return response.json()
        # pragma: no cover
        return {}

    # --- Парсинг ----------------------------------------------------------

    def _build_lot(self, item: dict[str, Any]) -> ParsedLot | None:
        """Превращает один элемент ``content`` в :class:`ParsedLot`."""
        lot_id = str(item.get("id") or "")
        if not lot_id:
            _logger.warning("torgi: элемент без id, пропускаем: %r", item)
            return None

        title = normalize_whitespace(str(item.get("lotName") or ""))
        if not title:
            _logger.warning("torgi: лот %s без lotName, заменяем заглушкой", lot_id)
            title = f"Лот torgi.gov.ru {lot_id}"

        description = normalize_whitespace(str(item.get("lotDescription") or "")) or None

        price = parse_price(item.get("priceMinExact") or item.get("priceMin"))
        price_step = parse_price(item.get("priceStep"))

        # Категория: сперва точный маппинг по коду, потом эвристика по тексту.
        category = None
        cat_obj = item.get("category") or {}
        code = str(cat_obj.get("code") or "")
        if code:
            category = _CATEGORY_CODE_MAP.get(code)
        if category is None:
            category = guess_category(title, description)
        if category is None:
            # Полный текст имени категории — тоже попытаемся.
            category = guess_category(str(cat_obj.get("name") or ""))

        region_raw = str(item.get("subjectRFCode") or "") or item.get("estateAddress")
        region = parse_okato(str(region_raw)) if region_raw else None

        images = [
            _IMAGE_URL.format(file_id=fid)
            for fid in (item.get("lotImages") or [])
            if fid
        ]

        # Даты. `biddEndTime` — это окончание приёма заявок, используем как auction_date
        # fallback, а `auctionStartDate` как более точное. `createDate` / `noticeFirstVersionPublicationDate`
        # — как published_at.
        auction_date = (
            parse_datetime(str(item.get("auctionStartDate") or ""))
            or parse_datetime(str(item.get("biddEndTime") or ""))
        )
        published_at = (
            parse_datetime(str(item.get("noticeFirstVersionPublicationDate") or ""))
            or parse_datetime(str(item.get("createDate") or ""))
        )

        status = normalize_whitespace(str(item.get("lotStatus") or "")) or None

        source_url = _LOT_PUBLIC_URL.format(id=lot_id)

        try:
            return ParsedLot(
                source=self.name,
                source_lot_id=lot_id[:128],
                title=title[:1000],
                description=description,
                category=category,
                region=region,
                price=price,
                price_step=price_step,
                source_url=source_url,
                auction_date=auction_date,
                published_at=published_at,
                status=status,
                images=images,
                raw=item,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "torgi: лот не прошёл валидацию id=%s: %s", lot_id, exc
            )
            return None


__all__ = ["TorgiSource"]
