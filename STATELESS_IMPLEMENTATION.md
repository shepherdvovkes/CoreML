# Реализация Stateless API, внешней векторной БД и Redis кэша

## Обзор изменений

Реализованы три ключевых улучшения архитектуры:

1. **Stateless API серверы** - убраны глобальные экземпляры, используется dependency injection
2. **Внешняя векторная БД** - поддержка Qdrant с fallback на ChromaDB
3. **Redis кэширование** - кэширование RAG и LLM запросов

## Изменения в архитектуре

### 1. Stateless API (main.py)

**До:**
```python
# Глобальные экземпляры (stateful)
router = QueryRouter()
rag_service = RAGService()
law_client = LawMCPClient()
```

**После:**
```python
# Dependency Injection (stateless)
async def get_query_router(
    rag_service: RAGService = Depends(get_rag_service),
    law_client: LawMCPClient = Depends(get_law_client),
    cache_service: CacheService = Depends(get_cache_service)
) -> QueryRouter:
    return QueryRouter(...)
```

**Преимущества:**
- Горизонтальное масштабирование (можно запускать несколько инстансов)
- Нет состояния между запросами
- Легче тестировать (можно мокировать зависимости)

### 2. Внешняя векторная БД (core/rag/vector_store.py)

**До:**
- Только локальная ChromaDB на диске

**После:**
- Поддержка Qdrant (внешняя БД по умолчанию)
- Fallback на ChromaDB если Qdrant недоступен
- Настройка через `config.py`:
  ```python
  rag_vector_db_type: str = "qdrant"  # или "chroma"
  qdrant_url: str = "http://localhost:6333"
  ```

**Преимущества:**
- Общая векторная БД для всех инстансов API
- Масштабируемость (Qdrant может работать в кластере)
- Персистентность данных независимо от API серверов

### 3. Redis кэширование (core/services/cache_service.py)

**Новый сервис:**
- `CacheService` - универсальный сервис кэширования
- Поддержка TTL, паттернов удаления
- Автоматическая сериализация/десериализация JSON

**Интеграция:**
- RAG поиск кэшируется (TTL: 1 час)
- LLM ответы кэшируются (TTL: 30 минут)
- Параллельная обработка источников (RAG + Law MCP)

**Преимущества:**
- Снижение нагрузки на векторную БД и LLM
- Ускорение ответов для повторяющихся запросов
- Экономия ресурсов

## Конфигурация

### config.py

Добавлены новые настройки:

```python
# Vector DB
rag_vector_db_type: str = "qdrant"  # qdrant, chroma
qdrant_url: str = "http://localhost:6333"
qdrant_api_key: str = ""
qdrant_collection_name: str = "legal_documents"

# Redis Cache
redis_url: str = "redis://localhost:6379/0"
redis_cache_ttl: int = 3600  # 1 hour
```

### docker-compose.yml

Добавлен сервис Qdrant:

```yaml
qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"  # HTTP API
    - "6334:6334"  # gRPC API
  volumes:
    - qdrant_data:/qdrant/storage
```

## Запуск

### 1. Запуск зависимостей

```bash
docker-compose up -d redis qdrant
```

### 2. Настройка переменных окружения (.env)

```env
# Vector DB
RAG_VECTOR_DB_TYPE=qdrant
QDRANT_URL=http://localhost:6333

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600
```

### 3. Запуск API сервера

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Проверка работоспособности

### Health Check

```bash
curl http://localhost:8000/health
```

Должен вернуть статус всех зависимостей:
- Redis cache
- Vector DB (Qdrant/ChromaDB)

### Тест кэширования

1. Первый запрос (cache miss):
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое договор?"}'
```

2. Второй запрос (cache hit - быстрее):
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое договор?"}'
```

## Производительность

### До улучшений:
- Последовательная обработка источников
- Нет кэширования
- Локальная БД на диске

### После улучшений:
- Параллельная обработка источников (`asyncio.gather`)
- Кэширование RAG и LLM запросов
- Внешняя векторная БД (Qdrant)

**Ожидаемое улучшение:**
- Первый запрос: ~2-3 секунды (как раньше)
- Повторный запрос: ~100-300ms (из кэша)
- Параллельная обработка: ~30-50% быстрее

## Масштабируемость

### Горизонтальное масштабирование

Теперь можно запускать несколько инстансов API:

```bash
# Инстанс 1
uvicorn main:app --port 8000

# Инстанс 2
uvicorn main:app --port 8001

# Инстанс 3
uvicorn main:app --port 8002
```

Все инстансы:
- Используют общую векторную БД (Qdrant)
- Используют общий кэш (Redis)
- Не имеют состояния между запросами

### Load Balancer

Можно использовать nginx или другой load balancer:

```nginx
upstream coreml_api {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}
```

## Миграция с ChromaDB на Qdrant

Если у вас уже есть данные в ChromaDB:

1. Экспорт данных из ChromaDB (если нужно)
2. Установка Qdrant: `docker-compose up -d qdrant`
3. Изменение конфигурации: `RAG_VECTOR_DB_TYPE=qdrant`
4. Переиндексация документов (они будут добавлены в Qdrant)

## Обратная совместимость

- Старый код с `VectorStore()` продолжит работать
- ChromaDB остается доступным как fallback
- Если Qdrant недоступен, автоматически используется ChromaDB

## Следующие шаги

1. Мониторинг производительности кэша
2. Настройка TTL для разных типов запросов
3. Репликация Qdrant для высокой доступности
4. Redis кластер для масштабирования кэша

