# CoreML Docker Images на DockerHub

Все Docker образы проекта CoreML доступны на DockerHub в репозитории [mcvovkes](https://hub.docker.com/u/mcvovkes).

## 📦 Доступные образы

| Образ | Описание | Размер | DockerHub |
|-------|----------|--------|-----------|
| `mcvovkes/api:latest` | API сервер (FastAPI) | ~5.45GB | [docker.io/mcvovkes/api](https://hub.docker.com/r/mcvovkes/api) |
| `mcvovkes/celery_worker:latest` | Celery Worker для фоновых задач | ~4.34GB | [docker.io/mcvovkes/celery_worker](https://hub.docker.com/r/mcvovkes/celery_worker) |
| `mcvovkes/flower:latest` | Flower - веб-интерфейс для мониторинга Celery | ~3.98GB | [docker.io/mcvovkes/flower](https://hub.docker.com/r/mcvovkes/flower) |
| `mcvovkes/html_screenshot:latest` | Сервис для создания скриншотов HTML страниц | ~3.44GB | [docker.io/mcvovkes/html_screenshot](https://hub.docker.com/r/mcvovkes/html_screenshot) |

## 🚀 Быстрый старт

### Загрузка всех образов

```bash
# Загрузить все образы CoreML
docker pull mcvovkes/api:latest
docker pull mcvovkes/celery_worker:latest
docker pull mcvovkes/flower:latest
docker pull mcvovkes/html_screenshot:latest
```

### Использование с docker-compose

Обновите `docker-compose.yml` или `docker-compose.prod.yml` для использования образов из DockerHub:

```yaml
services:
  api:
    image: mcvovkes/api:latest
    # Удалите секцию build: если она есть
    # build:
    #   context: .
    #   dockerfile: Dockerfile
    container_name: coreml_api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - QDRANT_URL=http://qdrant:6333
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
      - qdrant
    networks:
      - coreml_network
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data

  celery_worker:
    image: mcvovkes/celery_worker:latest
    # Удалите секцию build: если она есть
    container_name: coreml_celery_worker
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - QDRANT_URL=http://qdrant:6333
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
      - qdrant
    networks:
      - coreml_network
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data

  flower:
    image: mcvovkes/flower:latest
    # Удалите секцию build: если она есть
    container_name: coreml_flower
    restart: unless-stopped
    ports:
      - "5555:5555"
    env_file:
      - .env
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
    networks:
      - coreml_network

  html_screenshot:
    image: mcvovkes/html_screenshot:latest
    # Удалите секцию build: если она есть
    container_name: coreml_html_screenshot
    restart: unless-stopped
    ports:
      - "3015:3015"
    env_file:
      - .env
    environment:
      - PORT=3015
      - HOST=0.0.0.0
      - VISION_API_URL=${VISION_API_URL:-https://mail.s0me.uk/vision}
    networks:
      - coreml_network
    volumes:
      - ./services:/app/services:ro
      - ./core:/app/core:ro
      - ./config.py:/app/config.py:ro
```

### Запуск с docker-compose

```bash
# Загрузить и запустить все сервисы
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f

# Остановка
docker-compose -f docker-compose.prod.yml down
```

## 🔧 Ручной запуск контейнеров

### API сервер

```bash
docker run -d \
  --name coreml_api \
  -p 8000:8000 \
  --env-file .env \
  -e QDRANT_URL=http://qdrant:6333 \
  -e REDIS_URL=redis://redis:6379/0 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --network coreml_network \
  mcvovkes/api:latest
```

### Celery Worker

```bash
docker run -d \
  --name coreml_celery_worker \
  --env-file .env \
  -e QDRANT_URL=http://qdrant:6333 \
  -e REDIS_URL=redis://redis:6379/0 \
  -e CELERY_BROKER_URL=redis://redis:6379/0 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --network coreml_network \
  mcvovkes/celery_worker:latest
```

### Flower (мониторинг Celery)

```bash
docker run -d \
  --name coreml_flower \
  -p 5555:5555 \
  --env-file .env \
  -e CELERY_BROKER_URL=redis://redis:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://redis:6379/0 \
  --network coreml_network \
  mcvovkes/flower:latest
```

### HTML Screenshot сервис

```bash
docker run -d \
  --name coreml_html_screenshot \
  -p 3015:3015 \
  --env-file .env \
  -e PORT=3015 \
  -e HOST=0.0.0.0 \
  -v $(pwd)/services:/app/services:ro \
  -v $(pwd)/core:/app/core:ro \
  -v $(pwd)/config.py:/app/config.py:ro \
  --network coreml_network \
  mcvovkes/html_screenshot:latest
```

## 📋 Требования

Перед запуском контейнеров убедитесь, что у вас запущены:

1. **Redis** - для кэширования и Celery broker
2. **Qdrant** - векторная база данных

Эти сервисы можно запустить через docker-compose или отдельно:

```bash
# Redis
docker run -d --name coreml_redis -p 6379:6379 redis:7-alpine

# Qdrant
docker run -d --name coreml_qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```

## 🔄 Обновление образов

Для обновления до последней версии:

```bash
# Загрузить последние версии
docker pull mcvovkes/api:latest
docker pull mcvovkes/celery_worker:latest
docker pull mcvovkes/flower:latest
docker pull mcvovkes/html_screenshot:latest

# Перезапустить контейнеры
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

## 📝 Переменные окружения

Все контейнеры требуют файл `.env` с необходимыми переменными окружения. Пример:

```env
# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=your_api_key_here

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# LLM Providers
OPENAI_API_KEY=your_openai_key
CUSTOM_LLM_URL=http://localhost:8000/v1/chat/completions

# Vision API (для html_screenshot)
VISION_API_URL=https://mail.s0me.uk/vision
VISION_API_KEY=your_vision_api_key
```

## 🐛 Устранение неполадок

### Проверка статуса контейнеров

```bash
docker ps | grep coreml
```

### Просмотр логов

```bash
# API
docker logs coreml_api -f

# Celery Worker
docker logs coreml_celery_worker -f

# Flower
docker logs coreml_flower -f

# HTML Screenshot
docker logs coreml_html_screenshot -f
```

### Проверка здоровья сервисов

```bash
# API Health Check
curl http://localhost:8000/health

# Flower
curl http://localhost:5555

# HTML Screenshot Health Check
curl http://localhost:3015/health
```

## 📚 Дополнительная информация

- [Основной README](README.md)
- [Docker Compose конфигурация](docker-compose.prod.yml)
- [Dockerfile для API](Dockerfile)
- [Dockerfile для Celery](Dockerfile.celery)
- [Dockerfile для Flower](Dockerfile.flower)
- [Dockerfile для HTML Screenshot](Dockerfile.playwright)

## 🔗 Ссылки

- DockerHub репозиторий: https://hub.docker.com/u/mcvovkes
- API образ: https://hub.docker.com/r/mcvovkes/api
- Celery Worker образ: https://hub.docker.com/r/mcvovkes/celery_worker
- Flower образ: https://hub.docker.com/r/mcvovkes/flower
- HTML Screenshot образ: https://hub.docker.com/r/mcvovkes/html_screenshot

