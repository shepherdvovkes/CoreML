#!/bin/bash

# Скрипт для проверки важных ключей в .env файле
# Использование: ./scripts/verify_env.sh

ENV_FILE=${1:-.env}

echo "🔍 Проверка важных ключей в $ENV_FILE..."
echo ""

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Файл $ENV_FILE не найден!"
    exit 1
fi

# Список важных ключей для проверки
IMPORTANT_KEYS=(
    "OPENAI_API_KEY"
    "REDIS_PASSWORD"
    "QDRANT_API_KEY"
    "MCP_LAW_API_KEY"
)

MISSING_KEYS=0
EMPTY_KEYS=0

for key in "${IMPORTANT_KEYS[@]}"; do
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        value=$(grep "^${key}=" "$ENV_FILE" | cut -d'=' -f2-)
        if [ -z "$value" ] || [ "$value" = "" ]; then
            echo "⚠️  $key: установлен, но пустой"
            EMPTY_KEYS=$((EMPTY_KEYS + 1))
        else
            # Показываем только первые и последние символы для безопасности
            if [ ${#value} -gt 10 ]; then
                masked="${value:0:4}...${value: -4}"
            else
                masked="****"
            fi
            echo "✅ $key: установлен ($masked)"
        fi
    else
        echo "❌ $key: не найден"
        MISSING_KEYS=$((MISSING_KEYS + 1))
    fi
done

echo ""
if [ $MISSING_KEYS -eq 0 ] && [ $EMPTY_KEYS -eq 0 ]; then
    echo "✅ Все важные ключи установлены!"
    exit 0
else
    echo "⚠️  Проблемы найдены:"
    [ $MISSING_KEYS -gt 0 ] && echo "   - Отсутствует ключей: $MISSING_KEYS"
    [ $EMPTY_KEYS -gt 0 ] && echo "   - Пустых ключей: $EMPTY_KEYS"
    exit 1
fi

