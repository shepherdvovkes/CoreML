# План исправления ошибок 400 и проблем с Docker

## Проблемы обнаружены:

1. **Сервер использует старую модель gpt-3.5-turbo** вместо gpt-4o-mini
   - В логах: `Request model: gpt-3.5-turbo`
   - Решение: Перезапустить сервер

2. **Ошибка 400 - превышен лимит контекста**
   - Ошибка: `This model's maximum context length is 16385 tokens. However, your messages resulted in 23518 tokens`
   - User message length: 48068 символов
   - Решение: Убедиться что используется gpt-4o-mini с новыми лимитами

3. **Celery worker не может подключиться к Redis**
   - Ошибка: `Cannot connect to redis://localhost:6379/0: Error 111`
   - Причина: В docker-compose.yml нет секции celery_worker с правильными переменными
   - Решение: Добавить секцию celery_worker в docker-compose.yml

4. **HTML Screenshot сервис не запущен**
   - Ошибка: `RuntimeError: Form data requires "python-multipart" to be installed`
   - Причина: python-multipart есть в requirements, но образ не пересобран
   - Решение: Пересобрать Docker образ

5. **Qdrant помечен как unhealthy**
   - Логи показывают успешные запросы, но healthcheck может быть слишком строгим
   - Решение: Проверить healthcheck

## Шаги исправления:

### Шаг 1: Перезапустить сервер
```bash
# Найти процесс
ps aux | grep uvicorn

# Перезапустить (если запущен через systemd/supervisor)
# или просто запустить заново
cd /Users/vovkes/CoreML
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Шаг 2: Обновить docker-compose.yml
- Добавлена секция celery_worker с правильными переменными окружения
- Обновлена секция html_screenshot

### Шаг 3: Пересобрать и перезапустить Docker контейнеры
```bash
cd /Users/vovkes/CoreML

# Остановить старые контейнеры
docker-compose down

# Пересобрать образы
docker-compose build --no-cache html_screenshot celery_worker

# Запустить контейнеры
docker-compose up -d

# Проверить статус
docker-compose ps

# Проверить логи
docker-compose logs -f celery_worker
docker-compose logs -f html_screenshot
```

### Шаг 4: Проверить что сервер использует gpt-4o-mini
```bash
# Проверить логи после перезапуска
tail -f logs/app.log | grep -i "model\|gpt"
```

### Шаг 5: Проверить Qdrant healthcheck
```bash
# Проверить статус
docker inspect coreml_qdrant | grep -A 10 Health

# Проверить вручную
curl http://localhost:6333/health
```
