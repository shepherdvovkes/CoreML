# CoreML RAG MCP Prompt Service

Production-ready маршрутизатор для работы с различными источниками данных: RAG для документов, MCP серверы для юридической информации и множественные LLM провайдеры.

## Описание проекта

CoreML RAG MCP Prompt Service - это stateless микросервис для интеллектуальной обработки юридических запросов с использованием технологии RAG (Retrieval-Augmented Generation), интеграции с внешними MCP серверами и поддержкой множественных LLM провайдеров.

Проект реализует production-ready архитектуру с горизонтальным масштабированием, автоматическим кэшированием, внешней векторной базой данных и комплексной системой отказоустойчивости.

## Архитектура

```
CoreML_RAG_MCP_Prompt/
├── core/
│   ├── llm/              # LLM провайдеры (OpenAI, LMStudio, Custom)
│   ├── rag/              # RAG система для документов
│   ├── mcp/              # MCP клиенты (Закон онлайн)
│   └── router/           # Маршрутизатор запросов
├── data/                 # Данные и векторная БД
├── logs/                 # Логи приложения
├── config.py            # Конфигурация
├── main.py              # FastAPI сервер
└── requirements.txt    # Зависимости
```

## Возможности

- **RAG (Retrieval-Augmented Generation)**: Работа с документами (PDF, DOCX, XLSX, TXT, HTML)
- **MCP интеграция**: Доступ к базе данных Закон онлайн
- **Множественные LLM провайдеры**: OpenAI, LMStudio, кастомные API
- **Автоматическая маршрутизация**: Определение источника данных на основе запроса
- **Потоковая генерация**: Поддержка streaming ответов
- **Фоновая обработка**: Celery + Redis для асинхронной обработки документов
- **HTTP межсервисная коммуникация**: Готовые клиенты для взаимодействия между сервисами
- **Resilience Patterns**: Автоматические retry, circuit breaker и timeout для всех внешних вызовов

## Установка

1. Клонируйте репозиторий
2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

4. Настройте переменные окружения в `.env`

5. Запустите Redis (через Docker или локально):
```bash
# Через Docker Compose
docker-compose up -d redis

# Или локально
redis-server
```

## Использование

### Запуск сервисов

#### 1. Запуск API сервера
```bash
python main.py
```
Сервер будет доступен по адресу `http://localhost:8000`

#### 2. Запуск Celery Worker (для фоновых задач)
```bash
# Через скрипт
chmod +x scripts/start_celery_worker.sh
./scripts/start_celery_worker.sh

# Или напрямую
celery -A core.celery_app worker --loglevel=info --concurrency=4
```

#### 3. Запуск Flower (мониторинг Celery, опционально)
```bash
# Через скрипт
chmod +x scripts/start_flower.sh
./scripts/start_flower.sh

# Или через Docker Compose
docker-compose up -d flower

# Или напрямую
celery -A core.celery_app flower --port=5555
```
Flower будет доступен по адресу `http://localhost:5555`

### Запуск всех сервисов через Docker Compose
```bash
docker-compose up -d
```

### API Endpoints

#### POST `/query`
Обработка запроса пользователя

```json
{
  "query": "Какие права у меня при расторжении договора?",
  "llm_provider": "openai",
  "model": "gpt-3.5-turbo",
  "use_rag": true,
  "use_law": true
}
```

#### POST `/query/stream`
Потоковая обработка запроса

#### POST `/rag/add-document`
Добавление документа в RAG систему (асинхронная обработка через Celery)

**Ответ:**
```json
{
  "status": "queued",
  "task_id": "abc123-def456-...",
  "message": "Document queued for processing",
  "check_status_url": "/rag/task/abc123-def456-..."
}
```

#### GET `/rag/task/{task_id}`
Получение статуса задачи обработки документа

**Ответы:**
- `pending`: Задача в очереди
- `processing`: Задача выполняется
- `success`: Задача выполнена успешно
- `failure`: Ошибка при выполнении

#### POST `/rag/add-documents-batch`
Пакетное добавление документов в RAG систему

#### GET `/rag/search?query=...&top_k=5`
Поиск в RAG системе

#### POST `/mcp/law/search-cases?query=...&instance=3&limit=25`
Поиск судебных дел

#### GET `/mcp/law/case/{case_number}`
Получение деталей дела

## Конфигурация

Основные настройки в файле `config.py` и `.env`:

- **LLM Providers**: Настройки для OpenAI, LMStudio, кастомных API
- **RAG**: Параметры векторной БД, размер чанков, модель эмбеддингов
- **MCP**: URL и ключи для MCP серверов
- **Server**: Хост, порт, уровень логирования
- **Celery**: Настройки брокера (Redis), retry, timeout
- **Redis**: URL подключения, TTL для кэша

## Структура модулей

