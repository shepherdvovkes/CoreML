#!/bin/bash

# Скрипт для развертывания кнопок приложений на lexapp.co.ua
# Использование: ./deploy.sh [user@]hostname [remote_path]

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Параметры
REMOTE_HOST="${1:-user@lexapp.co.ua}"
REMOTE_PATH="${2:-/var/www/lexapp.co.ua/badges}"

echo -e "${GREEN}🚀 Развертывание кнопок приложений на ${REMOTE_HOST}${NC}"
echo -e "${YELLOW}Удаленный путь: ${REMOTE_PATH}${NC}"
echo ""

# Проверка наличия директории
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ ! -d "$SCRIPT_DIR" ]; then
    echo "❌ Ошибка: Директория не найдена"
    exit 1
fi

# Создание удаленной директории
echo "📁 Создание удаленной директории..."
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_PATH"

# Копирование файлов
echo "📦 Копирование файлов..."
rsync -avz --progress \
    "$SCRIPT_DIR/" \
    "$REMOTE_HOST:$REMOTE_PATH/"

# Установка прав доступа
echo "🔐 Установка прав доступа..."
ssh "$REMOTE_HOST" "chmod -R 755 $REMOTE_PATH && chown -R www-data:www-data $REMOTE_PATH 2>/dev/null || chmod -R 755 $REMOTE_PATH"

echo ""
echo -e "${GREEN}✅ Развертывание завершено!${NC}"
echo ""
echo "📋 Следующие шаги:"
echo "1. Настройте nginx для обслуживания статических файлов из $REMOTE_PATH"
echo "2. Обновите ссылки в index.html на реальные ссылки ваших приложений"
echo "3. Проверьте доступность: https://lexapp.co.ua/badges/index.html"
echo ""
echo "Пример конфигурации nginx:"
echo "---"
echo "location /badges {"
echo "    alias $REMOTE_PATH;"
echo "    try_files \$uri \$uri/ =404;"
echo "}"
echo "---"
