#!/bin/bash
set -e

echo "Waiting for MySQL..."
until mysqladmin ping -h"${MYSQL_HOST}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" --ssl=0 --silent; do
  sleep 2
  echo "MySQL not ready..."
done
echo "MySQL is ready!"

if [ "$SERVICE" = "web" ]; then
    echo "Running DB migrations..."
    flask db upgrade
    echo "Seeding default admin (if not exists)..."
    python -m app.seed
    echo "Starting Gunicorn..."
    exec gunicorn -w 4 -b 0.0.0.0:8000 run:app --log-level info

fi

if [ "$SERVICE" = "celery_worker" ]; then
    echo "Starting Celery Worker..."
    exec celery -A app.celery_app.celery worker --loglevel=info
fi

if [ "$SERVICE" = "celery_beat" ]; then
    echo "Starting Celery Beat..."
    exec celery -A app.celery_app.celery beat --loglevel=info
fi
