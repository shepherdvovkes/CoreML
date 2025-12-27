"""
Примеры улучшений архитектуры на основе анализа
"""

# ============================================================================
# 1. КЭШИРОВАНИЕ
# ============================================================================

from functools import wraps
from typing import Optional
import hashlib
import json
import redis.asyncio as redis
from datetime import timedelta

class CacheService:
    """Сервис кэширования для RAG и LLM ответов"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
    
    async def get(self, key: str) -> Optional[str]:
        """Получить значение из кэша"""
        return await self.redis_client.get(key)
    
    async def set(self, key: str, value: str, ttl: int = 3600):
        """Установить значение в кэш"""
        await self.redis_client.setex(key, ttl, value)
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Генерация ключа кэша"""
        key_data = json.dumps(kwargs, sort_keys=True)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

def cached_rag_search(ttl: int = 3600):
    """Декоратор для кэширования RAG поиска"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, query: str, top_k: int = None, *args, **kwargs):
            cache_key = self.cache._generate_key("rag_search", query=query, top_k=top_k)
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
            
            result = await func(self, query, top_k, *args, **kwargs)
            await self.cache.set(cache_key, json.dumps(result), ttl)
            return result
        return wrapper
    return decorator


# ============================================================================
# 2. ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА ИСТОЧНИКОВ
# ============================================================================

import asyncio
from typing import List, Tuple

class ImprovedQueryRouter:
    """Улучшенный роутер с параллельной обработкой"""
    
    async def process_query_parallel(
        self,
        query: str,
        use_rag: bool = True,
        use_law: bool = True
    ) -> dict:
        """Параллельная обработка всех источников"""
        
        # Создаем задачи для параллельного выполнения
        tasks = []
        
        if use_rag:
            tasks.append(
                asyncio.create_task(
                    self._get_rag_context_async(query),
                    name="rag"
                )
            )
        
        if use_law:
            tasks.append(
                asyncio.create_task(
                    self._get_law_context_async(query),
                    name="law"
                )
            )
        
        # Ждем все задачи с timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            # Fallback: используем то что успело загрузиться
            results = []
            for task in tasks:
                if task.done():
                    results.append(task.result())
                else:
                    task.cancel()
                    results.append(None)
        
        # Обрабатываем результаты
        contexts = []
        sources = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error in task {tasks[i].get_name()}: {result}")
                continue
            
            if result:
                contexts.append(result["context"])
                sources.append(result["source"])
        
        return {
            "contexts": contexts,
            "sources": sources
        }
    
    async def _get_rag_context_async(self, query: str) -> dict:
        """Асинхронный RAG поиск"""
        # Запускаем в thread pool для синхронных операций
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            self.rag_service.search,
            query,
            5
        )
        context = self.rag_service.get_context(query, top_k=5)
        return {"context": context, "source": "RAG"}
    
    async def _get_law_context_async(self, query: str) -> dict:
        """Асинхронный MCP поиск"""
        cases = await self.law_client.search_cases(query, limit=5)
        context = self._format_law_context(cases)
        return {"context": context, "source": "MCP_Law"}


# ============================================================================
# 3. RETRY И CIRCUIT BREAKER
# ============================================================================

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from circuitbreaker import circuit
import httpx

class ResilientLLMProvider:
    """LLM провайдер с retry и circuit breaker"""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
    )
    @circuit(failure_threshold=5, recovery_timeout=60)
    async def generate_with_retry(
        self,
        messages: List[dict],
        **kwargs
    ) -> dict:
        """Генерация с автоматическим retry"""
        try:
            response = await self.client.post(
                "/chat/completions",
                json={"messages": messages, **kwargs},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                # Retry только для server errors
                raise
            else:
                # Client errors не retry
                raise


# ============================================================================
# 4. ВЕРСИОНИРОВАНИЕ МОДЕЛЕЙ
# ============================================================================

from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ModelVersion:
    """Версия модели с метаданными"""
    name: str
    version: str
    created_at: datetime
    embedding_dim: int
    chunk_strategy: str
    metadata: Dict[str, Any]

class VersionedVectorStore:
    """Векторное хранилище с версионированием"""
    
    def __init__(self, model_version: ModelVersion):
        self.model_version = model_version
        # Создаем коллекцию с версией в имени
        collection_name = f"documents_v{model_version.version}"
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "model_name": model_version.name,
                "version": model_version.version,
                "created_at": model_version.created_at.isoformat(),
                "chunk_strategy": model_version.chunk_strategy
            }
        )
    
    def add_document_with_version(self, text: str, metadata: dict):
        """Добавление документа с версией модели"""
        metadata.update({
            "embedding_model_version": self.model_version.version,
            "embedding_model_name": self.model_version.name,
            "added_at": datetime.now().isoformat()
        })
        # ... добавление в коллекцию


# ============================================================================
# 5. МОНИТОРИНГ И МЕТРИКИ
# ============================================================================

from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time

# Метрики
query_counter = Counter('queries_total', 'Total queries', ['source', 'status'])
query_duration = Histogram('query_duration_seconds', 'Query duration', ['source'])
rag_search_duration = Histogram('rag_search_seconds', 'RAG search duration')
llm_tokens = Counter('llm_tokens_total', 'Total LLM tokens', ['model', 'type'])

def monitor_query(func):
    """Декоратор для мониторинга запросов"""
    @wraps(func)
    async def wrapper(self, query: str, *args, **kwargs):
        start_time = time.time()
        source = kwargs.get('source', 'unknown')
        
        try:
            result = await func(self, query, *args, **kwargs)
            query_counter.labels(source=source, status='success').inc()
            query_duration.labels(source=source).observe(time.time() - start_time)
            return result
        except Exception as e:
            query_counter.labels(source=source, status='error').inc()
            raise
    return wrapper


# ============================================================================
# 6. УЛУЧШЕННАЯ ОБРАБОТКА ОШИБОК
# ============================================================================

from enum import Enum
from typing import Optional

class ErrorType(Enum):
    """Типы ошибок"""
    NETWORK = "network"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL = "internal"

class ServiceError(Exception):
    """Базовый класс для ошибок сервиса"""
    def __init__(
        self,
        message: str,
        error_type: ErrorType,
        retryable: bool = False,
        status_code: int = 500
    ):
        self.message = message
        self.error_type = error_type
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(self.message)

class ImprovedQueryRouter:
    """Роутер с улучшенной обработкой ошибок"""
    
    async def process_query_safe(
        self,
        query: str,
        **kwargs
    ) -> dict:
        """Обработка запроса с fallback стратегией"""
        
        contexts = []
        sources = []
        errors = []
        
        # Пытаемся получить RAG контекст
        if kwargs.get('use_rag', True):
            try:
                rag_context = await self._get_rag_context_safe(query)
                if rag_context:
                    contexts.append(rag_context)
                    sources.append("RAG")
            except ServiceError as e:
                errors.append({"source": "RAG", "error": str(e)})
                logger.warning(f"RAG failed, continuing without it: {e}")
        
        # Пытаемся получить Law контекст
        if kwargs.get('use_law', True):
            try:
                law_context = await self._get_law_context_safe(query)
                if law_context:
                    contexts.append(law_context)
                    sources.append("MCP_Law")
            except ServiceError as e:
                errors.append({"source": "MCP_Law", "error": str(e)})
                logger.warning(f"Law MCP failed, continuing without it: {e}")
        
        # Если нет контекста, но есть ошибки - возвращаем частичный ответ
        if not contexts and errors:
            return {
                "answer": "Не удалось получить контекст из источников данных",
                "sources": [],
                "errors": errors,
                "partial": True
            }
        
        # Генерация ответа с доступным контекстом
        try:
            response = await self._generate_response(query, contexts)
            return {
                "answer": response,
                "sources": sources,
                "errors": errors if errors else None
            }
        except ServiceError as e:
            # Fallback: возвращаем контекст без LLM обработки
            return {
                "answer": "\n\n".join(contexts) if contexts else "Не удалось обработать запрос",
                "sources": sources,
                "errors": errors + [{"source": "LLM", "error": str(e)}],
                "partial": True
            }


# ============================================================================
# 7. STATELESS АРХИТЕКТУРА
# ============================================================================

from fastapi import Depends
from typing import Annotated

# Dependency injection для сервисов
def get_rag_service() -> RAGService:
    """Получить RAG сервис (может быть из DI контейнера)"""
    return RAGService()

def get_law_client() -> LawMCPClient:
    """Получить MCP клиент"""
    return LawMCPClient()

def get_query_router(
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    law_client: Annotated[LawMCPClient, Depends(get_law_client)]
) -> QueryRouter:
    """Создать роутер с зависимостями"""
    return QueryRouter(rag_service=rag_service, law_client=law_client)

# В main.py
@app.post("/query")
async def query(
    request: QueryRequest,
    router: Annotated[QueryRouter, Depends(get_query_router)]
):
    """Endpoint с dependency injection"""
    return await router.process_query(request.query)


# ============================================================================
# 8. HEALTH CHECKS
# ============================================================================

class HealthChecker:
    """Проверка здоровья зависимостей"""
    
    async def check_rag_health(self) -> dict:
        """Проверка RAG сервиса"""
        try:
            # Пробный поиск
            results = self.rag_service.search("test", top_k=1)
            return {"status": "healthy", "latency_ms": 0}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def check_vector_db_health(self) -> dict:
        """Проверка векторной БД"""
        try:
            # Проверка подключения
            collections = self.vector_store.client.list_collections()
            return {"status": "healthy", "collections": len(collections)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def check_mcp_health(self) -> dict:
        """Проверка MCP сервиса"""
        try:
            # Пробный запрос
            response = await self.law_client.client.get("/health", timeout=5.0)
            return {"status": "healthy" if response.status_code == 200 else "degraded"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    checker = HealthChecker()
    
    checks = {
        "rag": await checker.check_rag_health(),
        "vector_db": await checker.check_vector_db_health(),
        "mcp_law": await checker.check_mcp_health()
    }
    
    overall_status = "healthy" if all(
        c["status"] == "healthy" for c in checks.values()
    ) else "degraded"
    
    return {
        "status": overall_status,
        "checks": checks
    }


# ============================================================================
# 9. СТРУКТУРИРОВАННОЕ ЛОГИРОВАНИЕ
# ============================================================================

import structlog
import uuid

# Настройка structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

class RequestContext:
    """Контекст запроса для трейсинга"""
    def __init__(self):
        self.request_id = str(uuid.uuid4())
        self.trace_id = str(uuid.uuid4())
        self.user_id = None

@app.middleware("http")
async def add_request_context(request, call_next):
    """Middleware для добавления контекста"""
    context = RequestContext()
    request.state.context = context
    
    # Добавляем в логи
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=context.request_id,
        trace_id=context.trace_id
    )
    
    response = await call_next(request)
    return response

# Использование
async def process_query(self, query: str):
    logger.info(
        "query_received",
        query_length=len(query),
        user_id=request.state.context.user_id
    )
    
    # ... обработка
    
    logger.info(
        "query_processed",
        duration_ms=duration,
        sources_used=sources
    )

