# Resilience Patterns - Руководство

## Обзор

В проект интегрированы паттерны отказоустойчивости (resilience patterns) для повышения надежности и стабильности системы:

- **Retry** - автоматическая повторная попытка при временных сбоях
- **Circuit Breaker** - защита от каскадных сбоев
- **Timeout** - ограничение времени выполнения операций

## Архитектура

### Модуль `core/resilience.py`

Центральный модуль, содержащий все декораторы и конфигурацию:

- `@with_retry` - декоратор для retry с экспоненциальным backoff
- `@with_circuit_breaker` - декоратор для circuit breaker
- `@with_timeout` - декоратор для timeout
- `@resilient` - комбинированный декоратор
- `@resilient_llm`, `@resilient_rag`, `@resilient_mcp`, `@resilient_http` - предустановленные конфигурации

### Конфигурация

Все настройки управляются через `config.py` и `.env`:

```python
# Retry настройки
resilience_retry_max_attempts: int = 3
resilience_retry_min_wait: int = 1  # секунды
resilience_retry_max_wait: int = 10  # секунды
resilience_retry_multiplier: int = 2

# Circuit Breaker настройки
resilience_cb_fail_max: int = 5  # количество ошибок для открытия circuit
resilience_cb_timeout: int = 60  # секунды до попытки восстановления

# Timeout настройки (в секундах)
resilience_default_timeout: int = 30
resilience_llm_timeout: int = 120
resilience_rag_timeout: int = 60
resilience_mcp_timeout: int = 45
resilience_http_timeout: int = 30
```

Пример `.env`:

```bash
RESILIENCE_RETRY_MAX_ATTEMPTS=5
RESILIENCE_CB_FAIL_MAX=10
RESILIENCE_LLM_TIMEOUT=180
```

## Использование

### 1. Декоратор @retry

Автоматически повторяет операцию при временных сбоях:

```python
from core.resilience import with_retry

@with_retry(
    max_attempts=5,
    min_wait=1,
    max_wait=30,
    exceptions=(TimeoutError, ConnectionError)
)
async def fetch_data():
    # Ваш код
    pass
```

**Параметры:**
- `max_attempts` - максимальное количество попыток (по умолчанию из конфига)
- `min_wait` - минимальное время ожидания между попытками в секундах
- `max_wait` - максимальное время ожидания между попытками в секундах
- `multiplier` - множитель для экспоненциального backoff
- `exceptions` - типы исключений для retry

### 2. Декоратор @circuit_breaker

Защищает от каскадных сбоев, временно "размыкая" цепь при превышении порога ошибок:

```python
from core.resilience import with_circuit_breaker

@with_circuit_breaker(
    name="external_api",  # уникальное имя
    fail_max=5,
    timeout=60
)
async def call_external_api():
    # Ваш код
    pass
```

**Параметры:**
- `name` - уникальное имя circuit breaker (обязательно)
- `fail_max` - количество ошибок для открытия circuit
- `timeout` - время в секундах до попытки восстановления

**Состояния Circuit Breaker:**
- **CLOSED** (закрыт) - нормальная работа
- **OPEN** (открыт) - все запросы отклоняются, сервис недоступен
- **HALF_OPEN** (полуоткрыт) - пробная попытка восстановления

### 3. Декоратор @timeout

Ограничивает максимальное время выполнения операции:

```python
from core.resilience import with_timeout

@with_timeout(seconds=30)
async def slow_operation():
    # Ваш код
    pass
```

### 4. Комбинированный декоратор @resilient

Применяет все три паттерна одновременно:

```python
from core.resilience import resilient

@resilient(
    name="my_service",
    retry_max_attempts=3,
    circuit_breaker=True,
    cb_fail_max=5,
    timeout_seconds=30
)
async def robust_operation():
    # Ваш код
    pass
```

### 5. Предустановленные конфигурации

Для разных типов операций есть готовые декораторы:

#### LLM вызовы

```python
from core.resilience import resilient_llm

@resilient_llm(name="openai_generate")
async def call_llm():
    # Timeout 120s, retry 3 раза, circuit breaker активен
    pass
```

#### RAG операции

