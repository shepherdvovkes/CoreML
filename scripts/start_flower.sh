#!/bin/bash
# Скрипт для запуска Flower (мониторинг Celery)

set -e

echo "Starting Flower..."

# Активация виртуального окружения (если используется)
# source venv/bin/activate

# Запуск Flower
celery -A core.celery_app flower \
    --port=5555 \
    --broker=redis://localhost:6379/0 \
    --backend=redis://localhost:6379/0



