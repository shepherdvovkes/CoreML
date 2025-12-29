# Инструкция по развертыванию

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env файл с вашими настройками
```

### 3. Запуск Redis

#### Вариант A: Docker Compose (рекомендуется)
```bash
docker-compose up -d redis
```

#### Вариант B: Локальная установка
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Или запуск напрямую
redis-server
```

### 4. Запуск сервисов

#### Терминал 1: API Server
```bash
python main.py
```

#### Терминал 2: Celery Worker
```bash
celery -A core.celery_app worker --loglevel=info --concurrency=4
```

#### Терминал 3: Flower (опционально, для мониторинга)
```bash
celery -A core.celery_app flower --port=5555
```

### 5. Проверка работы

```bash
# Проверка API
curl http://localhost:8000/health

# Проверка Redis
redis-cli ping

# Проверка Celery (через Flower)
open http://localhost:5555
```

## Production развертывание

### Использование systemd (Linux)

#### 1. Создайте файл `/etc/systemd/system/coreml-api.service`:
```ini
[Unit]
Description=CoreML API Server
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/coreml
Environment="PATH=/opt/coreml/venv/bin"
ExecStart=/opt/coreml/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. Создайте файл `/etc/systemd/system/coreml-celery.service`:
```ini
[Unit]
Description=CoreML Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/coreml
Environment="PATH=/opt/coreml/venv/bin"
ExecStart=/opt/coreml/venv/bin/celery -A core.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. Запуск сервисов:
```bash
sudo systemctl daemon-reload
sudo systemctl enable coreml-api coreml-celery
sudo systemctl start coreml-api coreml-celery
```

### Использование Docker Compose (полное развертывание)

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

### Использование Supervisor

#### Создайте `/etc/supervisor/conf.d/coreml.conf`:
```ini
[program:coreml-api]
command=/opt/coreml/venv/bin/python main.py
directory=/opt/coreml
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/coreml/api.err.log
stdout_logfile=/var/log/coreml/api.out.log

[program:coreml-celery]
command=/opt/coreml/venv/bin/celery -A core.celery_app worker --loglevel=info
directory=/opt/coreml
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/coreml/celery.err.log
stdout_logfile=/var/log/coreml/celery.out.log
```

#### Запуск:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start coreml-api
sudo supervisorctl start coreml-celery
```

## Мониторинг

### Flower Dashboard
- URL: http://localhost:5555
- Показывает активные задачи, воркеры, статистику

### Redis CLI
```bash
# Подключение
redis-cli

# Просмотр очередей
KEYS celery*

# Информация о Redis
INFO
```

### Логи
```bash
# API Server логи
tail -f logs/app.log

# Celery логи (если настроены)
tail -f /var/log/coreml/celery.out.log
```

## Масштабирование

### Горизонтальное масштабирование Celery Workers

```bash
# Запуск нескольких воркеров на разных машинах
# Worker 1
celery -A core.celery_app worker --loglevel=info --hostname=worker1@%h

# Worker 2
celery -A core.celery_app worker --loglevel=info --hostname=worker2@%h

# Worker 3
celery -A core.celery_app worker --loglevel=info --hostname=worker3@%h
```

### Настройка concurrency

```bash
# Больше воркеров на одной машине
celery -A core.celery_app worker --loglevel=info --concurrency=8
```

### Использование разных очередей

```python
# В tasks.py
@celery_app.task(queue='high_priority')
def process_important_document(...):
    ...

@celery_app.task(queue='low_priority')
def process_document(...):
    ...
```

```bash
# Запуск воркеров для разных очередей
celery -A core.celery_app worker -Q high_priority --concurrency=2
celery -A core.celery_app worker -Q low_priority --concurrency=4
```

## Troubleshooting

### Проблема: Celery worker не видит задачи

**Решение:**
1. Проверьте подключение к Redis: `redis-cli ping`
2. Проверьте URL брокера в `.env`: `CELERY_BROKER_URL`
3. Убедитесь, что worker запущен: `celery -A core.celery_app inspect active`

### Проблема: Задачи падают с timeout

**Решение:**
1. Увеличьте `CELERY_TASK_TIME_LIMIT` в `.env`
2. Оптимизируйте обработку документов
3. Используйте более мощные машины для workers

### Проблема: Redis connection refused

**Решение:**
1. Проверьте, что Redis запущен: `redis-cli ping`
2. Проверьте URL в `.env`: `CELERY_BROKER_URL=redis://localhost:6379/0`
3. Проверьте firewall настройки

### Проблема: Медленная обработка документов

**Решение:**
1. Увеличьте количество workers: `--concurrency=8`
2. Используйте более мощные машины
3. Оптимизируйте код обработки документов
4. Используйте батчинг для множественных документов

## Безопасность

### Production настройки

1. **Используйте secrets management** для API ключей
2. **Настройте firewall** для Redis (только локальный доступ)
3. **Используйте SSL/TLS** для внешних API
4. **Ограничьте доступ** к Flower dashboard
5. **Настройте rate limiting** на API Gateway

### Redis безопасность

```bash
# В redis.conf
requirepass your_strong_password
bind 127.0.0.1  # Только локальный доступ
```

```python
# В .env
CELERY_BROKER_URL=redis://:password@localhost:6379/0
```

## Производительность

### Оптимальные настройки для production

```python
# config.py
celery_worker_prefetch_multiplier = 4
celery_worker_max_tasks_per_child = 1000
celery_task_time_limit = 300
celery_task_soft_time_limit = 240
```

### Мониторинг производительности

1. **Flower**: Активные задачи, throughput
2. **Redis**: Использование памяти, количество ключей
3. **System**: CPU, память, I/O

## Backup и восстановление

### Backup Redis

```bash
# Создание backup
redis-cli --rdb /backup/redis-$(date +%Y%m%d).rdb

# Восстановление
redis-cli --rdb /backup/redis-20240101.rdb
```

### Backup векторной БД

```bash
# ChromaDB данные
tar -czf backup-vector-db.tar.gz data/vector_db/
```



