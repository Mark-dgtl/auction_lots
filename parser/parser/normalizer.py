"""Общие утилиты нормализации данных от источников.

Модуль собирает в одном месте всё, что повторно нужно конкретным источникам:
разбор цен, разбор дат в разных форматах, очистка whitespace, простой
rule-based классификатор категорий и извлечение кода ОКАТО.

Функции намеренно максимально устойчивы к мусору: на некорректном входе
возвращают ``None`` (или исходную строку для регионов), а не бросают
исключения — чтобы парсер не падал из-за локального поля одного лота.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Final

from dateutil import parser as dateutil_parser
from dateutil import tz as dateutil_tz

from parser.base import CATEGORY_SLUGS


_logger = logging.getLogger("parser.normalizer")


_NBSP_CHARS: Final = ("\u00a0", "\u202f", "\u2009", "\u2007")
"""Различные «неразрывные» пробелы, которые встречаются в данных с сайтов."""

_MONTHS_RU: Final[dict[str, int]] = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
    # дополнительные формы в именительном падеже — встречаются в статусах
    "январь": 1,
    "февраль": 2,
    "март": 3,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июль": 7,
    "август": 8,
    "сентябрь": 9,
    "октябрь": 10,
    "ноябрь": 11,
    "декабрь": 12,
}

# Регулярка для формата "DD месяца YYYY [HH:MM]"
_RU_DATE_RE: Final = re.compile(
    r"(?P<day>\d{1,2})\s+"
    r"(?P<month>[а-яё]+)\s+"
    r"(?P<year>\d{4})"
    r"(?:[,\s]+(?P<hour>\d{1,2})[:\-.](?P<minute>\d{2}))?",
    re.IGNORECASE,
)

# Регулярка для формата "DD.MM.YYYY [HH:MM[:SS]]"
_DOT_DATE_RE: Final = re.compile(
    r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})"
    r"(?:[\sT]+(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?)?"
)

# Строка из 2-11 цифр, подходящая под ОКАТО (2, 5, 8 или 11 цифр по уровню региона).
_OKATO_RE: Final = re.compile(r"\b(\d{2}(?:\d{3}(?:\d{3}(?:\d{3})?)?)?)\b")


# --- Категории --------------------------------------------------------------

_CATEGORY_KEYWORDS: Final[list[tuple[str, tuple[str, ...]]]] = [
    # Порядок важен: более специфичные категории проверяем раньше.
    # Права требования и ценные бумаги — первыми, их ключевые слова самые
    # специфичные и не пересекаются.
    (
        "rights",
        (
            "право требован",
            "права требован",
            "дебиторск",
            "цессия",
        ),
    ),
    (
        "securities",
        (
            "акци",
            "облигаци",
            "вексел",
            "ценные бумаги",
            "доля в уставном",
        ),
    ),
    # ТМЦ / инвентарь ищем раньше недвижимости — иначе «мебель офисная»
    # может уехать в real_estate из-за «офис».
    (
        "inventory",
        (
            "тмц",
            "товарно-материальн",
            "материалы",
            "запасы",
            "сырь",
            "мебель",
            "инвентар",
        ),
    ),
    (
        "land",
        (
            "земельный участок",
            "земельн",
            "участок земли",
            "з/у",
            "лпх",
            "снт ",
            "под ижс",
            "сельхозназначени",
        ),
    ),
    (
        "vehicle",
        (
            "автомобил",
            "легков",
            "грузов",
            "автобус",
            "мотоцикл",
            "прицеп",
            "полуприцеп",
            "транспортн",
            "экскаватор",
            "трактор",
            "бульдозер",
            "ваз ",
            "lada",
            "toyota",
            "nissan",
            "kamaz",
            "камаз",
            "газель",
            "hyundai",
            "mazda",
            "ford",
            "bmw",
            "mercedes",
            "audi",
            "volkswagen",
            "skoda",
        ),
    ),
    (
        "equipment",
        (
            "станок",
            "оборудован",
            "агрегат",
            "компрессор",
            "насос",
            "генератор",
            "линия производств",
            "производственн",
            "станция",
        ),
    ),
    (
        "real_estate",
        (
            "квартир",
            "апартамент",
            "комнат",
            "жилой дом",
            "жилое помещение",
            "нежилое помещение",
            "нежилое здание",
            "здание",
            "сооружени",
            "помещени",
            "гараж",
            "машиномест",
            "парковоч",
            "дом ",
            "коттедж",
            "таунхаус",
            "дача",
            "офисное помещени",
            "склад",
            "магазин",
            "недвижим",
        ),
    ),
]


# --- Whitespace -------------------------------------------------------------


def normalize_whitespace(text: str) -> str:
    """Схлопывает любые пробельные символы в одиночные и убирает nbsp.

    Args:
        text: Произвольная строка.

    Returns:
        Строка без ведущих/замыкающих пробелов, с одиночными пробелами
        между словами. Если на вход пришёл ``None`` или пустая строка —
        вернёт пустую строку.
    """
    if not text:
        return ""
    cleaned = text
    for ch in _NBSP_CHARS:
        cleaned = cleaned.replace(ch, " ")
    cleaned = cleaned.replace("\r", " ").replace("\t", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# --- Цена -------------------------------------------------------------------


def parse_price(text: str | None) -> Decimal | None:
    """Извлекает десятичную цену из строки вида ``"1 234 567,89 руб."``.

    Логика:
      * убираются nbsp, пробелы-разделители разрядов;
      * запятая-разделитель дробной части приводится к точке;
      * валютные символы и текст (``руб``, ``₽``, ``RUB``) отбрасываются;
      * если в строке нет ни одной цифры — возвращается ``None``.

    Args:
        text: Строка с ценой либо ``None``.

    Returns:
        :class:`Decimal` с ценой или ``None``, если распарсить не удалось.
    """
    if text is None:
        return None
    raw = normalize_whitespace(str(text))
    if not raw:
        return None

    # Выбрасываем всё, что не цифра/разделитель/минус.
    cleaned = re.sub(r"[^\d,.\-]", "", raw)
    if not cleaned:
        return None

    # Отрезаем висящие в начале/конце разделители — обычно это хвосты от "руб.".
    cleaned = re.sub(r"^[,.]+", "", cleaned)
    cleaned = re.sub(r"[,.]+$", "", cleaned)
    if not cleaned:
        return None

    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        # Какой из разделителей появляется последним — тот десятичный.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        # Несколько запятых — это явно тысячные разделители ("1,234,567").
        if cleaned.count(",") > 1:
            cleaned = cleaned.replace(",", "")
        else:
            # Одиночная запятая: если справа 1-2 цифры — десятичная, иначе разряд.
            tail = cleaned.rsplit(",", 1)[1]
            if 1 <= len(tail) <= 2:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
    elif has_dot and cleaned.count(".") > 1:
        # "1.234.567" — все точки это разряды.
        head, _, tail = cleaned.rpartition(".")
        # Если хвост 3 цифры, скорее всего и он разряд → склеиваем всё.
        if len(tail) == 3:
            cleaned = cleaned.replace(".", "")
        else:
            cleaned = head.replace(".", "") + "." + tail

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        _logger.debug("Не удалось распарсить цену: %r", text)
        return None


# --- Даты -------------------------------------------------------------------


def _to_utc(dt: datetime, tz_name: str) -> datetime:
    """Приводит datetime к UTC, проставляя tz, если его нет."""
    if dt.tzinfo is None:
        local_tz = dateutil_tz.gettz(tz_name) or timezone.utc
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc)


def parse_datetime(text: str | None, tz: str = "Europe/Moscow") -> datetime | None:
    """Парсит дату из произвольной строки и возвращает UTC-aware ``datetime``.

    Поддерживаемые форматы:
      * ``"DD.MM.YYYY"`` и ``"DD.MM.YYYY HH:MM[:SS]"``;
      * ISO-8601 (``"2026-05-20T10:00:00Z"``, с суффиксом ``+03:00`` и т.п.);
      * ``"DD месяца YYYY"`` и ``"DD месяца YYYY HH:MM"`` с русскими месяцами;
      * unix-timestamp в миллисекундах или секундах, если передана строка
        из одних цифр.

    Args:
        text: Строка с датой либо ``None``.
        tz: Имя таймзоны, в которой интерпретировать naive-дату. По умолчанию
            московская — так как оба наших источника работают в ней.

    Returns:
        UTC-aware :class:`datetime` или ``None``, если распарсить не удалось.
    """
    if text is None:
        return None
    raw = normalize_whitespace(str(text))
    if not raw:
        return None

    # 1) unix timestamp (может быть int/float в виде строки)
    if re.fullmatch(r"-?\d{9,14}", raw):
        try:
            val = int(raw)
            # миллисекунды vs секунды
            if abs(val) > 10_000_000_000:
                val = val / 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    # 2) "DD.MM.YYYY [HH:MM[:SS]]"
    m = _DOT_DATE_RE.search(raw)
    if m:
        try:
            dt = datetime(
                int(m.group("year")),
                int(m.group("month")),
                int(m.group("day")),
                int(m.group("hour") or 0),
                int(m.group("minute") or 0),
                int(m.group("second") or 0),
            )
            return _to_utc(dt, tz)
        except ValueError:
            pass  # упадёт на ISO ниже

    # 3) "DD месяца YYYY [HH:MM]"
    m = _RU_DATE_RE.search(raw.lower())
    if m:
        month_name = m.group("month")
        month = _MONTHS_RU.get(month_name)
        if month:
            try:
                dt = datetime(
                    int(m.group("year")),
                    month,
                    int(m.group("day")),
                    int(m.group("hour") or 0),
                    int(m.group("minute") or 0),
                )
                return _to_utc(dt, tz)
            except ValueError:
                pass

    # 4) Всё остальное — отдаём dateutil как last resort.
    try:
        dt = dateutil_parser.parse(raw, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError, dateutil_parser.ParserError):
        _logger.debug("Не удалось распарсить дату: %r", text)
        return None
    return _to_utc(dt, tz)


# --- Категория --------------------------------------------------------------


def guess_category(title: str | None, description: str | None = None) -> str | None:
    """Простой rule-based классификатор категории лота.

    Последовательно проходит по словарю ключевых слов и возвращает slug
    первой подошедшей категории. Ищет подстроки в нижнем регистре,
    чтобы не зависеть от регистра и окончаний слов («квартир» → «квартиру»,
    «квартиры» и т.д.).

    Args:
        title: Заголовок лота.
        description: Описание лота (необязательно).

    Returns:
        Один из slug-ов :data:`parser.base.CATEGORY_SLUGS` или ``None``,
        если категория не определена.
    """
    parts: list[str] = []
    if title:
        parts.append(title)
    if description:
        parts.append(description)
    if not parts:
        return None

    haystack = normalize_whitespace(" ".join(parts)).lower()
    if not haystack:
        return None

    for slug, keywords in _CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return slug

    return None


# --- Регион / ОКАТО ---------------------------------------------------------


def parse_okato(region_text: str | None) -> str | None:
    """Возвращает код ОКАТО либо нормализованное имя региона.

    Если в тексте есть последовательность цифр, похожая на ОКАТО (2, 5, 8
    или 11 цифр), возвращается она. Иначе — исходная строка (очищенная
    от whitespace). Backend сам попробует смапить имя в код через LIKE.

    Args:
        region_text: Строка с регионом (код, название, «г. Москва»
            и т.п.) либо ``None``.

    Returns:
        Цифровой код ОКАТО (``str``), нормализованное имя региона или
        ``None``, если на входе пусто.
    """
    if region_text is None:
        return None
    raw = normalize_whitespace(str(region_text))
    if not raw:
        return None

    # Если вся строка — цифры подходящей длины, возвращаем её как код.
    if re.fullmatch(r"\d{2}(?:\d{3}(?:\d{3}(?:\d{3})?)?)?", raw):
        return raw

    # Если строка вида "45 г. Москва" — возьмём начальный код.
    m = _OKATO_RE.match(raw)
    if m and len(m.group(1)) in (2, 5, 8, 11):
        return m.group(1)

    return raw


# Публичный __all__ (не критично, но помогает статическим анализаторам).
__all__ = [
    "normalize_whitespace",
    "parse_price",
    "parse_datetime",
    "guess_category",
    "parse_okato",
]
