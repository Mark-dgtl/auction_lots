# Backend — Агрегатор торгов

FastAPI + PostgreSQL + Alembic + JWT.

## Быстрый старт (локально, без Docker)

### 1. Создать виртуальное окружение

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Установить зависимости

```bash
# Установить parser как editable-пакет
pip install -e "../parser"

# Установить backend со всеми dev-зависимостями
pip install -e ".[dev]"
```

### 3. Настроить окружение

```bash
cp ../.env.example .env
# Отредактировать .env: DATABASE_URL, JWT_SECRET и т.д.
```

### 4. Создать БД и применить миграции

```bash
# PostgreSQL должен быть запущен
createdb tenders  # если нужно создать БД

alembic upgrade head
```

### 5. Запустить сервер

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: http://localhost:8000/docs  
ReDoc: http://localhost:8000/redoc  
OpenAPI JSON: http://localhost:8000/openapi.json

---

## Тесты

### Тесты без PostgreSQL (SQLite in-memory)

```bash
cd backend
pytest -m "not pg" -v
```

### Тесты с PostgreSQL (требуют `DATABASE_URL` в .env)

```bash
pytest -m pg -v
```

---

## Структура `app/`

```
app/
├── __init__.py
├── main.py                  # FastAPI app, middleware, exception handlers
├── core/
│   ├── config.py            # Settings (pydantic-settings)
│   ├── errors.py            # AppError, NotFound, Unauthorized, ...
│   ├── logging.py           # configure_logging()
│   └── security.py          # hash_password, JWT utils
├── db/
│   ├── base.py              # Base = DeclarativeBase
│   └── session.py           # engine, async_session_maker, get_db
├── models/
│   ├── user.py              # users
│   ├── refresh_token.py     # refresh_tokens
│   ├── lot.py               # lots
│   ├── region.py            # regions
│   ├── category.py          # categories
│   ├── favorite.py          # favorites
│   ├── saved_filter.py      # saved_filters
│   ├── notification_log.py  # notification_log
│   ├── outbox.py            # outbox
│   └── parser_run.py        # parser_runs
├── schemas/
│   ├── auth.py              # Register/Login/Token/Me
│   ├── lot.py               # LotShort, LotDetail, LotListResponse
│   ├── favorite.py          # FavoriteListResponse
│   ├── filter.py            # SavedFilter CRUD schemas
│   ├── telegram.py          # TelegramLink, TelegramBind
│   ├── notification.py      # NotificationSettings
│   ├── meta.py              # Category/RegionItem + list responses
│   └── common.py            # ErrorEnvelope, Pagination
├── services/
│   ├── auth_service.py      # register, login, refresh, logout
│   ├── lot_service.py       # search, get_by_id
│   ├── favorite_service.py  # add, remove, list
│   ├── filter_service.py    # CRUD saved_filters
│   ├── telegram_service.py  # generate_link, unlink, bind_telegram
│   └── notification_service.py  # get/update settings
└── api/
    ├── __init__.py          # api_router + GET /api/me
    ├── deps.py              # get_current_user, get_current_user_optional, require_internal_token
    ├── auth.py              # /api/auth/*
    ├── lots.py              # /api/lots
    ├── favorites.py         # /api/favorites
    ├── filters.py           # /api/filters
    ├── telegram.py          # /api/telegram/*
    ├── notifications.py     # /api/notifications/*
    ├── meta.py              # /api/meta/*
    └── internal.py          # /api/internal/*
```

---

## Все эндпоинты

| Метод  | Путь                                | Auth        | Описание                                      |
|--------|-------------------------------------|-------------|-----------------------------------------------|
| POST   | /api/auth/register                  | —           | Регистрация                                   |
| POST   | /api/auth/login                     | —           | Вход, получение токенов                       |
| POST   | /api/auth/refresh                   | cookie      | Обновление access-токена                      |
| POST   | /api/auth/logout                    | cookie      | Выход                                         |
| GET    | /api/me                             | Bearer      | Данные текущего пользователя                  |
| GET    | /api/lots                           | optional    | Поиск лотов с фильтрами                       |
| GET    | /api/lots/{id}                      | optional    | Детальная карточка лота                       |
| GET    | /api/favorites                      | Bearer      | Список избранного                             |
| POST   | /api/favorites/{lot_id}             | Bearer      | Добавить в избранное                          |
| DELETE | /api/favorites/{lot_id}             | Bearer      | Убрать из избранного                          |
| GET    | /api/filters                        | Bearer      | Список сохранённых фильтров                   |
| POST   | /api/filters                        | Bearer      | Создать фильтр                                |
| PUT    | /api/filters/{id}                   | Bearer      | Обновить фильтр                               |
| DELETE | /api/filters/{id}                   | Bearer      | Удалить фильтр                                |
| POST   | /api/telegram/link                  | Bearer      | Сгенерировать deep-link                       |
| POST   | /api/telegram/unlink                | Bearer      | Отвязать Telegram                             |
| GET    | /api/notifications/settings         | Bearer      | Получить настройки уведомлений                |
| PUT    | /api/notifications/settings         | Bearer      | Обновить время дайджеста                      |
| GET    | /api/meta/categories                | —           | Справочник категорий                          |
| GET    | /api/meta/regions                   | —           | Справочник регионов                           |
| POST   | /api/internal/telegram/bind         | X-Internal-Token | Привязать TG-аккаунт (бот→backend)       |
| GET    | /api/internal/outbox                | X-Internal-Token | Очередь сообщений (заглушка M1)          |
| POST   | /api/internal/outbox/{id}/ack       | X-Internal-Token | Подтвердить доставку                     |
