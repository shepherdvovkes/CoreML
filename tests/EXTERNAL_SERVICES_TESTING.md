# Тестирование внешних сервисов

Этот документ описывает как запускать реальные интеграционные тесты для внешних сервисов.

## Быстрый старт

```bash
# Запустить все тесты внешних сервисов
pytest tests/test_external_services_integration.py -v -m requires_external_services

# Проверить здоровье всех сервисов
pytest tests/test_external_services_integration.py::TestExternalServicesHealth -v
```

## Требования

### 1. MCP Law Server

Сервер должен быть доступен по адресу из `config.py`:
- По умолчанию: `https://mcp.lexapp.co.ua/mcp`
- Настраивается через `MCP_LAW_SERVER_URL` в `.env`

**Проверка доступности:**
```bash
curl https://mcp.lexapp.co.ua/mcp
```

### 2. Redis

Redis должен быть запущен и доступен:
- По умолчанию: `localhost:6379`
- Настраивается через `REDIS_URL` в `.env`

**Запуск Redis:**
```bash
# Docker
docker run -d -p 6379:6379 redis:latest

# Или локально (если установлен)
redis-server
```

**Проверка:**
```bash
redis-cli ping
# Должно вернуть: PONG
```

### 3. Qdrant

Qdrant должен быть запущен и доступен:
- По умолчанию: `localhost:6333`
- Настраивается через `QDRANT_URL` в `.env`

**Запуск Qdrant:**
```bash
# Docker
docker run -d -p 6333:6333 qdrant/qdrant:latest

# Или локально (если установлен)
qdrant
```

**Проверка:**
```bash
curl http://localhost:6333/collections
```

## Запуск тестов

### Все тесты

```bash
pytest tests/test_external_services_integration.py -v -m requires_external_services
```

### По категориям

**MCP Law Server:**
```bash
pytest tests/test_external_services_integration.py::TestMCPLawServerIntegration -v
```

**Redis:**
```bash
pytest tests/test_external_services_integration.py::TestRedisIntegration -v
```

**Qdrant:**
```bash
pytest tests/test_external_services_integration.py::TestQdrantIntegration -v
```

**Проверка здоровья:**
```bash
pytest tests/test_external_services_integration.py::TestExternalServicesHealth -v
```

### Конкретный тест

```bash
pytest tests/test_external_services_integration.py::TestMCPLawServerIntegration::test_search_cases_real -v
```

## Что тестируется

### MCP Law Server (`TestMCPLawServerIntegration`)

1. **test_mcp_law_server_connection** - Проверка подключения к серверу
2. **test_search_cases_real** - Реальный поиск судебных дел
3. **test_search_cases_different_instances** - Поиск с разными инстанциями (1, 2, 3, 4)
4. **test_search_cases_limit** - Проверка ограничения количества результатов
5. **test_get_case_details_real** - Получение деталей дела
6. **test_extract_case_arguments_real** - Извлечение аргументов из дел (может быть долгим)
7. **test_mcp_law_error_handling** - Обработка ошибок

### Redis (`TestRedisIntegration`)

1. **test_redis_connection_real** - Проверка подключения и health check
2. **test_redis_set_get_real** - Запись и чтение данных (разные типы)
3. **test_redis_get_or_set_real** - Get-or-set операции с вычислением
4. **test_redis_ttl_real** - Проверка TTL (время жизни ключей)
5. **test_redis_delete_pattern_real** - Удаление по паттерну

### Qdrant (`TestQdrantIntegration`)

1. **test_qdrant_connection_real** - Проверка подключения
2. **test_qdrant_collection_exists_real** - Проверка существования коллекции
3. **test_qdrant_vector_store_real** - Работа с QdrantVectorStore

### Health Check (`TestExternalServicesHealth`)

1. **test_all_services_health** - Проверка здоровья всех сервисов одновременно

## Поведение при недоступности сервисов

- Тесты **автоматически пропускаются** (skip), если сервис недоступен
- Используется `pytest.skip()` вместо падения теста
- Это позволяет запускать тесты даже если не все сервисы доступны

## Примеры вывода

### Успешный запуск

```
tests/test_external_services_integration.py::TestMCPLawServerIntegration::test_search_cases_real PASSED
tests/test_external_services_integration.py::TestRedisIntegration::test_redis_connection_real PASSED
tests/test_external_services_integration.py::TestQdrantIntegration::test_qdrant_connection_real PASSED
```

### Пропущенные тесты (сервис недоступен)

```
tests/test_external_services_integration.py::TestMCPLawServerIntegration::test_search_cases_real SKIPPED [1] MCP Law Server недоступен: Connection refused
```

### Health Check вывод

```
=== Статус внешних сервисов ===
✓ mcp_law: доступен
✓ redis: доступен
✗ qdrant: недоступен
```

## Отладка

### Включить подробный вывод

```bash
pytest tests/test_external_services_integration.py -v -s
```

### Проверить только подключение

```bash
# MCP Law
pytest tests/test_external_services_integration.py::TestMCPLawServerIntegration::test_mcp_law_server_connection -v -s

# Redis
pytest tests/test_external_services_integration.py::TestRedisIntegration::test_redis_connection_real -v -s

# Qdrant
pytest tests/test_external_services_integration.py::TestQdrantIntegration::test_qdrant_connection_real -v -s
```

## Настройка через .env

Создайте или обновите `.env` файл:

```env
# MCP Law Server
MCP_LAW_SERVER_URL=https://mcp.lexapp.co.ua/mcp

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Опционально
```

## Примечания

- Тесты выполняют **реальные запросы** к сервисам
- Некоторые тесты могут занимать время (особенно `extract_case_arguments`)
- Тесты автоматически очищают временные данные
- Для тестов Redis и Qdrant могут создаваться временные ключи/коллекции (автоматически удаляются)

## Troubleshooting

### MCP Law Server недоступен

1. Проверьте URL в `config.py` или `.env`
2. Проверьте доступность сервера: `curl https://mcp.lexapp.co.ua/mcp`
3. Проверьте сетевые настройки и firewall

### Redis недоступен

1. Проверьте что Redis запущен: `redis-cli ping`
2. Проверьте URL в настройках: `REDIS_URL=redis://localhost:6379/0`
3. Проверьте порт: по умолчанию 6379

### Qdrant недоступен

1. Проверьте что Qdrant запущен: `curl http://localhost:6333/collections`
2. Проверьте URL в настройках: `QDRANT_URL=http://localhost:6333`
3. Проверьте порт: по умолчанию 6333