```python
from core.resilience import resilient_rag

@resilient_rag(name="vector_search")
async def search_vectors():
    # Timeout 60s, retry 3 раза, circuit breaker активен
    pass
```

#### MCP вызовы

```python
from core.resilience import resilient_mcp

@resilient_mcp(name="law_search")
async def search_cases():
    # Timeout 45s, retry 3 раза, circuit breaker активен
    pass
```

#### HTTP запросы

```python
from core.resilience import resilient_http

@resilient_http(name="api_call")
async def make_http_request():
    # Timeout 30s, retry 3 раза, circuit breaker активен
    pass
```

## Примеры из проекта

### OpenAI Provider

```python
from core.resilience import resilient_llm

class OpenAIProvider:
    @resilient_llm(name="openai_generate")
    async def generate(self, messages, **kwargs):
        # Автоматические retry, circuit breaker и timeout
        response = await self.client.post("/chat/completions", json=payload)
        return response
```

### MCP Law Client

```python
from core.resilience import resilient_mcp

class LawMCPClient:
    @resilient_mcp(name="mcp_search_cases")
    async def search_cases(self, query: str):
        # Автоматические retry, circuit breaker и timeout
        response = await self.client.post("/search", json={"query": query})
        return response.json()
    
    @resilient_mcp(name="mcp_extract_arguments", timeout_seconds=90)
    async def extract_case_arguments(self, query: str):
        # Увеличенный timeout для сложных операций
        response = await self.client.post("/extract", json={"query": query})
        return response.json()
```

### RAG Service

```python
from core.resilience import resilient_rag

class RAGService:
    @resilient_rag(name="rag_search")
    async def search(self, query: str, top_k: int = 5):
        # Автоматические retry, circuit breaker и timeout
        results = self.vector_store.search(query, top_k)
        return results
```

## Мониторинг Circuit Breakers

### Проверка статуса

```python
from core.resilience import get_circuit_breaker_status, get_all_circuit_breakers_status

# Статус конкретного circuit breaker
status = get_circuit_breaker_status("openai_generate")
print(status)
# {'name': 'openai_generate', 'state': 'closed', 'fail_counter': 0, 'fail_max': 5}

# Статус всех circuit breakers
all_status = get_all_circuit_breakers_status()
for cb_status in all_status:
    print(f"{cb_status['name']}: {cb_status['state']}")
```

### Сброс Circuit Breakers

```python
from core.resilience import CircuitBreakers

# Сброс всех circuit breakers (для тестирования)
CircuitBreakers.reset_all()
```

## Обработка исключений

### Retry Errors

Когда retry исчерпывает все попытки, выбрасывается последнее исключение:

```python
from tenacity import RetryError

try:
    await resilient_operation()
except TimeoutError:
    # Последняя попытка превысила timeout
    logger.error("Operation timed out after all retries")
except httpx.HTTPStatusError as e:
    # HTTP ошибка после всех попыток
    logger.error(f"HTTP error: {e.response.status_code}")
```

### Circuit Breaker Errors

Когда circuit открыт, выбрасывается `CircuitBreakerError`:

```python
from pybreaker import CircuitBreakerError

try:
    await call_with_circuit_breaker()
except CircuitBreakerError:
    # Сервис временно недоступен
    logger.warning("Circuit breaker is OPEN, service unavailable")
    # Можно вернуть fallback значение или кэшированные данные
    return cached_result
```

### Timeout Errors

```python
try:
    await operation_with_timeout()
except TimeoutError as e:
    logger.error(f"Operation timed out: {e}")
    # Обработка timeout
```

## Best Practices

### 1. Выбор правильных таймаутов

- **LLM вызовы**: 120-180 секунд (генерация может быть медленной)
- **RAG поиск**: 30-60 секунд (векторный поиск обычно быстрый)
- **HTTP API**: 10-30 секунд (стандартные REST запросы)
- **MCP вызовы**: 30-60 секунд (зависит от сложности)

### 2. Настройка retry

- Используйте retry только для **idempotent** операций (можно повторять безопасно)
- Не используйте retry для операций изменения данных без idempotency ключей
- Настройте исключения для retry аккуратно

