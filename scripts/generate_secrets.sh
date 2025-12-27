#!/bin/bash

# Скрипт для генерации безопасных паролей и ключей
# Использование: ./scripts/generate_secrets.sh [.env_file]

set -e

ENV_FILE=${1:-.env}

echo "🔐 Генерация безопасных паролей и ключей..."

# Функция для генерации безопасного пароля
generate_password() {
    # Генерирует пароль длиной 32 символа из букв, цифр и спецсимволов
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Функция для генерации API ключа
generate_api_key() {
    # Генерирует API ключ длиной 64 символа
    openssl rand -hex 32
}

# Проверка наличия .env файла
if [ ! -f "$ENV_FILE" ]; then
    echo "📋 Создание нового .env файла из .env.example..."
    if [ -f .env.example ]; then
        cp .env.example "$ENV_FILE"
    else
        echo "❌ Файл .env.example не найден!"
        exit 1
    fi
else
    # Сохраняем существующие важные ключи (не генерируем их заново)
    echo "💾 Проверка существующих API ключей..."
    PRESERVE_KEYS=("OPENAI_API_KEY" "MCP_LAW_API_KEY" "LMSTUDIO_BASE_URL" "CUSTOM_LLM_BASE_URL")
    declare -A SAVED_KEYS
    
    for key in "${PRESERVE_KEYS[@]}"; do
        if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
            SAVED_VALUE=$(grep "^${key}=" "$ENV_FILE" | cut -d'=' -f2-)
            if [ -n "$SAVED_VALUE" ] && [ "$SAVED_VALUE" != "" ]; then
                SAVED_KEYS["$key"]="$SAVED_VALUE"
                echo "   ✅ $key сохранен (не будет перезаписан)"
            fi
        fi
    done
fi

# Генерация пароля для Redis
if ! grep -q "^REDIS_PASSWORD=" "$ENV_FILE" 2>/dev/null || grep -q "^REDIS_PASSWORD=$" "$ENV_FILE" 2>/dev/null; then
    REDIS_PASSWORD=$(generate_password)
    if grep -q "^REDIS_PASSWORD=" "$ENV_FILE"; then
        # Замена существующей пустой строки
        sed -i.bak "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASSWORD|" "$ENV_FILE"
    else
        # Добавление новой строки
        echo "REDIS_PASSWORD=$REDIS_PASSWORD" >> "$ENV_FILE"
    fi
    echo "✅ Сгенерирован пароль для Redis"
else
    echo "ℹ️  Пароль Redis уже установлен (пропуск)"
fi

# Генерация API ключа для Qdrant
if ! grep -q "^QDRANT_API_KEY=" "$ENV_FILE" 2>/dev/null || grep -q "^QDRANT_API_KEY=$" "$ENV_FILE" 2>/dev/null; then
    QDRANT_API_KEY=$(generate_api_key)
    if grep -q "^QDRANT_API_KEY=" "$ENV_FILE"; then
        sed -i.bak "s|^QDRANT_API_KEY=.*|QDRANT_API_KEY=$QDRANT_API_KEY|" "$ENV_FILE"
    else
        echo "QDRANT_API_KEY=$QDRANT_API_KEY" >> "$ENV_FILE"
    fi
    echo "✅ Сгенерирован API ключ для Qdrant"
else
    echo "ℹ️  API ключ Qdrant уже установлен (пропуск)"
fi

# Обновление URL с паролями
if grep -q "^REDIS_PASSWORD=" "$ENV_FILE"; then
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2)
    
    # Функция для обновления Redis URL
    update_redis_url() {
        local KEY=$1
        local DEFAULT_HOST=${2:-redis:6379}
        
        if grep -q "^${KEY}=" "$ENV_FILE"; then
            # Извлекаем хост, порт и БД из текущего URL
            CURRENT_URL=$(grep "^${KEY}=" "$ENV_FILE" | cut -d'=' -f2- | sed 's/^[[:space:]]*//')
            
            # Удаляем старый пароль если есть
            CURRENT_URL=$(echo "$CURRENT_URL" | sed 's|redis://:[^@]*@|redis://|' | sed 's|redis://||')
            
            # Извлекаем хост:порт и БД
            if [[ "$CURRENT_URL" == *"/"* ]]; then
                HOST_PORT=$(echo "$CURRENT_URL" | cut -d'/' -f1)
                DB=$(echo "$CURRENT_URL" | cut -d'/' -f2)
            else
                HOST_PORT="$CURRENT_URL"
                DB="0"
            fi
            
            # Используем значение по умолчанию если пусто
            if [ -z "$HOST_PORT" ]; then
                HOST_PORT="$DEFAULT_HOST"
            fi
            
            # Обновляем URL с новым паролем
            NEW_URL="redis://:${REDIS_PASSWORD}@${HOST_PORT}/${DB}"
            sed -i.bak "s|^${KEY}=.*|${KEY}=${NEW_URL}|" "$ENV_FILE"
        fi
    }
    
    # Обновление всех Redis URL
    update_redis_url "REDIS_URL" "redis:6379"
    update_redis_url "CELERY_BROKER_URL" "redis:6379"
    update_redis_url "CELERY_RESULT_BACKEND" "redis:6379"
    
    echo "✅ Обновлены URL с паролем Redis"
fi

# Восстановление сохраненных ключей (если они были)
if [ ${#SAVED_KEYS[@]} -gt 0 ]; then
    echo "💾 Восстановление сохраненных API ключей..."
    for key in "${!SAVED_KEYS[@]}"; do
        value="${SAVED_KEYS[$key]}"
        if grep -q "^${key}=" "$ENV_FILE"; then
            # Проверяем, не был ли ключ перезаписан пустым значением
            current_value=$(grep "^${key}=" "$ENV_FILE" | cut -d'=' -f2-)
            if [ -z "$current_value" ] || [ "$current_value" = "" ]; then
                sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
                echo "   ✅ $key восстановлен"
            fi
        else
            echo "${key}=${value}" >> "$ENV_FILE"
            echo "   ✅ $key добавлен"
        fi
    done
fi

# Удаление backup файлов
rm -f "$ENV_FILE.bak"

echo ""
echo "✅ Генерация секретов завершена!"
echo "📝 Файл: $ENV_FILE"
echo ""
echo "⚠️  ВАЖНО: Сохраните этот файл в безопасном месте!"
echo "   Файл .env содержит секретные ключи и не должен попадать в git!"

