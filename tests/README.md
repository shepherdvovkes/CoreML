# Интеграционные тесты CoreML RAG MCP Prompt Service

Этот каталог содержит интеграционные тесты для проверки взаимодействия между различными компонентами системы.

## Структура тестов

- `conftest.py` - Конфигурация pytest и общие фикстуры
- `test_api_integration.py` - Тесты API endpoints
- `test_rag_integration.py` - Тесты RAG сервиса
- `test_query_router_integration.py` - Тесты маршрутизатора запросов
- `test_celery_integration.py` - Тесты Celery задач
- `test_cache_integration.py` - Тесты сервиса кэширования
- `test_mcp_integration.py` - Тесты MCP клиента (с моками)
- `test_ollama_integration.py` - Реальные тесты с Ollama сервером
- `test_external_services_integration.py` - **Реальные тесты для внешних сервисов** (MCP Law, Redis, Qdrant)
- `test_database_initialization.py` - Тесты инициализации баз данных и таблиц

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Запуск тестов

### Запуск всех тестов
```bash
pytest tests/
```

### Запуск конкретного файла тестов
```bash
pytest tests/test_api_integration.py
```

### Запуск конкретного теста
```bash
pytest tests/test_api_integration.py::TestHealthEndpoints::test_root_endpoint
```

### Запуск с подробным выводом
```bash
pytest tests/ -v
```

### Запуск с покрытием кода
```bash
pytest tests/ --cov=core --cov=main --cov-report=html
```

## Маркеры тестов

Тесты могут быть помечены специальными маркерами:

- `@pytest.mark.integration` - интеграционные тесты
- `@pytest.mark.unit` - юнит тесты
- `@pytest.mark.slow` - медленные тесты
- `@pytest.mark.requires_redis` - требует Redis
- `@pytest.mark.requires_qdrant` - требует Qdrant
- `@pytest.mark.requires_celery` - требует Celery
- `@pytest.mark.requires_ollama` - требует запущенный Ollama сервер на localhost:11434
- `@pytest.mark.requires_external_services` - требует доступности внешних сервисов (MCP, Redis, Qdrant)

Запуск тестов с определенным маркером:
```bash
pytest -m integration
pytest -m "not slow"
pytest -m requires_ollama  # Только тесты с Ollama
pytest -m "not requires_ollama"  # Все тесты кроме Ollama
```

## Тесты инициализации баз данных

Файл `test_database_initialization.py` содержит тесты для проверки корректной инициализации всех баз данных:

- **Qdrant**: проверка существования коллекции, конфигурации (размерность векторов, расстояние COSINE)
- **ChromaDB**: проверка существования коллекции и пути хранения
- **Redis**: проверка подключения, записи/чтения данных, health check

Запуск тестов инициализации БД:
```bash
# Все тесты инициализации
pytest tests/test_database_initialization.py -v

# Только тесты Qdrant (требует запущенный Qdrant)
pytest tests/test_database_initialization.py::TestQdrantInitialization -v -m requires_qdrant

# Только тесты Redis (требует запущенный Redis)
pytest tests/test_database_initialization.py::TestRedisInitialization -v -m requires_redis

# Интеграционный тест всех БД
pytest tests/test_database_initialization.py::TestDatabaseInitializationIntegration -v
```

## Реальные интеграционные тесты с Ollama

Файл `test_ollama_integration.py` содержит реальные интеграционные тесты с Ollama API.
Эти тесты требуют запущенный Ollama сервер:

```bash
# Установите Ollama: https://ollama.ai
# Запустите сервер:
ollama serve

# Или просто:
ollama  # запускает сервер автоматически
```

Убедитесь, что модель `gpt-oss:120b-cloud` установлена:
```bash
ollama pull gpt-oss:120b-cloud
```

Запуск реальных тестов Ollama:
```bash
pytest tests/test_ollama_integration.py -v -m requires_ollama
```

## Реальные тесты внешних сервисов

Файл `test_external_services_integration.py` содержит **реальные интеграционные тесты** для внешних сервисов.
Эти тесты выполняют реальные запросы к сервисам и требуют их доступности:

### Требования

1. **MCP Law Server** - должен быть доступен по адресу из `config.py` (по умолчанию: `https://mcp.lexapp.co.ua/mcp`)
2. **Redis** - должен быть запущен и доступен (по умолчанию: `localhost:6379`)
3. **Qdrant** - должен быть запущен и доступен (по умолчанию: `localhost:6333`)

### Запуск тестов

```bash
# Все тесты внешних сервисов
pytest tests/test_external_services_integration.py -v -m requires_external_services

# Только тесты MCP Law Server
pytest tests/test_external_services_integration.py::TestMCPLawServerIntegration -v

# Только тесты Redis
pytest tests/test_external_services_integration.py::TestRedisIntegration -v

# Только тесты Qdrant
pytest tests/test_external_services_integration.py::TestQdrantIntegration -v

# Проверка здоровья всех сервисов
pytest tests/test_external_services_integration.py::TestExternalServicesHealth -v
```

### Что тестируется

#### MCP Law Server
- Подключение к серверу
- Поиск судебных дел с разными параметрами
- Получение деталей дела
- Извлечение аргументов из дел
- Обработка ошибок

#### Redis
- Подключение и health check
- Запись и чтение данных (разные типы)
- Get-or-set операции
- TTL (время жизни ключей)
- Удаление по паттерну

#### Qdrant
- Подключение к серверу
- Проверка существования коллекций
- Работа с QdrantVectorStore

### Примечания

- Тесты автоматически пропускаются (skip), если сервис недоступен
- Тесты выполняют реальные запросы и могут занимать время
- Некоторые тесты могут создавать временные данные (автоматически очищаются)
- Для тестов MCP Law требуется доступ к реальному API сервера

## Фикстуры

Основные фикстуры, доступные в тестах:

- `test_client` - FastAPI TestClient для синхронных запросов
- `async_client` - AsyncClient для асинхронных запросов
- `cache_service` - Сервис кэширования с моком Redis
- `rag_service_without_cache` - RAG сервис без кэша
- `rag_service_with_cache` - RAG сервис с кэшем
- `mock_law_client` - Мок MCP Law клиента
- `mock_llm_provider` - Мок LLM провайдера
- `query_router` - QueryRouter с моками
- `sample_query` - Пример запроса для тестов
- `sample_document_content` - Пример содержимого документа

## Моки и заглушки

Тесты используют моки для внешних зависимостей:
- Redis (кэширование)
- Векторное хранилище (Qdrant/ChromaDB)
- LLM провайдеры
- MCP серверы
- Celery брокер

Это позволяет запускать тесты без необходимости настройки всех внешних сервисов.

## Примечания

- Большинство тестов используют моки для изоляции компонентов
- Для полных интеграционных тестов с реальными сервисами требуется настройка окружения
- Тесты автоматически очищают состояние между запусками
- Event loop создается один раз на сессию для оптимизации

## Примеры использования

### Тест API endpoint
```python
def test_query_endpoint(test_client, sample_query):
    response = test_client.post("/query", json={"query": sample_query})
    assert response.status_code == 200
```

### Тест RAG сервиса
```python
@pytest.mark.asyncio
async def test_rag_search(rag_service_without_cache, sample_query):
    results = await rag_service_without_cache.search(sample_query)
    assert len(results) > 0
```

### Тест с кэшированием
```python
@pytest.mark.asyncio
async def test_cache(cache_service, mock_redis):
    await cache_service.set("key", "value", ttl=60)
    value = await cache_service.get("key")
    assert value == "value"
```

