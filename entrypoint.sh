#!/bin/sh
set -e

echo "Waiting for database..."
python manage.py migrate --no-input
python manage.py collectstatic --no-input --clear

exec "$@"