### LLM Providers (`core/llm/`)
- `base.py`: Базовый класс для провайдеров
- `openai_provider.py`: Провайдер OpenAI API
- `lmstudio_provider.py`: Провайдер LMStudio
- `custom_provider.py`: Провайдер для кастомных API
- `factory.py`: Фабрика для создания провайдеров

### RAG (`core/rag/`)
- `document_processor.py`: Обработка документов (PDF, DOCX, XLSX, TXT, HTML)
- `vector_store.py`: Векторное хранилище (ChromaDB)
- `rag_service.py`: Сервис для работы с RAG

### MCP (`core/mcp/`)
- `law_client.py`: Клиент для MCP сервера Закон онлайн

### Router (`core/router/`)
- `query_router.py`: Маршрутизатор запросов с автоматическим определением источников

### Celery (`core/`)
- `celery_app.py`: Конфигурация Celery
- `tasks.py`: Фоновые задачи для обработки документов

### HTTP Services (`core/services/`)
- `http_client.py`: HTTP клиенты для межсервисной коммуникации
  - `ServiceHTTPClient`: Базовый клиент с retry логикой
  - `RAGServiceClient`: Клиент для RAG сервиса
  - `EmbeddingServiceClient`: Клиент для Embedding сервиса

## Примеры использования

### Python клиент

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/query",
        json={
            "query": "Какие права у меня при расторжении договора?",
            "llm_provider": "openai"
        }
    )
    print(response.json())
```

### cURL

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Какие права у меня при расторжении договора?",
    "llm_provider": "openai"
  }'
```

## Разработка

Проект использует:
- **FastAPI** для API сервера
- **ChromaDB** для векторного хранилища
- **Sentence Transformers** для эмбеддингов
- **LangChain** для работы с документами
- **httpx** для асинхронных HTTP запросов
- **Celery** для фоновых задач
- **Redis** для брокера сообщений и кэширования
- **Flower** для мониторинга Celery

## Архитектура с Celery

```
┌─────────────┐
│  API Server │ (FastAPI)
└──────┬──────┘
       │
       ├─── POST /rag/add-document
       │    └───> Celery Task Queue (Redis)
       │              └───> Celery Worker
       │                        └───> RAG Service
       │
       └─── GET /rag/task/{task_id}
            └───> Redis (результаты задач)
```

## HTTP межсервисная коммуникация

Проект включает готовые HTTP клиенты для взаимодействия между сервисами:

```python
from core.services.http_client import RAGServiceClient, EmbeddingServiceClient

# RAG Service Client
rag_client = RAGServiceClient(base_url="http://rag-service:8001")
results = await rag_client.search("query", top_k=5)

# Embedding Service Client
embedding_client = EmbeddingServiceClient(base_url="http://embedding-service:8002")
embeddings = await embedding_client.encode(["text1", "text2"])
```

Все клиенты включают:
- Автоматический retry с exponential backoff
- Circuit breaker защиту
- Timeout обработку
- Health check методы
- Обработку ошибок

## Resilience Patterns (Отказоустойчивость)

Проект включает комплексную систему resilience паттернов для повышения надежности:

### Основные паттерны

1. **Retry** - автоматическая повторная попытка при временных сбоях
2. **Circuit Breaker** - защита от каскадных сбоев
3. **Timeout** - ограничение времени выполнения операций

### Применение

Все внешние вызовы автоматически защищены:

```python
from core.resilience import resilient_llm, resilient_http, resilient_mcp

# LLM вызовы (timeout 120s, retry 3 раза)
@resilient_llm(name="openai_api")
async def call_openai():
    ...

# HTTP запросы (timeout 30s, circuit breaker)
@resilient_http(name="external_api")
async def fetch_data():
    ...

# MCP вызовы (timeout 45s, retry + circuit breaker)
@resilient_mcp(name="law_search")
async def search_cases():
    ...
```

### Конфигурация

Настройки через `.env`:

```bash
# Retry
RESILIENCE_RETRY_MAX_ATTEMPTS=3
RESILIENCE_RETRY_MIN_WAIT=1
RESILIENCE_RETRY_MAX_WAIT=10

# Circuit Breaker
RESILIENCE_CB_FAIL_MAX=5
RESILIENCE_CB_TIMEOUT=60

# Timeouts
RESILIENCE_LLM_TIMEOUT=120
RESILIENCE_RAG_TIMEOUT=60
RESILIENCE_MCP_TIMEOUT=45
```

### Мониторинг

```python
from core.resilience import get_all_circuit_breakers_status

# Проверка статуса всех circuit breakers
status = get_all_circuit_breakers_status()
```

Подробная документация: [RESILIENCE.md](RESILIENCE.md)

Примеры использования: [examples/resilience_example.py](examples/resilience_example.py)

## Лицензия

MIT

