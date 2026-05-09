"""Общие фикстуры pytest для парсера."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(relative_path: str) -> Any:
    """Загружает JSON-фикстуру относительно каталога ``fixtures/``.

    Args:
        relative_path: Путь вида ``"torgi/search_response.json"``.

    Returns:
        Декодированный JSON.
    """
    with (FIXTURES_DIR / relative_path).open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def torgi_search_response() -> dict[str, Any]:
    """Сырой ответ поиска torgi.gov.ru."""
    return load_fixture("torgi/search_response.json")


@pytest.fixture
def torgi_lot_card() -> dict[str, Any]:
    """Сырая карточка лота torgi.gov.ru."""
    return load_fixture("torgi/lot_card.json")


@pytest.fixture
def efrsb_list_page() -> dict[str, Any]:
    """Сырая страница списка сообщений ЕФРСБ."""
    return load_fixture("efrsb/list_page1.json")


@pytest.fixture
def efrsb_lot_card() -> dict[str, Any]:
    """Сырая карточка сообщения ЕФРСБ."""
    return load_fixture("efrsb/lot_card.json")


@pytest.fixture
def empty_efrsb_page() -> dict[str, Any]:
    """Пустой ответ ЕФРСБ — для обрыва пагинации."""
    return {"pageData": [], "found": 0}


@pytest.fixture
def empty_torgi_page() -> dict[str, Any]:
    """Пустой ответ torgi — для обрыва пагинации."""
    return {
        "content": [],
        "totalElements": 0,
        "totalPages": 0,
        "size": 20,
        "number": 0,
        "first": True,
        "last": True,
        "empty": True,
    }
