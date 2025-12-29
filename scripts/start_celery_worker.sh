#!/bin/bash
# Скрипт для запуска Celery worker

set -e

echo "Starting Celery worker..."

# Активация виртуального окружения (если используется)
# source venv/bin/activate

# Запуск worker
celery -A core.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --max-tasks-per-child=1000 \
    --time-limit=300 \
    --soft-time-limit=240



