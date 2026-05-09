#!/usr/bin/env bash
# Выполнять на сервере из корня репозитория (рядом с docker-compose.yml).
# Вызывается вручную или из GitHub Actions по SSH.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="${DEPLOY_BRANCH:-main}"
git fetch origin "$BRANCH"
git checkout -B "$BRANCH" "origin/$BRANCH"

docker compose up -d
# Фронт подхватывается с диска без рестарта; backend — uvicorn --reload; бот — без hot-reload
docker compose restart backend bot

echo "Deploy OK ($(date -Iseconds))"
