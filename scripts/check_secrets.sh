#!/bin/bash

# Скрипт для проверки наличия и безопасности секретов
# Использование: ./scripts/check_secrets.sh [.env_file]

set -e

ENV_FILE=${1:-.env}

echo "🔍 Проверка безопасности секретов в $ENV_FILE..."

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Файл $ENV_FILE не найден!"
    exit 1
fi

# Проверка наличия секретов
MISSING_SECRETS=0

# Проверка Redis пароля
if ! grep -q "^REDIS_PASSWORD=" "$ENV_FILE" 2>/dev/null || grep -q "^REDIS_PASSWORD=$" "$ENV_FILE" 2>/dev/null; then
    echo "⚠️  REDIS_PASSWORD не установлен или пустой"
    MISSING_SECRETS=$((MISSING_SECRETS + 1))
else
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2)
    if [ ${#REDIS_PASSWORD} -lt 16 ]; then
        echo "⚠️  REDIS_PASSWORD слишком короткий (минимум 16 символов)"
        MISSING_SECRETS=$((MISSING_SECRETS + 1))
    else
        echo "✅ REDIS_PASSWORD установлен и достаточно длинный"
    fi
fi

# Проверка Qdrant API ключа
if ! grep -q "^QDRANT_API_KEY=" "$ENV_FILE" 2>/dev/null || grep -q "^QDRANT_API_KEY=$" "$ENV_FILE" 2>/dev/null; then
    echo "⚠️  QDRANT_API_KEY не установлен или пустой"
    MISSING_SECRETS=$((MISSING_SECRETS + 1))
else
    QDRANT_KEY=$(grep "^QDRANT_API_KEY=" "$ENV_FILE" | cut -d'=' -f2)
    if [ ${#QDRANT_KEY} -lt 32 ]; then
        echo "⚠️  QDRANT_API_KEY слишком короткий (минимум 32 символа)"
        MISSING_SECRETS=$((MISSING_SECRETS + 1))
    else
        echo "✅ QDRANT_API_KEY установлен и достаточно длинный"
    fi
fi

# Проверка соответствия URL с паролями
if grep -q "^REDIS_PASSWORD=" "$ENV_FILE" 2>/dev/null; then
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2)
    
    # Проверка REDIS_URL
    if grep -q "^REDIS_URL=" "$ENV_FILE" 2>/dev/null; then
        REDIS_URL=$(grep "^REDIS_URL=" "$ENV_FILE" | cut -d'=' -f2)
        if [[ "$REDIS_URL" != *":$REDIS_PASSWORD@"* ]]; then
            echo "⚠️  REDIS_URL не содержит пароль или пароль не совпадает"
            MISSING_SECRETS=$((MISSING_SECRETS + 1))
        else
            echo "✅ REDIS_URL содержит правильный пароль"
        fi
    fi
    
    # Проверка CELERY_BROKER_URL
    if grep -q "^CELERY_BROKER_URL=" "$ENV_FILE" 2>/dev/null; then
        CELERY_BROKER=$(grep "^CELERY_BROKER_URL=" "$ENV_FILE" | cut -d'=' -f2)
        if [[ "$CELERY_BROKER" != *":$REDIS_PASSWORD@"* ]]; then
            echo "⚠️  CELERY_BROKER_URL не содержит пароль или пароль не совпадает"
            MISSING_SECRETS=$((MISSING_SECRETS + 1))
        else
            echo "✅ CELERY_BROKER_URL содержит правильный пароль"
        fi
    fi
    
    # Проверка CELERY_RESULT_BACKEND
    if grep -q "^CELERY_RESULT_BACKEND=" "$ENV_FILE" 2>/dev/null; then
        CELERY_BACKEND=$(grep "^CELERY_RESULT_BACKEND=" "$ENV_FILE" | cut -d'=' -f2)
        if [[ "$CELERY_BACKEND" != *":$REDIS_PASSWORD@"* ]]; then
            echo "⚠️  CELERY_RESULT_BACKEND не содержит пароль или пароль не совпадает"
            MISSING_SECRETS=$((MISSING_SECRETS + 1))
        else
            echo "✅ CELERY_RESULT_BACKEND содержит правильный пароль"
        fi
    fi
fi

# Проверка прав доступа к файлу
FILE_PERMS=$(stat -c "%a" "$ENV_FILE" 2>/dev/null || stat -f "%OLp" "$ENV_FILE" 2>/dev/null)
if [ "$FILE_PERMS" != "600" ] && [ "$FILE_PERMS" != "400" ]; then
    echo "⚠️  Файл $ENV_FILE имеет небезопасные права доступа: $FILE_PERMS"
    echo "   Рекомендуется: chmod 600 $ENV_FILE"
    MISSING_SECRETS=$((MISSING_SECRETS + 1))
else
    echo "✅ Файл $ENV_FILE имеет безопасные права доступа"
fi

# Итоговый результат
echo ""
if [ $MISSING_SECRETS -eq 0 ]; then
    echo "✅ Все проверки безопасности пройдены!"
    exit 0
else
    echo "❌ Обнаружено проблем: $MISSING_SECRETS"
    echo "   Запустите: ./scripts/generate_secrets.sh $ENV_FILE"
    exit 1
fi

