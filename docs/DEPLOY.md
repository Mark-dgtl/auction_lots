# Деплой на VPS (Docker Compose)

## 1. Подготовка на сервере

```bash
cd /path/to/auction_lots   # или ваш каталог клона
cp .env.example .env
nano .env   # или vim
```

**Обязательно задать в `.env`:**


| Переменная                                    | Комментарий                                                                                    |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `POSTGRES_`*                                  | Сильный `POSTGRES_PASSWORD`; имя БД/юзера можно оставить `tenders`                             |
| `DATABASE_URL`                                | Должен совпадать с `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, хост `db`, порт `5432` |
| `JWT_SECRET`, `INTERNAL_API_TOKEN`            | Случайные длинные строки, не как в примере                                                     |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` | Из @BotFather                                                                                  |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`               | Пароль сменить с дефолтного                                                                    |
| `CORS_ORIGINS`                                | Публичные URL фронта, напр. `https://yourdomain.ru,http://yourdomain.ru`                       |
| `FRONTEND_API_BASE_URL`                       | URL API **из браузера**, напр. `https://yourdomain.ru/api` или `https://api.yourdomain.ru/api` |


Первый запуск (сборка образов + миграции Alembic выполняются при старте backend):

```bash
docker compose up --build -d
```

Проверка:

- API: `http://СЕРВЕР:8000/docs`
- Фронт: `http://СЕРВЕР:8080`

Порт **5433** на хосте проброшен в Postgres — удобно для `pg_dump`/`psql` с сервера; снаружи лучше **закрыть firewall** для 5433, 8000, 8080, если доступ только через nginx/Caddy.

## 2. Прод: домен и HTTPS

Поставьте **Caddy** или **nginx** на хосте (не обязательно в Docker): прокси на `127.0.0.1:8080` (фронт) и при необходимости отдельный `location /api/` → `127.0.0.1:8000`. После этого обновите `CORS_ORIGINS` и `FRONTEND_API_BASE_URL`, перезапустите backend:

```bash
docker compose restart backend
```

## 3. Перенос базы данных

### Вариант A: Пустая БД на сервере (нет старых данных)

Ничего делать не нужно: при первом `docker compose up` backend выполнит `alembic upgrade head` и создаст схему. Админ из `.env` создаётся bootstrap’ом, если в таблице пользователей ещё нет админов.

### Вариант B: Копия данных со старой машины (PostgreSQL)

**На старой машине** (где уже крутится такой же проект или тот же Postgres 16):

Логический дамп (SQL):

```bash
# если Postgres в compose с пробросом 5433 на хост:
pg_dump -h 127.0.0.1 -p 5433 -U tenders -d tenders --no-owner --no-acl -F p -f tenders_backup.sql
```

Или из контейнера:

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl -F p > tenders_backup.sql
```

Перекинуть файл на VPS (`scp`, `rsync`).

**На сервере** перед импортом остановите приложения, чтобы не писали в БД:

```bash
cd /path/to/project
docker compose stop backend bot
```

Убедитесь, что контейнер `db` запущен. Импорт (перезапишет данные в существующей БД — при необходимости сначала пересоздайте volume):

```bash
docker compose start db
# подождать healthcheck
docker compose exec -T db psql -U tenders -d tenders -v ON_ERROR_STOP=1 < tenders_backup.sql
```

Затем:

```bash
docker compose up -d
```

Backend снова выполнит `alembic upgrade head` — для уже заполненной БД миграции должны пройти как «уже применены» или догнать только недостающие ревизии.

**Важно:**

- Логин/пароль роли в дампе должны совпадать с `POSTGRES_USER` / `POSTGRES_PASSWORD` в `.env` на сервере, либо используйте `--no-owner` и создайте пользователя как в `.env` до импорта.
- Версия PostgreSQL на сервере — **16** (как в `docker-compose.yml`); дамп с другой мажорной версии может потребовать промежуточный апгрейд или `pg_dump` с новой версии клиента.

### Вариант C: Кастомный формат (`-Fc`) и `pg_restore`

```bash
pg_dump -h ... -Fc -f tenders.dump ...
docker compose exec -T db pg_restore -U tenders -d tenders --no-owner --clean --if-exists < tenders.dump
```

(Для `pg_restore` из stdin иногда удобнее скопировать файл в контейнер или использовать `cat tenders.dump | docker compose exec -T db pg_restore ...`.)

## 4. Бэкапы на проде

Периодически:

```bash
docker compose exec -T db pg_dump -U tenders -d tenders -F c -f /tmp/t.dump \
  && docker compose cp db:/tmp/t.dump ./backup-$(date -I).dump
```

Храните дампы вне сервера.

## 5. CI/CD

См. `.github/workflows/deploy.yml` и `scripts/deploy.sh`: на сервере нужен клон репо, `.env`, доступ `git fetch` и Docker. После пуша в `main` скрипт делает `git pull` и `docker compose up -d` + restart backend/bot.

## 6. Доступ по IP без :8080 (nginx на хосте)

Фронт в Docker слушает **8080** (`8080:80` в compose). Чтобы открывать сайт как `http://IP/`:

1. На VPS: `curl -I http://127.0.0.1:8080/` — должен отвечать ваш фронт (из каталога проекта: `docker compose up -d`).
2. Системный nginx проксирует 80 → 8080 (`/etc/nginx/sites-available/auction`, `proxy_pass http://127.0.0.1:8080;`).
3. Отключите дефолтный сайт: `rm /etc/nginx/sites-enabled/default`, `nginx -t && systemctl reload nginx`.
4. В `.env`: `CORS_ORIGINS=http://ВАШ_IP`, затем `docker compose restart backend`.

Команды `docker compose` выполняйте **в каталоге клона репозитория**, не из `/root/` с чужим compose-файлом.
