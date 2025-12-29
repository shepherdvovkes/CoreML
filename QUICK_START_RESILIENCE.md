# Quick Start - Resilience Patterns

## Установка

```bash
# 1. Установите зависимости
pip install -r requirements.txt

# 2. Создайте .env файл (если еще нет)
# Добавьте настройки resilience:
RESILIENCE_RETRY_MAX_ATTEMPTS=3
RESILIENCE_CB_FAIL_MAX=5
RESILIENCE_LLM_TIMEOUT=120
```

## Базовое использование

### Для LLM вызовов

```python
from core.resilience import resilient_llm

@resilient_llm(name="openai_api")
async def call_openai():
    # Автоматически: retry 3 раза, timeout 120s, circuit breaker
    response = await client.post("/chat/completions", json=payload)
    return response
```

### Для HTTP запросов

```python
from core.resilience import resilient_http

@resilient_http(name="external_api")
async def fetch_data():
    # Автоматически: retry 3 раза, timeout 30s, circuit breaker
    response = await client.get("/api/data")
    return response
```

### Для RAG операций

```python
from core.resilience import resilient_rag

@resilient_rag(name="vector_search")
async def search_documents(query: str):
    # Автоматически: retry 3 раза, timeout 60s, circuit breaker
    results = vector_store.search(query)
    return results
```

### Для MCP вызовов

```python
from core.resilience import resilient_mcp

@resilient_mcp(name="law_search")
async def search_cases(query: str):
    # Автоматически: retry 3 раза, timeout 45s, circuit breaker
    response = await client.post("/search", json={"query": query})
    return response
```

## Кастомные настройки

```python
from core.resilience import resilient

@resilient(
    name="my_operation",
    retry_max_attempts=5,      # 5 попыток вместо 3
    timeout_seconds=180,       # 3 минуты вместо 30s
    cb_fail_max=10             # 10 ошибок для открытия circuit
)
async def my_operation():
    # Ваш код
    pass
```

## Мониторинг

```python
from core.resilience import get_all_circuit_breakers_status

# Проверить статус всех circuit breakers
statuses = get_all_circuit_breakers_status()
for status in statuses:
    print(f"{status['name']}: {status['state']}")
```

## Обработка ошибок

```python
from pybreaker import CircuitBreakerError

try:
    result = await call_with_resilience()
except CircuitBreakerError:
    # Circuit открыт - сервис недоступен
    return cached_result
except TimeoutError:
    # Timeout превышен
    return None
```

## Запуск примера

```bash
python examples/resilience_example.py
```

## Полная документация

- [RESILIENCE.md](RESILIENCE.md) - полная документация
- [RESILIENCE_IMPLEMENTATION_SUMMARY.md](RESILIENCE_IMPLEMENTATION_SUMMARY.md) - детали реализации
- [examples/resilience_example.py](examples/resilience_example.py) - примеры кода

## Что включено

✅ **Retry** - автоматическая повторная попытка при сбоях
✅ **Circuit Breaker** - защита от каскадных сбоев  
✅ **Timeout** - ограничение времени выполнения
✅ **Мониторинг** - встроенные функции для отслеживания статуса
✅ **Логирование** - автоматическое логирование всех событий
✅ **Конфигурация** - настройки через .env

## Уже применено в

- ✅ `core/llm/openai_provider.py` - OpenAI API вызовы
- ✅ `core/llm/custom_provider.py` - Кастомные LLM вызовы
- ✅ `core/mcp/law_client.py` - MCP сервер вызовы
- ✅ `core/services/http_client.py` - HTTP клиенты
- ✅ `core/rag/rag_service.py` - RAG операции

Все внешние вызовы теперь защищены! 🛡️



