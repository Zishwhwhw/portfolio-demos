#!/bin/bash
# Демо-бот для портфолио: токен в .env (не в git), админ — владелец.
cd "$(dirname "$0")"
set -a; . ./.env; set +a
export ADMIN_ID="${ADMIN_ID:-2142303952}" WEBAPP_URL="${WEBAPP_URL:-https://zishwhwhw.github.io/portfolio-demos/miniapp/}" DB_PATH="${DB_PATH:-$PWD/orders.db}"
exec ./.venv/bin/python main.py
