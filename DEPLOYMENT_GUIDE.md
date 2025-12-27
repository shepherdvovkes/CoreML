# Руководство по развертыванию CoreML на production сервере

## Требования

- Docker и Docker Compose установлены на сервере
- Минимум 4GB RAM
- Минимум 20GB свободного места на диске
- Порты: 8000 (API), 6333-6334 (Qdrant), 6379 (Redis), 5555 (Flower)

## Инициализация баз данных

При развертывании автоматически создаются все необходимые коллекции/таблицы:

- **Qdrant**: Коллекция `legal_documents` создается автоматически
- **Redis**: Не требует инициализации (готов к использованию)
- **ChromaDB**: Коллекция создается автоматически (если используется)

Скрипт `init_db.py` проверяет:
- ✅ Создание коллекций
- ✅ Доступ пользователя из конфигурации
- ✅ Права на запись данных

Подробнее: см. `DB_INITIALIZATION.md`

## Быстрый старт

### 1. Подготовка сервера

```bash
# Подключение к серверу
ssh vovkes@mail.s0me.uk

# Создание директории для проекта
mkdir -p ~/coreml
cd ~/coreml
```

### 2. Клонирование/копирование проекта

```bash
# Если проект в git
git clone <repository_url> .

# Или скопируйте файлы проекта на сервер
```

### 3. Настройка конфигурации

```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование конфигурации
nano .env
```

**Важные настройки для production:**

```env
# Используйте внутренние имена контейнеров
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# API настройки
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# LLM API ключи
OPENAI_API_KEY=your_actual_key_here
```

### 3. Развертывание

```bash
# Сделать скрипты исполняемыми
chmod +x scripts/*.sh

# Запуск развертывания
./scripts/deploy.sh prod
```

## Структура сервисов

После развертывания будут запущены следующие контейнеры:

1. **coreml_redis** - Redis для кэша и Celery
2. **coreml_qdrant** - Векторная БД Qdrant
3. **coreml_api** - FastAPI сервер (4 workers)
4. **coreml_celery_worker** - Celery worker для фоновых задач
5. **coreml_flower** - Мониторинг Celery (опционально)

## Управление сервисами

### Просмотр статуса

```bash
docker-compose -f docker-compose.prod.yml ps
```

### Просмотр логов

```bash
# Все логи
docker-compose -f docker-compose.prod.yml logs -f

# Логи конкретного сервиса
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f celery_worker
docker-compose -f docker-compose.prod.yml logs -f qdrant
```

### Перезапуск сервисов

```bash
# Перезапуск всех
docker-compose -f docker-compose.prod.yml restart

# Перезапуск конкретного сервиса
docker-compose -f docker-compose.prod.yml restart api
```

### Остановка

```bash
docker-compose -f docker-compose.prod.yml down
```

### Остановка с удалением данных (осторожно!)

```bash
docker-compose -f docker-compose.prod.yml down -v
```

## Обновление

```bash
# Автоматическое обновление
./scripts/update.sh prod
```

Или вручную:

```bash
# Получение обновлений
git pull

# Пересборка и перезапуск
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## Резервное копирование

```bash
# Создание резервной копии
./scripts/backup.sh

# Восстановление из резервной копии
tar xzf backups/coreml_backup_YYYYMMDD_HHMMSS.tar.gz
# Затем восстановите данные в соответствующие контейнеры
```

## Мониторинг

### Health Checks

```bash
# Проверка API
curl http://localhost:8000/health

# Проверка Qdrant
curl http://localhost:6333/health

# Проверка Redis
docker exec coreml_redis redis-cli ping
```

### Flower (Celery мониторинг)

Откройте в браузере: `http://mail.s0me.uk:5555`

### Метрики

- API доступен на: `http://mail.s0me.uk:8000`
- API документация: `http://mail.s0me.uk:8000/docs`
- Qdrant dashboard: `http://mail.s0me.uk:6333/dashboard`

## Настройка Nginx (опционально)

Если нужно использовать Nginx как reverse proxy:

```nginx
# /etc/nginx/sites-available/coreml
server {
    listen 80;
    server_name mail.s0me.uk;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /flower {
        proxy_pass http://localhost:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Масштабирование

### Горизонтальное масштабирование API

```bash
# Запуск нескольких инстансов API
docker-compose -f docker-compose.prod.yml up -d --scale api=3
```

### Масштабирование Celery workers

```bash
# Запуск нескольких workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=3
```

## Устранение неполадок

### Проблема: Контейнеры не запускаются

```bash
# Проверка логов
docker-compose -f docker-compose.prod.yml logs

# Проверка использования ресурсов
docker stats

# Проверка портов
netstat -tulpn | grep -E '8000|6333|6379'
```

### Проблема: API не отвечает

```bash
# Проверка логов API
docker-compose -f docker-compose.prod.yml logs api

# Проверка здоровья зависимостей
docker exec coreml_redis redis-cli ping
curl http://localhost:6333/health
```

### Проблема: Недостаточно памяти

```bash
# Очистка неиспользуемых образов
docker system prune -a

# Ограничение памяти для контейнеров (в docker-compose.prod.yml)
# Добавьте в каждый сервис:
# deploy:
#   resources:
#     limits:
#       memory: 1G
```

## Безопасность

### Рекомендации для production:

1. **Используйте HTTPS** (настройте SSL сертификаты)
2. **Ограничьте доступ к портам** (используйте firewall)
3. **Используйте секреты** для API ключей (Docker secrets или внешний vault)
4. **Регулярно обновляйте** образы Docker
5. **Мониторьте логи** на предмет подозрительной активности

### Firewall настройки

```bash
# Разрешить только необходимые порты
ufw allow 22/tcp    # SSH
ufw allow 80/tcp     # HTTP (если используется Nginx)
ufw allow 443/tcp   # HTTPS
# Не открывайте 8000, 6333, 6379, 5555 публично!
```

## Производительность

### Оптимизация для production:

1. **Увеличьте количество workers** в Dockerfile (сейчас 4)
2. **Настройте Redis persistence** (уже настроено)
3. **Используйте SSD** для volumes Qdrant
4. **Мониторьте использование ресурсов** через `docker stats`

## Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose -f docker-compose.prod.yml logs`
2. Проверьте статус: `docker-compose -f docker-compose.prod.yml ps`
3. Проверьте health checks: `curl http://localhost:8000/health`

