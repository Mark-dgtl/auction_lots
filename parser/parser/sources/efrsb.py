"""Источник лотов ЕФРСБ (``bankrot.fedresurs.ru``).

.. warning::
    **Источник временно заморожен.** С апреля 2026 публичный JSON
    (``/api/trademsg/search``, ранее ``/backend/trademsg/search``) закрыт
    Qrator'ом и отдаёт HTML SPA-shell без валидного cookie-челленджа.
    Код источника сохранён, HTTP-контракт и нормализация актуальны и
    покрыты тестами через ``respx``. Для возобновления работы нужно:

    1. Восстановить доступ (смена белых IP у Qrator либо headless-обход
       через Playwright), **или**
    2. Реализовать альтернативный вход: торговые площадки ЭТП
       (sberbank-ast, roseltorg и т.п.).

    Пока источник исключён из ``PARSER_SOURCES`` в ``.env``.

Стратегия извлечения:
    1. Делаем GET на публичный JSON-эндпоинт поиска торговых сообщений
       (``/backend/trademsg/search``). Для каждого сообщения типа
       «Сообщение о проведении торгов» берём вложенный объект ``trade``
       с массивом ``lots``. Именно лоты мы и возвращаем в виде :class:`ParsedLot`.
    2. Если JSON-эндпоинт возвращает HTML (Qrator-капча, SPA-shell) либо
       403/404 — логируем предупреждение и пытаемся распарсить HTML-страницу
       списка торгов через BeautifulSoup (fallback).
    3. Если и HTML не отдаётся без JS (Angular-SPA) — пишем ``error`` с raw
       HTML в ``debug`` и поднимаемся наверх. В боевом деплое в этом случае
       нужен Playwright (см. комментарий ниже).

.. note::
    EFRSB защищён Qrator: публичный доступ может требовать заголовков
    ``Cookie`` (сессионные), корректного ``User-Agent`` и ``Referer``.
    В тестах HTTP полностью замокан через ``respx``.

.. note::
    **Playwright-fallback (не включён)**. Если в будущем эвристики ниже
    начнут ломаться, рекомендуемый следующий шаг — поднять headless-браузер
    и получить JSON через реальный XHR. Интерфейс :class:`EfrsbSource`
    останется тем же, меняется только реализация ``_fetch_page``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Final

import httpx
from bs4 import BeautifulSoup
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


_logger = logging.getLogger("parser.efrsb")


_API_URL: Final = "https://bankrot.fedresurs.ru/api/trademsg/search"
_CARD_URL_TEMPLATE: Final = "https://bankrot.fedresurs.ru/message/{guid}"
_LOT_URL_TEMPLATE: Final = "https://bankrot.fedresurs.ru/message/{guid}?lot={lot_id}"

_DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) "
        "Gecko/20100101 Firefox/127.0"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": "https://bankrot.fedresurs.ru/",
}

_PAGE_SIZE: Final = 25
"""Размер страницы по умолчанию. EFRSB лимитирует 100, берём умеренный."""


def _is_retryable_error(exc: BaseException) -> bool:
    """Ретраим только сетевые ошибки и 5xx. 4xx — фатально."""
    if isinstance(exc, (httpx.TransportError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return False


class EfrsbSource(BaseSource):
    """Источник лотов ЕФРСБ.

    Attributes:
        name: Идентификатор источника (``"efrsb"``).
        client: Внешне переданный ``httpx.AsyncClient`` (для тестов). Если
            не передан — создаётся внутренний.
    """

    name: str = "efrsb"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        api_url: str = _API_URL,
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
        """Асинхронный генератор лотов ЕФРСБ.

        Обходит страницы поиска и для каждого торгового сообщения
        порождает один или несколько :class:`ParsedLot` (по числу лотов).

        Args:
            since: Если задано — пропускаем лоты с ``published_at`` раньше этой даты.
            filters: Дополнительные фильтры (category/region/price_from/to/query).
            limit: Жёсткий лимит количества отданных лотов.

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
        full_scan_completed = False
        self._run_telemetry = {
            "pages_fetched": 0,
            "expected_total_elements": None,
            "yielded_total": 0,
            "skipped_invalid": 0,
            "full_scan_completed": False,
        }
        try:
            offset = 0
            while True:
                page = await self._fetch_page(
                    client,
                    offset=offset,
                    filters=filters,
                )
                items = page.get("pageData") or page.get("items") or []
                pages_fetched += 1
                if not items:
                    _logger.info(
                        "ЕФРСБ: пустая страница offset=%s, завершаем обход", offset
                    )
                    break

                _logger.info(
                    "ЕФРСБ: получено %d сообщений на offset=%s", len(items), offset
                )

                for msg in items:
                    async for lot in self._lots_from_message(msg):
                        if since and lot.published_at and lot.published_at < since:
                            continue
                        yield lot
                        yielded += 1
                        if limit is not None and yielded >= limit:
                            full_scan_completed = False
                            return

                # Пагинация. Если пришло меньше запрошенного — последняя страница.
                if len(items) < self._page_size:
                    full_scan_completed = True
                    break
                offset += self._page_size
        finally:
            self._run_telemetry = {
                "pages_fetched": pages_fetched,
                "expected_total_elements": None,
                "yielded_total": yielded,
                "skipped_invalid": skipped_invalid,
                "full_scan_completed": full_scan_completed and limit is None,
            }
            if not self._external_client and self._client is None:
                await client.aclose()

    # --- Сетевой слой -----------------------------------------------------

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        *,
        offset: int,
        filters: ParseFilters | None,
    ) -> dict[str, Any]:
        """Получает одну страницу списка сообщений с ретраями.

        Делает GET с query-параметрами. При сетевой ошибке или 5xx —
        экспоненциальный backoff (3 попытки). 403/404 считаются фатальными
        (Qrator/нет прав).
        """
        params: dict[str, Any] = {
            "limit": self._page_size,
            "offset": offset,
            "orderDirection": "desc",
            "orderBy": "publishDate",
            "group": "TradeTrade",  # только сообщения о торгах
        }
        if filters:
            if filters.query:
                params["searchString"] = filters.query
            if filters.region:
                params["region"] = filters.region
            if filters.price_from is not None:
                params["priceFrom"] = str(filters.price_from)
            if filters.price_to is not None:
                params["priceTo"] = str(filters.price_to)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception(_is_retryable_error),
            reraise=True,
        ):
            with attempt:
                _logger.debug(
                    "ЕФРСБ: запрос %s params=%s попытка=%d",
                    self._api_url,
                    params,
                    attempt.retry_state.attempt_number,
                )
                response = await client.get(self._api_url, params=params)
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code in (403, 404):
                    _logger.warning(
                        "ЕФРСБ заморожен: API возвращает HTTP %s "
                        "(Qrator-блокировка). Источник пропускается.",
                        response.status_code,
                    )
                    response.raise_for_status()
                # Некоторые страницы отдают SPA-shell c Content-Type text/html.
                ctype = response.headers.get("content-type", "")
                if "application/json" not in ctype:
                    _logger.warning(
                        "ЕФРСБ: неожиданный content-type=%r, пробуем HTML-fallback",
                        ctype,
                    )
                    return self._parse_html_fallback(response.text)
                return response.json()
        # pragma: no cover -- reraise=True делает эту ветку недостижимой
        return {}

    # --- Парсинг сообщения → лоты -----------------------------------------

    async def _lots_from_message(
        self, msg: dict[str, Any]
    ) -> AsyncIterator[ParsedLot]:
        """Раскрывает одно торговое сообщение в один или несколько ``ParsedLot``."""
        guid = msg.get("guid") or msg.get("id") or ""
        if not guid:
            _logger.warning("ЕФРСБ: сообщение без guid, пропускаем: %r", msg)
            return

        publish_date = parse_datetime(msg.get("publishDate"))
        debtor_raw = msg.get("debtor") or {}
        debtor_name = normalize_whitespace(
            debtor_raw.get("name")
            or debtor_raw.get("fullName")
            or msg.get("debtorName")
            or ""
        )

        trade = msg.get("trade") or {}
        auction_date = parse_datetime(
            trade.get("bidEndDate")
            or trade.get("auctionDate")
            or trade.get("bidStartDate"),
        )
        region_text = (
            trade.get("region")
            or trade.get("regionName")
            or msg.get("regionName")
            or debtor_raw.get("region")
        )
        region = parse_okato(region_text) if region_text else None

        lots: list[dict[str, Any]] = trade.get("lots") or msg.get("lots") or []
        if not lots:
            # Иногда поле lots отсутствует, а сам лот описан прямо в сообщении.
            lots = [msg]

        for idx, lot in enumerate(lots, start=1):
            try:
                parsed = self._build_lot(
                    lot,
                    msg=msg,
                    guid=guid,
                    default_index=idx,
                    publish_date=publish_date,
                    auction_date=auction_date,
                    region=region,
                    debtor_name=debtor_name,
                )
            except Exception as exc:  # noqa: BLE001 — хотим не рушить обход
                _logger.exception(
                    "ЕФРСБ: не удалось построить ParsedLot для guid=%s lot=%s: %s",
                    guid,
                    idx,
                    exc,
                )
                continue
            if parsed is not None:
                yield parsed
            else:
                self._run_telemetry["skipped_invalid"] = (
                    int(self._run_telemetry.get("skipped_invalid", 0)) + 1
                )

    def _build_lot(
        self,
        lot: dict[str, Any],
        *,
        msg: dict[str, Any],
        guid: str,
        default_index: int,
        publish_date: datetime | None,
        auction_date: datetime | None,
        region: str | None,
        debtor_name: str,
    ) -> ParsedLot | None:
        """Формирует :class:`ParsedLot` из JSON-описания одного лота."""
        lot_number = str(
            lot.get("lotNumber") or lot.get("number") or default_index
        )
        source_lot_id = f"{guid}:{lot_number}"

        raw_title = (
            lot.get("lotName")
            or lot.get("name")
            or lot.get("description")
            or lot.get("lotDescription")
            or ""
        )
        title = normalize_whitespace(raw_title) or f"Лот {lot_number}"
        if debtor_name and debtor_name not in title:
            title = f"{title} ({debtor_name})"[:1000]

        description_parts: list[str] = []
        if raw_desc := lot.get("description") or lot.get("lotDescription"):
            description_parts.append(normalize_whitespace(str(raw_desc)))
        if addr := lot.get("address") or lot.get("estateAddress"):
            description_parts.append(f"Адрес: {normalize_whitespace(str(addr))}")
        description = " ".join(p for p in description_parts if p) or None

        price = parse_price(lot.get("priceStart") or lot.get("priceMin") or lot.get("price"))
        price_step = parse_price(lot.get("priceStep") or lot.get("priceStepValue"))

        classifier = lot.get("classifierNode") or {}
        category_text = (
            classifier.get("name")
            or lot.get("categoryName")
            or lot.get("classifier")
        )
        category = guess_category(title, description) or (
            guess_category(str(category_text)) if category_text else None
        )

        images = self._extract_images(lot)

        lot_region = lot.get("region") or lot.get("regionName") or region
        if isinstance(lot_region, str):
            lot_region = parse_okato(lot_region)

        source_url = _LOT_URL_TEMPLATE.format(guid=guid, lot_id=lot_number)
        status = normalize_whitespace(
            str(lot.get("status") or msg.get("statusName") or "")
        ) or None

        try:
            return ParsedLot(
                source=self.name,
                source_lot_id=source_lot_id[:128],
                title=title[:1000],
                description=description,
                category=category,
                region=lot_region,
                price=price,
                price_step=price_step,
                source_url=source_url,
                auction_date=auction_date,
                published_at=publish_date,
                status=status,
                images=images,
                raw={"message": msg, "lot": lot},
            )
        except Exception as exc:  # noqa: BLE001 — pydantic ValidationError тоже
            _logger.warning(
                "ЕФРСБ: лот не прошёл валидацию source_lot_id=%s: %s",
                source_lot_id,
                exc,
            )
            return None

    # --- HTML fallback ----------------------------------------------------

    def _parse_html_fallback(self, html: str) -> dict[str, Any]:
        """Пробует выдрать список сообщений из HTML (страница списка торгов).

        Реальный сайт — Angular-SPA, без JS отдаётся «пустой» shell.
        Функция детектирует этот случай и возвращает пустой ``pageData``,
        логируя ``error`` с первыми 500 символами HTML в debug.
        """
        soup = BeautifulSoup(html, "lxml")
        # На странице-shell нет таблиц с сообщениями, но оставляем попытку
        # распарсить ``table.messages-table`` — на случай, если сайт
        # вернёт HTML-вариант (редко, но бывало при маршрутизации Qrator).
        items: list[dict[str, Any]] = []
        for row in soup.select("table.messages-table tbody tr"):
            cells = [normalize_whitespace(c.get_text(" ")) for c in row.select("td")]
            if not cells:
                continue
            items.append(
                {
                    "guid": row.get("data-guid") or row.get("id") or "",
                    "publishDate": cells[0] if cells else None,
                    "debtor": {"name": cells[1] if len(cells) > 1 else None},
                    "lotName": cells[2] if len(cells) > 2 else None,
                }
            )

        if not items:
            _logger.error(
                "ЕФРСБ: HTML-fallback не нашёл записей (вероятно, SPA-shell)."
            )
            _logger.debug("ЕФРСБ: HTML начинается с: %s", html[:500])
        return {"pageData": items, "found": len(items)}

    # --- Утилиты ----------------------------------------------------------

    @staticmethod
    def _extract_images(lot: dict[str, Any]) -> list[str]:
        """Извлекает список URL изображений. Поддерживает строковые и dict-элементы."""
        raw = lot.get("photos") or lot.get("images") or lot.get("lotImages") or []
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                url = item
            elif isinstance(item, dict):
                url = item.get("url") or item.get("link") or item.get("src") or ""
            else:
                continue
            url = normalize_whitespace(url)
            if url.startswith("http"):
                out.append(url)
            elif url:
                # относительный путь — дополним до абсолютного
                out.append(f"https://bankrot.fedresurs.ru{url}")
        return out

    def get_run_telemetry(self) -> dict[str, Any]:
        return dict(self._run_telemetry)


__all__ = ["EfrsbSource"]

