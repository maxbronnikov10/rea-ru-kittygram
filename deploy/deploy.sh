#!/usr/bin/env bash
# Деплой Kittygram на сервер Ubuntu 22.04/24.04: nginx + gunicorn + systemd,
# база PostgreSQL. Запускать из корня клонированного репозитория:
#   SERVER_NAME=<IP или домен> bash deploy/deploy.sh
# Повторный запуск обновляет код, зависимости, миграции и статику.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="${APP_USER:-$(whoami)}"
SERVER_NAME="${SERVER_NAME:-_}"
WEB_ROOT=/var/www/kittygram

echo "==> Каталог проекта: $APP_DIR, пользователь: $APP_USER"

echo "==> 1/7 Системные пакеты"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip nginx postgresql \
    > /dev/null
# Node.js нужен только для сборки фронтенда; из apt ставим, если его нет
# (в Ubuntu 24.04 это Node 18, в 22.04 — слишком старый Node 12).
command -v node > /dev/null || sudo apt-get install -y -qq nodejs npm > /dev/null

if [ ! -f "$APP_DIR/.env" ]; then
    echo "Нет файла $APP_DIR/.env — создайте его из .env.example" >&2
    exit 1
fi
set -a; . "$APP_DIR/.env"; set +a

echo "==> 2/7 База данных PostgreSQL"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'" \
    | grep -q 1 || sudo -u postgres psql -c \
    "CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" \
    | grep -q 1 || sudo -u postgres psql -c \
    "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"

echo "==> 3/7 Виртуальное окружение и зависимости"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"

echo "==> 4/7 Миграции и статика бэкенда"
cd "$APP_DIR/backend"
"$APP_DIR/venv/bin/python" manage.py migrate --noinput
"$APP_DIR/venv/bin/python" manage.py collectstatic --noinput > /dev/null

echo "==> 5/7 Сборка фронтенда"
NODE_MAJOR=$(node -v 2>/dev/null | sed 's/v\([0-9]*\).*/\1/' || echo 0)
if [ "${NODE_MAJOR:-0}" -lt 18 ]; then
    echo "Нужен Node.js 18+, установлен: $(node -v 2>/dev/null || echo нет)" >&2
    exit 1
fi
cd "$APP_DIR/frontend"
npm ci --no-audit --no-fund --loglevel=error
npm run build > /dev/null

sudo mkdir -p "$WEB_ROOT/media"
sudo cp -r "$APP_DIR/frontend/build/." "$WEB_ROOT/"
sudo mkdir -p "$WEB_ROOT/static"
sudo cp -r "$APP_DIR/backend/collected_static/." "$WEB_ROOT/static/"
sudo chown -R "$APP_USER":www-data "$WEB_ROOT/media"

echo "==> 6/7 Gunicorn как сервис systemd"
sed -e "s|{{USER}}|$APP_USER|g" -e "s|{{APP_DIR}}|$APP_DIR|g" \
    "$APP_DIR/deploy/gunicorn_kittygram.service" \
    | sudo tee /etc/systemd/system/gunicorn_kittygram.service > /dev/null
grep -q '^MEDIA_ROOT=' "$APP_DIR/.env" \
    || echo "MEDIA_ROOT=$WEB_ROOT/media" >> "$APP_DIR/.env"
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn_kittygram
sudo systemctl restart gunicorn_kittygram

echo "==> 7/7 Nginx"
sed -e "s|{{SERVER_NAME}}|$SERVER_NAME|g" \
    "$APP_DIR/deploy/nginx_kittygram.conf" \
    | sudo tee /etc/nginx/sites-available/kittygram > /dev/null
sudo ln -sf /etc/nginx/sites-available/kittygram \
    /etc/nginx/sites-enabled/kittygram
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "==> Готово: http://$SERVER_NAME/ (API: /api/, Swagger: /api/docs/)"
