"""Общие фикстуры для тестов бота."""

import pytest


@pytest.fixture
def backend_url() -> str:
    """Базовый URL фиктивного backend для тестов."""
    return "http://test-backend"


@pytest.fixture
def internal_token() -> str:
    """Тестовый internal API token."""
    return "test-internal-token"
