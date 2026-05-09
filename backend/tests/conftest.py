"""Фикстуры для тестов.

Тесты без маркера @pytest.mark.pg запускаются на SQLite in-memory.
Тесты с маркером @pytest.mark.pg требуют реальной PostgreSQL.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# Отключаем планировщик во всех тестах — до импорта app
settings.SCHEDULER_ENABLED = False

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.category import Category
from app.models.lot import Lot
from app.models.region import Region
from app.models.user import User

# ---------------------------------------------------------------------------
# Данные для seed
# ---------------------------------------------------------------------------

CATEGORIES_SEED = [
    ("real_estate", "Недвижимость"),
    ("vehicle", "Транспорт"),
    ("equipment", "Оборудование"),
    ("land", "Земельные участки"),
    ("rights", "Права требования"),
    ("securities", "Ценные бумаги"),
    ("inventory", "ТМЦ и материалы"),
    ("other", "Прочее"),
]

REGIONS_SEED = [
    ("45", "Москва"),
    ("40", "Санкт-Петербург"),
    ("66", "Свердловская область"),
    ("50", "Московская область"),
    ("23", "Краснодарский край"),
]


# ---------------------------------------------------------------------------
# Движок и сессии
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def engine():
    """Создаёт SQLite in-memory движок с таблицами для каждого теста.

    StaticPool гарантирует, что все сессии теста используют одно соединение
    и видят одну и ту же in-memory базу данных.
    """
    _engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Предоставляет сессию БД для прямого использования в тестах."""
    _session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with _session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(engine):
    """HTTP-клиент с переопределённой зависимостью get_db → SQLite."""
    _session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with _session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Seed справочников
    async with _session_maker() as session:
        for slug, name in CATEGORIES_SEED:
            session.add(Category(slug=slug, name=name))
        for code, name in REGIONS_SEED:
            session.add(Region(code=code, name=name))
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Вспомогательные фикстуры
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Регистрирует тестового пользователя и возвращает {id, email, password}."""
    email = "test@example.com"
    password = "testpassword123"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": password}
    )
    assert resp.status_code == 201
    data = resp.json()
    return {"id": data["id"], "email": email, "password": password}


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, registered_user: dict) -> dict:
    """Логинит тестового пользователя и возвращает заголовки с access-токеном."""
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_lots(engine) -> list[int]:
    """Создаёт 3 тестовых лота и возвращает список их ID."""
    _session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with _session_maker() as session:
        # Seed справочников если нет
        from sqlalchemy import select

        existing_cat = await session.scalar(
            select(Category).where(Category.slug == "real_estate")
        )
        if not existing_cat:
            for slug, name in CATEGORIES_SEED:
                session.add(Category(slug=slug, name=name))
            for code, name in REGIONS_SEED:
                session.add(Region(code=code, name=name))

        lots = [
            Lot(
                source="efrsb",
                source_lot_id="lot-001",
                title="Квартира 52 м² в Москве",
                category="real_estate",
                region_code="45",
                price=3500000,
                source_url="https://efrsb.ru/lot/1",
            ),
            Lot(
                source="efrsb",
                source_lot_id="lot-002",
                title="Автомобиль BMW X5",
                category="vehicle",
                region_code="40",
                price=1200000,
                source_url="https://efrsb.ru/lot/2",
            ),
            Lot(
                source="torgi_gov",
                source_lot_id="lot-003",
                title="Промышленное оборудование",
                category="equipment",
                region_code="66",
                price=500000,
                source_url="https://torgi.gov.ru/lot/3",
            ),
        ]
        for lot in lots:
            session.add(lot)
        await session.commit()
        for lot in lots:
            await session.refresh(lot)
        return [lot.id for lot in lots]
