"""Юнит-тесты для :mod:`parser.normalizer`."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from parser.normalizer import (
    guess_category,
    normalize_whitespace,
    parse_datetime,
    parse_okato,
    parse_price,
)


class TestNormalizeWhitespace:
    """Тесты :func:`normalize_whitespace`."""

    @pytest.mark.parametrize(
        "src,expected",
        [
            ("  hello\tworld  ", "hello world"),
            ("foo\u00a0bar", "foo bar"),
            ("  a\n\nb\n c ", "a b c"),
            ("", ""),
            ("\u202f\u2009", ""),
            ("one  two   three", "one two three"),
        ],
    )
    def test_basic(self, src: str, expected: str) -> None:
        assert normalize_whitespace(src) == expected

    def test_none_friendly(self) -> None:
        assert normalize_whitespace(None) == ""  # type: ignore[arg-type]


class TestParsePrice:
    """Тесты :func:`parse_price`."""

    @pytest.mark.parametrize(
        "src,expected",
        [
            ("1 234 567,89 руб.", Decimal("1234567.89")),
            ("1 234 567.89 ₽", Decimal("1234567.89")),
            ("3500000", Decimal("3500000")),
            ("3 500 000,00", Decimal("3500000.00")),
            ("1,234,567.89", Decimal("1234567.89")),
            ("1.234.567,89", Decimal("1234567.89")),
            ("42", Decimal("42")),
            ("0,01", Decimal("0.01")),
            ("-1000", Decimal("-1000")),
        ],
    )
    def test_valid(self, src: str, expected: Decimal) -> None:
        assert parse_price(src) == expected

    @pytest.mark.parametrize("src", ["", None, "abc", "руб.", "---", "   "])
    def test_invalid(self, src) -> None:
        assert parse_price(src) is None

    def test_decimal_from_number(self) -> None:
        assert parse_price(350000) == Decimal("350000")


class TestParseDatetime:
    """Тесты :func:`parse_datetime`."""

    def test_dot_format_with_time(self) -> None:
        dt = parse_datetime("20.05.2026 10:00")
        assert dt == datetime(2026, 5, 20, 7, 0, 0, tzinfo=timezone.utc)

    def test_dot_format_date_only(self) -> None:
        dt = parse_datetime("01.01.2026")
        assert dt == datetime(2025, 12, 31, 21, 0, 0, tzinfo=timezone.utc)

    def test_iso_z(self) -> None:
        dt = parse_datetime("2026-05-20T10:00:00Z")
        assert dt == datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc)

    def test_iso_with_offset(self) -> None:
        dt = parse_datetime("2026-05-20T10:00:00+03:00")
        assert dt == datetime(2026, 5, 20, 7, 0, 0, tzinfo=timezone.utc)

    def test_russian_month(self) -> None:
        dt = parse_datetime("20 мая 2026, 10:00")
        assert dt == datetime(2026, 5, 20, 7, 0, 0, tzinfo=timezone.utc)

    def test_russian_month_date_only(self) -> None:
        dt = parse_datetime("20 мая 2026")
        assert dt is not None
        # Naive-дата интерпретируется как Europe/Moscow → 00:00 MSK = 21:00 UTC прошлого дня.
        assert dt == datetime(2026, 5, 19, 21, 0, 0, tzinfo=timezone.utc)

    def test_russian_month_date_only_utc(self) -> None:
        dt = parse_datetime("20 мая 2026", tz="UTC")
        assert dt == datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)

    def test_unix_seconds(self) -> None:
        dt = parse_datetime("1747742400")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_unix_millis(self) -> None:
        dt = parse_datetime("1747742400000")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_custom_tz(self) -> None:
        # naive-дата в UTC должна дать UTC
        dt = parse_datetime("01.06.2026 15:00", tz="UTC")
        assert dt == datetime(2026, 6, 1, 15, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.parametrize("src", ["", None, "not a date", "99.99.9999"])
    def test_invalid(self, src) -> None:
        assert parse_datetime(src) is None

    def test_result_is_utc(self) -> None:
        dt = parse_datetime("2026-05-20T10:00:00+03:00")
        assert dt is not None
        assert dt.utcoffset().total_seconds() == 0


class TestGuessCategory:
    """Тесты :func:`guess_category`."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Квартира 52 кв.м, Москва", "real_estate"),
            ("Жилой дом в деревне", "real_estate"),
            ("Нежилое помещение 120 кв.м", "real_estate"),
            ("Гараж подземный", "real_estate"),
            ("Земельный участок 10 соток", "land"),
            ("З/у под ИЖС", "land"),
            ("Автомобиль LADA Granta", "vehicle"),
            ("КАМАЗ 5320, 1995 г.в.", "vehicle"),
            ("Грузовой автомобиль Mercedes Sprinter", "vehicle"),
            ("Станок токарный 1К62", "equipment"),
            ("Производственная линия", "equipment"),
            ("Права требования к ООО", "rights"),
            ("Дебиторская задолженность", "rights"),
            ("Акции ПАО \"Ромашка\"", "securities"),
            ("Мебель офисная, б/у", "inventory"),
            ("Что-то непонятное", None),
            ("", None),
        ],
    )
    def test_title(self, title: str, expected: str | None) -> None:
        assert guess_category(title) == expected

    def test_description_fallback(self) -> None:
        assert guess_category("Лот №1", "Двухкомнатная квартира") == "real_estate"

    def test_none(self) -> None:
        assert guess_category(None, None) is None

    def test_land_before_real_estate(self) -> None:
        """«Земельный участок» не должен уехать в real_estate только из-за близких слов."""
        assert guess_category("Земельный участок с домом") == "land"


class TestParseOkato:
    """Тесты :func:`parse_okato`."""

    @pytest.mark.parametrize(
        "src,expected",
        [
            ("45", "45"),
            ("77", "77"),
            ("45000000000", "45000000000"),
            ("45000", "45000"),
            ("45 г. Москва", "45"),
            ("г. Москва", "г. Москва"),
            ("Свердловская область", "Свердловская область"),
            ("", None),
            (None, None),
            ("   ", None),
        ],
    )
    def test_parse(self, src, expected) -> None:
        assert parse_okato(src) == expected

    def test_single_digit_not_okato(self) -> None:
        assert parse_okato("1") == "1"  # возвращается как имя
