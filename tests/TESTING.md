# Руководство по интеграционным тестам

## Обзор

Интеграционные тесты проверяют взаимодействие между различными компонентами системы CoreML RAG MCP Prompt Service. Тесты используют моки для изоляции компонентов и обеспечения быстрого выполнения.

## Структура тестов

### 1. test_api_integration.py
Тесты для API endpoints:
- Health check endpoints (`/`, `/health`)
- Query endpoints (`/query`, `/query/stream`)
- RAG endpoints (`/rag/add-document`, `/rag/search`, `/rag/task/{task_id}`)
- MCP endpoints (`/mcp/law/search-cases`, `/mcp/law/case/{case_number}`)

### 2. test_rag_integration.py
Тесты для RAG сервиса:
- Поиск документов с кэшированием и без
- Получение контекста
- Добавление документов
- Инвалидация кэша
- Обработка ошибок

### 3. test_query_router_integration.py
Тесты для QueryRouter:
- Обработка запросов с RAG и Law MCP
- Автоматическая классификация запросов
- Кэширование ответов
- Потоковая обработка
- Обработка ошибок в различных компонентах

### 4. test_celery_integration.py
Тесты для Celery задач:
- Обработка одного документа
- Пакетная обработка документов
- Обработка ошибок и retry
- Health check задачи

### 5. test_cache_integration.py
Тесты для сервиса кэширования:
- Сохранение и получение значений
- Удаление ключей и паттернов
- Get-or-set операции
- Проверка существования ключей
- Health check
- Обработка ошибок

### 6. test_mcp_integration.py
Тесты для MCP клиента:
- Поиск судебных дел
- Получение деталей дела
- Извлечение аргументов
- Обработка ошибок

## Запуск тестов

### Все тесты
```bash
pytest tests/
```

### Конкретный файл
```bash
pytest tests/test_api_integration.py
```

### Конкретный тест
```bash
pytest tests/test_api_integration.py::TestHealthEndpoints::test_root_endpoint
```

### С покрытием
```bash
pytest tests/ --cov=core --cov=main --cov-report=html
```

## Фикстуры

Основные фикстуры определены в `conftest.py`:

- **test_client** - FastAPI TestClient для синхронных HTTP запросов
- **async_client** - AsyncClient для асинхронных запросов
- **cache_service** - Сервис кэширования с моком Redis
- **rag_service_without_cache** - RAG сервис без кэша
- **rag_service_with_cache** - RAG сервис с кэшем
- **mock_law_client** - Мок MCP Law клиента
- **mock_llm_provider** - Мок LLM провайдера
- **query_router** - QueryRouter с настроенными моками
- **sample_query** - Пример запроса
- **sample_document_content** - Пример содержимого документа

## Моки

Тесты используют моки для следующих компонентов:

1. **Redis** - для тестирования кэширования без реального Redis
2. **Векторное хранилище** - для тестирования RAG без Qdrant/ChromaDB
3. **LLM провайдеры** - для тестирования без реальных API вызовов
4. **MCP серверы** - для тестирования без реальных MCP серверов
5. **Celery брокер** - для тестирования задач без реального брокера

## Примеры использования

### Тест API endpoint
```python
def test_query_endpoint(test_client, sample_query):
    response = test_client.post("/query", json={"query": sample_query})
    assert response.status_code == 200
```

### Тест асинхронного сервиса
```python
@pytest.mark.asyncio
async def test_rag_search(rag_service_without_cache, sample_query):
    results = await rag_service_without_cache.search(sample_query)
    assert len(results) > 0
```

### Тест с моками
```python
def test_with_mock(mock_llm_provider):
    with patch('module.function', return_value=mock_llm_provider):
        result = function_under_test()
        assert result is not None
```

## Примечания

- Все тесты изолированы и не зависят друг от друга
- Моки автоматически очищаются между тестами
- Event loop создается один раз на сессию для оптимизации
- Для полных интеграционных тестов с реальными сервисами требуется дополнительная настройка

## Расширение тестов

Для добавления новых тестов:

1. Создайте новый файл `test_*.py` в директории `tests/`
2. Используйте существующие фикстуры из `conftest.py`
3. Следуйте структуре существующих тестов
4. Добавьте маркеры при необходимости

## Troubleshooting

### Проблемы с импортами
Убедитесь, что все зависимости установлены:
```bash
pip install -r requirements.txt
```

### Проблемы с async тестами
Убедитесь, что используется `pytest-asyncio` и тесты помечены `@pytest.mark.asyncio`

### Проблемы с моками
Проверьте, что моки правильно настроены и соответствуют реальным интерфейсам

