# Telegram-бот агрегатора торгов

Бот уведомляет пользователей о новых лотах согласно их сохранённым фильтрам.

## Зависимости

- Python 3.11+
- [aiogram](https://docs.aiogram.dev/) 3.x (Telegram Bot API)
- [httpx](https://www.python-httpx.org/) — HTTP-клиент для backend API

## Установка

```bash
cd bot/
pip install -e .
```

Для разработки (тесты):
```bash
pip install -e ".[dev]"
```

## Конфигурация

Создайте файл `.env` в директории `bot/` (или используйте корневой `.env`):

```dotenv
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...     # Получить у @BotFather
BACKEND_INTERNAL_URL=http://localhost:8000  # URL backend
INTERNAL_API_TOKEN=change-me-internal-token # Должен совпадать с backend
```

Если `TELEGRAM_BOT_TOKEN` не задан, бот запустится в режиме ожидания и будет
логировать предупреждение — это позволяет тестам работать без реального токена.

## Запуск

```bash
python -m bot.main
```

## Тесты

```bash
cd bot/
pytest
```

Тесты используют `respx` для мокирования HTTP-запросов к backend.
Реальный Telegram-токен не требуется.

## Как работает привязка аккаунта

1. Пользователь на сайте нажимает «Привязать Telegram» → получает deep-link вида
   `https://t.me/<bot_username>?start=<token>`.
2. Переходит по ссылке → бот получает команду `/start <token>`.
3. Бот вызывает `POST /api/internal/telegram/bind` с токеном и Telegram ID.
4. Backend проверяет токен и сохраняет `telegram_user_id` / `telegram_chat_id`.

## Архитектура

```
bot/
  bot/
    main.py              # Точка входа: polling + outbox_loop параллельно
    config.py            # pydantic-settings
    handlers/
      start.py           # /start [token], /help
    services/
      backend_client.py  # HTTP-клиент для внутреннего API
      outbox_poller.py   # Цикл опроса очереди outbox
  tests/
    test_start.py        # Тесты BackendClient.bind_telegram
    test_outbox_poller.py # Тесты get_outbox / ack_outbox
```
