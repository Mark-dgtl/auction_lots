# Контракты системы «Агрегатор торгов»

Документ фиксирует интерфейсы между модулями. Обязателен для исполнения всеми
субагентами (`parsing_proger`, `backender`, `frontender`). Любое изменение
контракта — только через оркестратор.

Статус: **Source of truth для M1**. Реализация в коде обязана соответствовать
этому документу. При противоречиях — приоритет за этим документом.

> **Заметка по ЕФРСБ (апрель 2026):** источник `efrsb` временно заморожен.
> API ``bankrot.fedresurs.ru`` закрыт Qrator'ом и не отвечает JSON'ом без
> полноценного браузерного челленджа. Код источника, контракт `ParsedLot`
> и тесты `respx` сохранены и валидны; для боевой работы источник отключен
> в `PARSER_SOURCES` до восстановления доступа или добавления
> Playwright-обхода. Основной рабочий источник на текущем этапе — `torgi_gov`.

---

## 1. Контракт парсер-пакета (`parser`)

### 1.1 Схема `ParsedLot`

Единственный формат, в котором парсер отдаёт данные в backend.
Реализация — `parser/parser/base.py` (Pydantic v2).

| Поле             | Тип                       | Обязательное | Описание                                                                      |
| ---------------- | ------------------------- | ------------ | ----------------------------------------------------------------------------- |
| `source`         | `str`                     | да           | Идентификатор источника: `"efrsb"` или `"torgi_gov"`.                         |
| `source_lot_id`  | `str`                     | да           | Идентификатор лота в системе источника. Уникален в рамках `source`.           |
| `title`          | `str`                     | да           | Заголовок лота. Не пустой, не длиннее 1000 символов.                          |
| `description`    | `str \| None`             | нет          | Полное описание.                                                              |
| `category`       | `str \| None`             | нет          | Категория в нормализованном виде (slug). См. §1.3.                            |
| `region`         | `str \| None`             | нет          | Регион в виде кода ОКАТО (2 цифры) ИЛИ строки — нормализация на backend.       |
| `price`          | `Decimal \| None`         | нет          | Текущая цена лота в рублях.                                                   |
| `price_step`     | `Decimal \| None`         | нет          | Шаг понижения цены (для голландского аукциона).                               |
| `source_url`     | `HttpUrl`                 | да           | Прямая ссылка на карточку лота у источника.                                   |
| `auction_date`   | `datetime \| None`        | нет          | Дата проведения торгов (timezone-aware, UTC).                                 |
| `published_at`   | `datetime \| None`        | нет          | Дата публикации лота у источника (timezone-aware, UTC).                       |
| `status`         | `str \| None`             | нет          | Текстовый статус у источника (например, `"active"`, `"cancelled"`).           |
| `images`         | `list[HttpUrl]`           | да (может быть пустым) | Список URL-ссылок на изображения лота.                              |
| `raw`            | `dict[str, Any]`          | да           | Сырые данные источника (для отладки и будущих миграций).                      |

### 1.2 Интерфейс `BaseSource`

```python
class BaseSource(ABC):
    """Абстракция источника лотов. Каждый источник реализует этот интерфейс."""

    name: str  # уникальное имя источника ("efrsb", "torgi_gov")

    async def fetch_lots(
        self,
        since: datetime | None = None,
        filters: ParseFilters | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[ParsedLot]:
        """Асинхронный генератор лотов."""
```

`ParseFilters` — Pydantic-модель с необязательными полями:
`category`, `region`, `price_from`, `price_to`, `query`.

### 1.3 Справочник категорий (slug)

Парсер **обязан** мапить свои категории на этот словарь. Неизвестные — в `null`.

| slug              | Название                |
| ----------------- | ----------------------- |
| `real_estate`     | Недвижимость            |
| `vehicle`         | Транспорт               |
| `equipment`       | Оборудование            |
| `land`            | Земельные участки       |
| `rights`          | Права требования        |
| `securities`      | Ценные бумаги           |
| `inventory`       | ТМЦ и материалы         |
| `other`           | Прочее                  |