```python
# Хорошо - retry только для временных сбоев
@with_retry(exceptions=(TimeoutError, ConnectionError))
async def fetch_data():
    pass

# Плохо - retry для всех ошибок
@with_retry(exceptions=(Exception,))  # НЕ ДЕЛАЙТЕ ТАК
async def update_database():
    pass
```

### 3. Именование Circuit Breakers

Используйте уникальные, описательные имена:

```python
# Хорошо
@with_circuit_breaker(name="openai_gpt4_api")
@with_circuit_breaker(name="qdrant_vector_search")
@with_circuit_breaker(name="mcp_law_extract_arguments")

# Плохо
@with_circuit_breaker(name="api")  # Слишком общее
@with_circuit_breaker(name="cb1")  # Неинформативное
```

### 4. Комбинирование декораторов

Порядок важен! Применяйте в таком порядке:

```python
# Правильно: timeout -> circuit_breaker -> retry
@with_timeout(30)
@with_circuit_breaker("service")
@with_retry()
async def operation():
    pass

# Или используйте @resilient, который применяет в правильном порядке
@resilient(name="service", timeout_seconds=30)
async def operation():
    pass
```

### 5. Логирование

Все декораторы автоматически логируют события:

- Retry попытки - WARNING уровень
- Circuit breaker открытие/закрытие - ERROR/INFO уровень
- Timeout превышения - ERROR уровень

### 6. Мониторинг в Production

Добавьте эндпоинт для мониторинга:

```python
from fastapi import APIRouter
from core.resilience import get_all_circuit_breakers_status

router = APIRouter()

@router.get("/health/circuit-breakers")
async def circuit_breakers_health():
    """Статус всех circuit breakers"""
    return {
        "circuit_breakers": get_all_circuit_breakers_status(),
        "timestamp": datetime.utcnow().isoformat()
    }
```

## Тестирование

### Тест retry

```python
import pytest
from unittest.mock import AsyncMock
from core.resilience import with_retry

@pytest.mark.asyncio
async def test_retry_on_failure():
    mock_func = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), "success"])
    
    @with_retry(max_attempts=3)
    async def func():
        return await mock_func()
    
    result = await func()
    assert result == "success"
    assert mock_func.call_count == 3
```

### Тест circuit breaker

```python
import pytest
from core.resilience import with_circuit_breaker, CircuitBreakers

@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    CircuitBreakers.reset_all()
    
    call_count = 0
    
    @with_circuit_breaker(name="test_cb", fail_max=3)
    async def failing_func():
        nonlocal call_count
        call_count += 1
        raise Exception("Error")
    
    # Первые 3 вызова должны выполниться
    for _ in range(3):
        with pytest.raises(Exception):
            await failing_func()
    
    # 4-й вызов должен быть заблокирован circuit breaker
    from pybreaker import CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        await failing_func()
    
    assert call_count == 3  # Только первые 3 попытки
```

## Troubleshooting

### Проблема: Слишком много retry

**Симптом**: Медленный ответ, много retry попыток в логах

**Решение**:
- Уменьшите `resilience_retry_max_attempts`
- Проверьте, не пытаетесь ли вы retry для постоянных ошибок (не временных)

### Проблема: Circuit breaker постоянно открыт

**Симптом**: `CircuitBreakerError` в логах

**Решение**:
- Проверьте здоровье внешнего сервиса
- Увеличьте `resilience_cb_fail_max`
- Увеличьте `resilience_cb_timeout` для более медленного восстановления

### Проблема: Timeout слишком короткий

**Симптом**: `TimeoutError` для валидных запросов

**Решение**:
- Увеличьте соответствующий timeout в конфиге
- Используйте специализированные таймауты для медленных операций

```python
@resilient_llm(name="slow_operation", timeout_seconds=300)  # 5 минут
async def generate_large_response():
    pass
```

## Зависимости

Установка:

```bash
pip install -r requirements.txt
```

Требуемые библиотеки:
- `tenacity` - для retry с экспоненциальным backoff
- `pybreaker` - для circuit breaker паттерна
- `httpx` - HTTP клиент с async поддержкой

## Дополнительные ресурсы

- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [PyBreaker Documentation](https://github.com/danielfm/pybreaker)
- [Resilience Patterns Overview](https://docs.microsoft.com/en-us/azure/architecture/patterns/category/resiliency)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)

