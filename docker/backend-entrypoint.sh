#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-0}" = "1" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
