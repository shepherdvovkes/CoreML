#!/bin/bash

# Скрипт для развертывания CoreML на production сервере
# Использование: ./scripts/deploy.sh [environment]
# environment: prod (по умолчанию) или dev

set -e

ENVIRONMENT=${1:-prod}
COMPOSE_FILE="docker-compose.yml"

if [ "$ENVIRONMENT" = "prod" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
fi

echo "🚀 Развертывание CoreML в режиме: $ENVIRONMENT"
echo "📄 Используется файл: $COMPOSE_FILE"

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден!"
    if [ -f .env.example ]; then
        echo "📋 Создание .env из .env.example..."
        cp .env.example .env
    else
        echo "❌ Файл .env.example не найден!"
        exit 1
    fi
else
    # Сохраняем существующие важные ключи перед генерацией паролей
    echo "💾 Сохранение существующих API ключей..."
    if grep -q "^OPENAI_API_KEY=" .env 2>/dev/null; then
        SAVED_OPENAI_KEY=$(grep "^OPENAI_API_KEY=" .env | cut -d'=' -f2-)
        echo "   ✅ OPENAI_API_KEY сохранен"
    fi
    if grep -q "^MCP_LAW_API_KEY=" .env 2>/dev/null; then
        SAVED_MCP_KEY=$(grep "^MCP_LAW_API_KEY=" .env | cut -d'=' -f2-)
        echo "   ✅ MCP_LAW_API_KEY сохранен"
    fi
fi

# Генерация безопасных паролей
echo "🔐 Генерация безопасных паролей и ключей..."
if [ -f scripts/generate_secrets.sh ]; then
    chmod +x scripts/generate_secrets.sh
    ./scripts/generate_secrets.sh .env
    
    # Проверка безопасности секретов
    if [ -f scripts/check_secrets.sh ]; then
        chmod +x scripts/check_secrets.sh
        echo "🔍 Проверка безопасности секретов..."
        ./scripts/check_secrets.sh .env || echo "⚠️  Некоторые проверки безопасности не пройдены"
    fi
    
    # Восстановление сохраненных API ключей
    if [ -n "$SAVED_OPENAI_KEY" ]; then
        echo "💾 Восстановление OPENAI_API_KEY..."
        sed -i.bak "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$SAVED_OPENAI_KEY|" .env || \
        echo "OPENAI_API_KEY=$SAVED_OPENAI_KEY" >> .env
        rm -f .env.bak
    fi
    if [ -n "$SAVED_MCP_KEY" ]; then
        echo "💾 Восстановление MCP_LAW_API_KEY..."
        sed -i.bak "s|^MCP_LAW_API_KEY=.*|MCP_LAW_API_KEY=$SAVED_MCP_KEY|" .env || \
        echo "MCP_LAW_API_KEY=$SAVED_MCP_KEY" >> .env
        rm -f .env.bak
    fi
    
    # Установка безопасных прав доступа к .env
    chmod 600 .env
    echo "✅ Установлены безопасные права доступа на .env (600)"
    
    # Проверка важных ключей
    if [ -f scripts/verify_env.sh ]; then
        chmod +x scripts/verify_env.sh
        echo "🔍 Проверка важных ключей..."
        ./scripts/verify_env.sh .env || {
            echo "⚠️  Некоторые важные ключи отсутствуют или пусты"
            echo "   Убедитесь, что OPENAI_API_KEY установлен перед развертыванием"
        }
    fi
else
    echo "⚠️  Скрипт generate_secrets.sh не найден, пропуск генерации паролей"
fi

# Остановка существующих контейнеров
echo "🛑 Остановка существующих контейнеров..."
docker-compose -f $COMPOSE_FILE down || true

# Сборка образов
echo "🔨 Сборка Docker образов..."
docker-compose -f $COMPOSE_FILE build --no-cache

# Запуск сервисов
echo "▶️  Запуск сервисов..."
docker-compose -f $COMPOSE_FILE up -d

# Ожидание готовности сервисов
echo "⏳ Ожидание готовности сервисов..."
echo "   Ожидание Redis..."
for i in {1..30}; do
    if docker exec coreml_redis redis-cli ping > /dev/null 2>&1 || \
       (docker exec coreml_redis redis-cli -a "${REDIS_PASSWORD:-}" ping > /dev/null 2>&1 2>/dev/null); then
        echo "   ✅ Redis готов"
        break
    fi
    sleep 1
done

echo "   Ожидание Qdrant..."
for i in {1..30}; do
    if curl -f http://localhost:6333/health > /dev/null 2>&1; then
        echo "   ✅ Qdrant готов"
        break
    fi
    sleep 1
done

sleep 5

# Проверка здоровья сервисов
echo "🏥 Проверка здоровья сервисов..."
docker-compose -f $COMPOSE_FILE ps

# Инициализация баз данных
echo "🔧 Инициализация баз данных..."
if [ -f scripts/init_db.py ]; then
    # Запуск инициализации в контейнере API (если он уже запущен)
    if docker ps | grep -q coreml_api; then
        echo "   Запуск инициализации БД в контейнере..."
        docker exec coreml_api python scripts/init_db.py || {
            echo "   ⚠️  Инициализация через контейнер не удалась, попробуем локально..."
            python3 scripts/init_db.py || echo "   ⚠️  Локальная инициализация не удалась"
        }
    else
        echo "   Запуск инициализации БД локально..."
        python3 scripts/init_db.py || echo "   ⚠️  Инициализация не удалась (продолжаем...)"
    fi
else
    echo "   ⚠️  Скрипт init_db.py не найден, пропуск инициализации"
fi

# Проверка API
echo "🔍 Проверка API..."
sleep 5
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API сервер работает!"
else
    echo "❌ API сервер не отвечает. Проверьте логи:"
    echo "   docker-compose -f $COMPOSE_FILE logs api"
fi

# Показать статус
echo ""
echo "📊 Статус контейнеров:"
docker-compose -f $COMPOSE_FILE ps

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "📝 Полезные команды:"
echo "   Логи API:           docker-compose -f $COMPOSE_FILE logs -f api"
echo "   Логи Celery:        docker-compose -f $COMPOSE_FILE logs -f celery_worker"
echo "   Логи Redis:         docker-compose -f $COMPOSE_FILE logs -f redis"
echo "   Логи Qdrant:        docker-compose -f $COMPOSE_FILE logs -f qdrant"
echo "   Остановка:          docker-compose -f $COMPOSE_FILE down"
echo "   Перезапуск:         docker-compose -f $COMPOSE_FILE restart"
echo ""
echo "🌐 Доступные сервисы:"
echo "   API:                http://localhost:8000"
echo "   API Docs:           http://localhost:8000/docs"
echo "   Flower (Celery):    http://localhost:5555"
echo "   Qdrant:             http://localhost:6333"

