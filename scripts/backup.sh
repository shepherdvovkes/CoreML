#!/bin/bash

# Скрипт для резервного копирования данных CoreML
# Использование: ./scripts/backup.sh [backup_dir]

set -e

BACKUP_DIR=${1:-./backups}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/coreml_backup_$TIMESTAMP"

echo "💾 Создание резервной копии CoreML..."
echo "📁 Директория: $BACKUP_PATH"

# Создание директории для бэкапов
mkdir -p "$BACKUP_PATH"

# Бэкап данных Qdrant
echo "📦 Резервное копирование Qdrant..."
if docker ps | grep -q coreml_qdrant; then
    docker exec coreml_qdrant tar czf /tmp/qdrant_backup.tar.gz /qdrant/storage
    docker cp coreml_qdrant:/tmp/qdrant_backup.tar.gz "$BACKUP_PATH/qdrant_backup.tar.gz"
    docker exec coreml_qdrant rm /tmp/qdrant_backup.tar.gz
    echo "✅ Qdrant скопирован"
else
    echo "⚠️  Qdrant контейнер не запущен"
fi

# Бэкап данных Redis (опционально)
echo "📦 Резервное копирование Redis..."
if docker ps | grep -q coreml_redis; then
    docker exec coreml_redis redis-cli SAVE
    docker cp coreml_redis:/data/dump.rdb "$BACKUP_PATH/redis_dump.rdb" || true
    echo "✅ Redis скопирован"
else
    echo "⚠️  Redis контейнер не запущен"
fi

# Бэкап локальных данных
if [ -d "./data" ]; then
    echo "📦 Резервное копирование локальных данных..."
    tar czf "$BACKUP_PATH/data_backup.tar.gz" ./data
    echo "✅ Локальные данные скопированы"
fi

# Бэкап конфигурации
if [ -f ".env" ]; then
    echo "📦 Резервное копирование конфигурации..."
    cp .env "$BACKUP_PATH/.env"
    echo "✅ Конфигурация скопирована"
fi

# Создание архива
echo "📦 Создание архива..."
cd "$BACKUP_DIR"
tar czf "coreml_backup_$TIMESTAMP.tar.gz" "coreml_backup_$TIMESTAMP"
rm -rf "coreml_backup_$TIMESTAMP"
cd - > /dev/null

echo "✅ Резервное копирование завершено!"
echo "📁 Файл: $BACKUP_DIR/coreml_backup_$TIMESTAMP.tar.gz"

