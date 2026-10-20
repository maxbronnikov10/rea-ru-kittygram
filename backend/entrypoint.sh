#!/bin/sh
# Перед запуском gunicorn: миграции и сбор статики Django в общий том,
# откуда её раздаёт nginx (контейнер gateway).
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
mkdir -p /backend_static/static
cp -r /app/collected_static/. /backend_static/static/

exec "$@"