### 1.4 Справочник регионов

Используется код ОКАТО (двузначный). Примеры: `45` — Москва, `40` — СПб,
`66` — Свердловская область. Полный seed — в миграции backend. Если парсер
получает только название — передаёт строку; backend нормализует через LIKE.

### 1.5 Контракт логирования парсера

- Логгер: `logging.getLogger("parser.<source>")`.
- Сообщения на русском языке.
- При ошибках извлечения отдельных полей — `warning` с указанием `source_lot_id`.
- При полной невозможности распарсить страницу — `error` c raw HTML-дампом в debug.

---

## 2. Контракт REST API (backend)

Базовый URL: `/api`. Все ответы — JSON, кодировка UTF-8.

### 2.1 Формат ошибок

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Неверный email или пароль"
  }
}
```

Коды ошибок:
`VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`,
`RATE_LIMITED`, `INTERNAL_ERROR`,
`NOT_ADMIN`, `ALREADY_ADMIN`, `USER_BLOCKED`,
`INVALID_SQL`, `SQL_TIMEOUT`, `DML_NOT_CONFIRMED`,
`BOT_OFFLINE`, `JOB_NOT_FOUND`, `PARSER_BUSY`, `TELEGRAM_NOT_LINKED`.

### 2.2 Аутентификация

| Метод | Путь                    | Тело / query                                  | Ответ (200)                                |
| ----- | ----------------------- | --------------------------------------------- | ------------------------------------------ |
| POST  | `/api/auth/register`    | `{email, password}`                           | `{id, email}`                              |
| POST  | `/api/auth/login`       | `{email, password}`                           | `{access_token, token_type, expires_in}` + set HttpOnly cookie `refresh_token` |
| POST  | `/api/auth/refresh`     | cookie `refresh_token`                        | `{access_token, token_type, expires_in}`   |
| POST  | `/api/auth/logout`      | cookie `refresh_token`                        | `204`                                      |
| GET   | `/api/me`               | `Authorization: Bearer <access_token>`        | `{id, email, telegram_linked, digest_time}` |

Пароль: мин. 8 символов, хранится как `bcrypt`. Email приводится к lower-case.

### 2.3 Лоты

| Метод | Путь                | Query                                                                                                                                    | Ответ |
| ----- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| GET   | `/api/lots`         | `query`, `category`, `region`, `price_from`, `price_to`, `date_from`, `date_to`, `sort` (`date_desc`\|`price_asc`\|`price_desc`), `page`, `page_size` (1..100) | `{items: [LotShort], total, page, page_size}` |
| GET   | `/api/lots/{id}`    | —                                                                                                                                        | `LotDetail` |

`LotShort`:

```json
{
  "id": 123,
  "source": "efrsb",
  "title": "Квартира 52 м²",
  "category": "real_estate",
  "region_code": "45",
  "region_name": "Москва",
  "price": "3500000.00",
  "auction_date": "2026-05-20T10:00:00Z",
  "thumbnail": "https://...",
  "is_favorite": false
}
```

`LotDetail` = `LotShort` + `{description, price_step, source_url, images, status, published_at, updated_at}`.

### 2.4 Избранное

| Метод  | Путь                         | Ответ          |
| ------ | ---------------------------- | -------------- |
| GET    | `/api/favorites`             | `{items: [LotShort], total}` |
| POST   | `/api/favorites/{lot_id}`    | `204`          |
| DELETE | `/api/favorites/{lot_id}`    | `204`          |

### 2.5 Сохранённые фильтры

| Метод  | Путь                      | Тело                                                    | Ответ              |
| ------ | ------------------------- | ------------------------------------------------------- | ------------------ |
| GET    | `/api/filters`            | —                                                       | `{items: [SavedFilter]}` |
| POST   | `/api/filters`            | `{name, filter, notify_enabled}`                        | `SavedFilter`      |
| PUT    | `/api/filters/{id}`       | `{name?, filter?, notify_enabled?}`                     | `SavedFilter`      |
| DELETE | `/api/filters/{id}`       | —                                                       | `204`              |

`SavedFilter`:

```json
{
  "id": 10,
  "name": "Квартиры в Москве до 5 млн",
  "filter": {
    "query": "квартира",
    "category": "real_estate",
    "region": "45",
    "price_from": null,
    "price_to": 5000000
  },
  "notify_enabled": true,
  "created_at": "2026-04-24T12:00:00Z"
}
```

### 2.6 Telegram и уведомления

| Метод | Путь                             | Тело              | Ответ                             |
| ----- | -------------------------------- | ----------------- | --------------------------------- |
| POST  | `/api/telegram/link`             | —                 | `{deep_link, token, expires_at}`  |
| POST  | `/api/telegram/unlink`           | —                 | `204`                             |
| PUT   | `/api/notifications/settings`    | `{digest_time}`   | `{digest_time}`                   |
| GET   | `/api/notifications/settings`    | —                 | `{digest_time, telegram_linked}`  |
| POST  | `/api/notifications/test`        | —                 | `204`                             |

`digest_time` — строка формата `"HH:MM"` в таймзоне пользователя (UTC+3 по умолчанию, Moscow).

`POST /api/notifications/test` — отправляет тестовое уведомление в привязанный Telegram. Если Telegram не привязан — `409 {"error": {"code": "TELEGRAM_NOT_LINKED", "message": "..."}}`. Требует авторизации.

### 2.7 Внутренний API (бот ↔ backend)

Защищён shared secret (`X-Internal-Token`).

| Метод | Путь                               | Тело                                          | Ответ                                       |
| ----- | ---------------------------------- | --------------------------------------------- | ------------------------------------------- |
| POST  | `/api/internal/telegram/bind`      | `{token, telegram_user_id, chat_id}`          | `{user_id}` или `404`                       |
| GET   | `/api/internal/outbox`             | `?limit=50`                                   | `{items: [{id, chat_id, text, lot_ids}]}`   |
| POST  | `/api/internal/outbox/{id}/ack`    | `{status: "sent" \| "failed", error?}`        | `204`                                       |
| POST  | `/api/internal/bot/heartbeat`      | `{version?, polling_ok: bool}`                | `204`                                       |
| POST  | `/api/internal/bot/log`            | `{records: [{ts, level, name, message}]}`    | `204` (батч; до 200 записей за вызов)       |

`POST /api/internal/outbox/{id}/ack` теперь принимает тело: при `failed`
сообщение возвращается в очередь с увеличенным `attempt_count`;
после трёх неудач — статус `failed`, в audit пишется ошибка.

### 2.8 Метаданные

| Метод | Путь                 | Ответ                                      |
| ----- | -------------------- | ------------------------------------------ |
| GET   | `/api/meta/categories` | `{items: [{slug, name}]}`                |
| GET   | `/api/meta/regions`  | `{items: [{code, name}]}`                  |

### 2.9 Admin API (`/api/admin/*`)

Все эндпоинты требуют `Authorization: Bearer <access_token>` пользователя
с `is_admin = true`. Иначе — `403 {"error": {"code": "NOT_ADMIN"}}`.
Любое изменение состояния пишется в `admin_audit_log` (см. §3.1).

#### 2.9.1 Здоровье и метрики

| Метод | Путь                                  | Ответ |
| ----- | ------------------------------------- | ----- |
| GET   | `/api/admin/health`                   | `HealthReport` |
| GET   | `/api/admin/stats`                    | `StatsReport` |

`HealthReport`:
```json
{
  "db": {"ok": true, "latency_ms": 3},
  "scheduler": {"running": true, "jobs": [{"id": "parser_tick", "next_run": "...", "paused": false}]},
  "outbox": {"pending": 0, "failed": 0, "oldest_pending_age_seconds": null},
  "bot": {"online": true, "last_heartbeat_at": "..."},
  "parser": {"last_runs": [ParserRun, ...]},
  "process": {"version": "1.0.0", "uptime_seconds": 1234, "rss_mb": 142, "cpu_percent": 1.2}
}
```

`StatsReport`:
```json
{
  "users_total": 42, "users_with_telegram": 17, "users_admin": 1, "users_blocked": 0,
  "lots_total": 1234, "lots_by_source": {"torgi_gov": 1234, "efrsb": 0},
  "lots_added_24h": 56,
  "favorites_total": 312, "filters_total": 88, "filters_with_notify": 41,
  "outbox": {"pending": 0, "sent": 1500, "failed": 2},
  "errors_24h": 3
}
```

#### 2.9.2 Логи (live tail)

| Метод | Путь                                  | Ответ |
| ----- | ------------------------------------- | ----- |
| GET   | `/api/admin/logs?level=&q=&limit=200` | `{items: [LogRecord]}` (снапшот кольцевого буфера) |
| GET   | `/api/admin/logs/stream`              | `text/event-stream` SSE, `data: {LogRecord}` |

`LogRecord`:
```json
{"ts":"2026-04-25T07:00:00Z","level":"INFO","source":"backend|bot","logger":"app.ingest","message":"..."}
```

Буфер — кольцевой, общий для backend и bot. Логи бота попадают через
`POST /api/internal/bot/log`. Размер буфера — `ADMIN_LOG_BUFFER_SIZE`.

#### 2.9.3 Шедулер и парсер

| Метод | Путь                                          | Тело                  | Ответ |
| ----- | --------------------------------------------- | --------------------- | ----- |
| GET   | `/api/admin/scheduler/jobs`                   | —                     | `{items: [SchedulerJob]}` |
| POST  | `/api/admin/scheduler/jobs/{id}/run`          | —                     | `204` |
| POST  | `/api/admin/scheduler/jobs/{id}/pause`        | —                     | `204` |
| POST  | `/api/admin/scheduler/jobs/{id}/resume`       | —                     | `204` |
| POST  | `/api/admin/parser/run`                       | `{source: "torgi_gov" \| "all"}` | `ParserRunReport` |
| GET   | `/api/admin/parser/runs?limit=50`             | —                     | `{items: [ParserRun]}` |

`SchedulerJob`: `{id, name, next_run_time, trigger, paused}`.
`ParserRunReport`: `{source, status, lots_seen, lots_new, lots_updated, lots_skipped, error?, started_at, finished_at}`.

#### 2.9.4 Пользователи

| Метод   | Путь                                    | Тело / query                           | Ответ |
| ------- | --------------------------------------- | -------------------------------------- | ----- |
| GET     | `/api/admin/users?q=&page=&page_size=`  | —                                      | `{items: [AdminUser], total, page, page_size}` |
| GET     | `/api/admin/users/{id}`                 | —                                      | `AdminUserDetail` |
| PATCH   | `/api/admin/users/{id}`                 | `{full_name?, is_admin?, is_blocked?, digest_time?, digest_tz?}` | `AdminUserDetail` |
| DELETE  | `/api/admin/users/{id}`                 | —                                      | `204` |
| POST    | `/api/admin/users/{id}/unlink-telegram` | —                                      | `204` |

`AdminUser`:
```json
{
  "id": 1, "email": "...", "is_admin": false, "is_blocked": false,
  "telegram_linked": true, "telegram_user_id": 123456789,
  "digest_time": "09:00", "digest_tz": "Europe/Moscow",
  "favorites_count": 5, "filters_count": 2,
  "created_at": "..."
}
```

`AdminUserDetail` = `AdminUser` + `{recent_outbox: [OutboxItem], recent_filters: [SavedFilter]}`.

Удаление себя самого — `409 ALREADY_ADMIN`. Снятие `is_admin` с последнего
оставшегося админа — `409 ALREADY_ADMIN`.

#### 2.9.5 Лоты

| Метод   | Путь                                                  | Ответ |
| ------- | ----------------------------------------------------- | ----- |
| GET     | `/api/admin/lots?source=&status=&q=&page=&page_size=` | `{items: [LotShort], total}` |
| DELETE  | `/api/admin/lots/{id}`                                | `204` |
| POST    | `/api/admin/lots/{id}/refresh`                        | `LotDetail` (re-fetch у источника) |

#### 2.9.6 Outbox

| Метод   | Путь                                                            | Ответ |
| ------- | --------------------------------------------------------------- | ----- |
| GET     | `/api/admin/outbox?status=pending\|sent\|failed&limit=&offset=` | `{items: [OutboxItem], total}` |
| POST    | `/api/admin/outbox/{id}/retry`                                  | `204` |
| DELETE  | `/api/admin/outbox/{id}`                                        | `204` |

`OutboxItem`: `{id, user_id, user_email, chat_id, text, lot_ids, status, attempt_count, error?, created_at, sent_at?}`.

#### 2.9.7 Бот: личные сообщения и рассылка

| Метод | Путь                          | Тело                                                                                  | Ответ |
| ----- | ----------------------------- | ------------------------------------------------------------------------------------- | ----- |
| POST  | `/api/admin/bot/send`         | `{user_id, text, parse_mode?: "html" \| "markdown"}`                                  | `{outbox_id}` |
| POST  | `/api/admin/bot/broadcast`    | `{text, parse_mode?, audience: {has_telegram: true, has_filter?: bool, user_ids?: [int]}}` | `{queued: 42}` |

Если у пользователя не привязан Telegram — `409 TELEGRAM_NOT_LINKED`.
Если бот offline (нет heartbeat более 2 минут) — предупреждение в ответе:
`{"outbox_id": ..., "warning": "BOT_OFFLINE"}` (HTTP 200, в очередь сообщение
кладётся, но не уйдёт пока бот не поднимется).

#### 2.9.8 БД-консоль

| Метод | Путь                                          | Тело / query                           | Ответ |
| ----- | --------------------------------------------- | -------------------------------------- | ----- |
| GET   | `/api/admin/db/tables`                        | —                                      | `{items: [{name, rows_estimate}]}` |
| GET   | `/api/admin/db/tables/{name}?limit=&offset=`  | —                                      | `{columns: [...], rows: [...], total}` |
| GET   | `/api/admin/db/reports`                       | —                                      | `{items: [{id, title, sql}]}` (готовые отчёты) |
| POST  | `/api/admin/db/reports/{id}/run`              | —                                      | `QueryResult` |
| POST  | `/api/admin/db/query`                         | `{sql, mode: "readonly" \| "danger", confirm?: true}` | `QueryResult` |

`QueryResult`:
```json
{
  "columns": ["id", "email"],
  "rows": [[1, "..."]],
  "row_count": 1,
  "elapsed_ms": 12,
  "truncated": false
}
```

Правила `POST /api/admin/db/query`:
- Запрос парсится через `sqlparse`. В режиме `readonly` разрешены только
  `SELECT` и `WITH ... SELECT`. Любой `INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE`
  → `400 INVALID_SQL`.
- В режиме `danger` дозволены DML (`INSERT/UPDATE/DELETE`). DDL
  (`DROP/ALTER/TRUNCATE/CREATE`) запрещены навсегда. Без `confirm: true` →
  `400 DML_NOT_CONFIRMED`.
- Для каждого запроса:
  `SET LOCAL statement_timeout = '5s'`, `SET LOCAL idle_in_transaction_session_timeout = '5s'`.
- Для `SELECT` без явного `LIMIT` — оборачиваем в `SELECT ... LIMIT 500` и
  выставляем `truncated: true` если строк ровно 500.
- Любой запуск пишется в audit с маскированием (без полного текста, только
  fingerprint и `mode`).

Готовые отчёты (id, в комплекте «из коробки»):
- `users_with_telegram` — все юзеры с привязкой.
- `top_lots_by_favorites` — топ-20 самых добавленных в избранное.
- `outbox_failed_24h` — отказы доставки за сутки.
- `parser_runs_summary` — агрегация по источникам и статусам за 7 дней.
- `daily_signups_30d` — регистрации по дням.

### 2.10 Соглашения для админских ответов

- Время — `TIMESTAMPTZ` в UTC, формат ISO-8601 с `Z`.
- Денежные значения — строки (`"3500000.00"`).
- Все списочные эндпоинты поддерживают `page`/`page_size` (1..100).
- В ошибках с подробностями — поле `error.details: object`.

---

## 3. Модель данных (PostgreSQL)

### 3.1 Таблицы

```sql
-- Пользователи
CREATE TABLE users (
    id                   BIGSERIAL PRIMARY KEY,
    email                CITEXT NOT NULL UNIQUE,
    password_hash        VARCHAR(255) NOT NULL,
    full_name            VARCHAR(255),
    is_admin             BOOLEAN NOT NULL DEFAULT FALSE,
    is_blocked           BOOLEAN NOT NULL DEFAULT FALSE,
    telegram_user_id     BIGINT UNIQUE,
    telegram_chat_id     BIGINT,
    telegram_link_token  VARCHAR(64) UNIQUE,
    telegram_token_expires_at TIMESTAMPTZ,
    digest_time          TIME,       -- локальное время отправки дайджеста
    digest_tz            VARCHAR(64) NOT NULL DEFAULT 'Europe/Moscow',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX users_is_admin_idx   ON users (is_admin) WHERE is_admin = TRUE;
CREATE INDEX users_is_blocked_idx ON users (is_blocked) WHERE is_blocked = TRUE;

-- Справочник регионов (ОКАТО)
CREATE TABLE regions (
    code      VARCHAR(8) PRIMARY KEY,
    name      VARCHAR(255) NOT NULL
);

-- Справочник категорий
CREATE TABLE categories (
    slug      VARCHAR(32) PRIMARY KEY,
    name      VARCHAR(255) NOT NULL
);

-- Лоты
CREATE TABLE lots (
    id             BIGSERIAL PRIMARY KEY,
    source         VARCHAR(32) NOT NULL,
    source_lot_id  VARCHAR(128) NOT NULL,
    title          TEXT NOT NULL,
    description    TEXT,
    category       VARCHAR(32) REFERENCES categories(slug),
    region_code    VARCHAR(8)  REFERENCES regions(code),
    price          NUMERIC(18,2),
    price_step     NUMERIC(18,2),
    source_url     TEXT NOT NULL,
    auction_date   TIMESTAMPTZ,
    published_at   TIMESTAMPTZ,
    status         VARCHAR(64),
    images         JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw            JSONB NOT NULL DEFAULT '{}'::jsonb,
    search_tsv     TSVECTOR,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_lot_id)
);
CREATE INDEX lots_search_idx   ON lots USING gin(search_tsv);
CREATE INDEX lots_title_trgm   ON lots USING gin(title gin_trgm_ops);
CREATE INDEX lots_filters_idx  ON lots (category, region_code, price, auction_date);
CREATE INDEX lots_first_seen   ON lots (first_seen_at DESC);

-- Избранное
CREATE TABLE favorites (
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lot_id      BIGINT NOT NULL REFERENCES lots(id)  ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, lot_id)
);

-- Сохранённые фильтры
CREATE TABLE saved_filters (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(128) NOT NULL,
    filter          JSONB NOT NULL,
    notify_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX saved_filters_user ON saved_filters (user_id);

-- Журнал отправленных уведомлений (идемпотентность)
CREATE TABLE notification_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filter_id   BIGINT NOT NULL REFERENCES saved_filters(id) ON DELETE CASCADE,
    lot_id      BIGINT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, filter_id, lot_id)
);

-- Очередь исходящих сообщений для бота
CREATE TABLE outbox (
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id        BIGINT NOT NULL,
    text           TEXT NOT NULL,
    parse_mode     VARCHAR(16),                 -- 'html' | 'markdown' | NULL
    lot_ids        JSONB NOT NULL DEFAULT '[]'::jsonb,
    status         VARCHAR(16) NOT NULL DEFAULT 'pending', -- pending|sent|failed
    attempt_count  INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT,
    source         VARCHAR(16) NOT NULL DEFAULT 'digest',  -- digest|admin|test
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at        TIMESTAMPTZ
);
CREATE INDEX outbox_pending_idx ON outbox (created_at) WHERE status = 'pending';
CREATE INDEX outbox_status_idx  ON outbox (status, created_at DESC);

-- Журнал запусков парсера
CREATE TABLE parser_runs (
    id           BIGSERIAL PRIMARY KEY,
    source       VARCHAR(32) NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    status       VARCHAR(16) NOT NULL DEFAULT 'running',
    lots_seen    INTEGER NOT NULL DEFAULT 0,
    lots_new     INTEGER NOT NULL DEFAULT 0,
    lots_updated INTEGER NOT NULL DEFAULT 0,
    triggered_by VARCHAR(16) NOT NULL DEFAULT 'schedule', -- schedule|admin
    triggered_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    error        TEXT
);
CREATE INDEX parser_runs_started_idx ON parser_runs (started_at DESC);

-- Аудит-журнал админских действий
CREATE TABLE admin_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    admin_user_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(64) NOT NULL,    -- USER_DELETE, BOT_BROADCAST, DB_QUERY, ...
    target_type     VARCHAR(32),             -- user, lot, outbox, sql, ...
    target_id       VARCHAR(64),             -- id или fingerprint sql
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip              VARCHAR(64),
    user_agent      VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX admin_audit_user_idx    ON admin_audit_log (admin_user_id, created_at DESC);
CREATE INDEX admin_audit_action_idx  ON admin_audit_log (action, created_at DESC);

-- Heartbeat бота (одна строка, обновляется ботом каждые 30 сек)
CREATE TABLE bot_heartbeat (
    id              SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    polling_ok      BOOLEAN NOT NULL DEFAULT TRUE,
    version         VARCHAR(32)
);
INSERT INTO bot_heartbeat (id) VALUES (1) ON CONFLICT DO NOTHING;
```

### 3.2 Расширения PostgreSQL

- `CREATE EXTENSION IF NOT EXISTS citext;`
- `CREATE EXTENSION IF NOT EXISTS pg_trgm;`

### 3.3 Обновление `search_tsv`

Триггер + функция:

```sql
CREATE FUNCTION lots_search_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.search_tsv :=
        setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER lots_tsv_trigger
BEFORE INSERT OR UPDATE ON lots
FOR EACH ROW EXECUTE FUNCTION lots_search_tsv_update();
```

---

## 4. Конвенции

- Все timestamps в БД — `TIMESTAMPTZ` в UTC. Конвертация в локальное время —
  на стороне backend при формировании ответа и на стороне фронта при рендере.
- Цены — `NUMERIC(18, 2)` в БД, строки в JSON (чтобы не терять точность).
- Пагинация — `page` (с 1) и `page_size` (дефолт 20, макс 100).
- Авторизация: access токен — в заголовке `Authorization: Bearer`;
  refresh токен — в HttpOnly cookie `refresh_token` с `SameSite=Lax`.
- Логи на русском: `logging.getLogger(__name__)`, формат —
  `%(asctime)s %(levelname)s %(name)s: %(message)s`.
- Docstrings — на русском, в Google-стиле, для всех публичных функций и классов.
