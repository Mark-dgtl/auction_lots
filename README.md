# Агрегатор торгов

Веб-сервис для агрегации информации о лотах с электронных торговых площадок.
Поиск, фильтрация, избранное, ежедневные уведомления в Telegram.

**Активные источники:** `torgi.gov.ru` — публичный JSON-API (работает).

**Заморожено:** `bankrot.fedresurs.ru` (ЕФРСБ) — с апреля 2026 API закрыт
Qrator'ом; код источника, контракты и тесты сохранены, источник исключён
из `PARSER_SOURCES` до восстановления доступа или интеграции Playwright.
Подробнее — в шапке `parser/parser/sources/efrsb.py` и в `docs/CONTRACTS.md`.

## Стек

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, APScheduler.
- **БД**: PostgreSQL 16 (full-text + pg_trgm).
- **Парсер**: httpx + BeautifulSoup/lxml.
- **Telegram-бот**: aiogram 3.
- **Фронтенд**: HTML5, CSS3, vanilla JavaScript (ES6 modules), nginx.

## Структура репозитория

```
backend/   — FastAPI-приложение и миграции
parser/    — Python-пакет парсинга, используется backend
bot/       — Telegram-бот
frontend/  — статический фронтенд под nginx
docs/      — контракты и документация
```

## Быстрый старт

```bash
cp .env.example .env
# Отредактируйте .env: минимум TELEGRAM_BOT_TOKEN и TELEGRAM_BOT_USERNAME
docker compose up --build
```

После старта:

- Фронтенд: <http://localhost:8080>
- API: <http://localhost:8000/api>
- OpenAPI docs: <http://localhost:8000/docs>
- Админ-панель: <http://localhost:8080/admin.html>
  (логин из `.env`: `ADMIN_EMAIL` / `ADMIN_PASSWORD`,
  дефолт — `admin@tenders.app` / `admin12345` — обязательно сменить
  в проде).

## Админ-панель

Отдельная SPA на `/admin.html`. Доступ — только пользователям с
`is_admin = TRUE` (бутстрап из env при первом старте).

Возможности:

- **Dashboard** — здоровье БД/scheduler'a/бота, метрики процесса,
  агрегированная статистика (юзеры, лоты, outbox, ошибки).
- **Logs** — live-tail логов backend и бота через SSE
  (`/api/admin/logs/stream`). Кольцевой буфер на 2000 записей.
- **Users** — список, редактирование (`is_admin`, `is_blocked`,
  `digest_time`), отвязка Telegram, удаление. Защита: нельзя
  удалить последнего админа и снять права с самого себя.
- **Lots** — фильтр по источнику/статусу, удаление, re-parse.
- **Outbox** — фильтр по статусу `pending|sent|failed`, retry, delete.
- **Parser** — список APScheduler-jobs (Pause/Resume/Run-now),
  on-demand запуск по источнику, история последних запусков.
- **Bot** — отправка личного сообщения пользователю и broadcast
  по аудитории (`has_telegram`, `has_filter`, `user_ids[]`).
- **DB-консоль** — список таблиц, готовые отчёты и произвольный SQL
  в двух режимах:
  - `readonly`: только `SELECT/WITH`, авто-`LIMIT 500`,
    `statement_timeout=5s`.
  - `danger`: `INSERT/UPDATE/DELETE` с обязательным `confirm: true`.
    DDL (`DROP/ALTER/TRUNCATE/CREATE/...`) запрещён всегда.

Все деструктивные действия логируются в `admin_audit_log` с указанием
admin_id, action, payload и timestamp.

## Разработка без Docker

См. `backend/README.md`, `parser/README.md`, `bot/README.md`.

## Документация

- [docs/CONTRACTS.md](docs/CONTRACTS.md) — контракты API, парсера, БД.
