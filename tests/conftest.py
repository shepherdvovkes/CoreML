"""
Конфигурация pytest для интеграционных тестов
"""
import pytest
import asyncio
import os
import tempfile
import shutil
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Глобальный мок для vector_store, чтобы избежать проблем с инициализацией
mock_vector_store_global = MagicMock()
mock_vector_store_global.add_documents = Mock()
mock_vector_store_global.search = Mock(return_value=[
    {
        'text': 'Test document content',
        'metadata': {'source': 'test.pdf'},
        'distance': 0.1
    }
])

# Мокаем create_vector_store до импорта main
with patch('core.rag.vector_store.create_vector_store', return_value=mock_vector_store_global):
    with patch('core.rag.rag_service.create_vector_store', return_value=mock_vector_store_global):
        # Импорты приложения
        from main import app
from core.rag.rag_service import RAGService
from core.rag.vector_store import create_vector_store
from core.services.cache_service import CacheService
from core.mcp.law_client import LawMCPClient
from core.router.query_router import QueryRouter
from core.llm.factory import LLMProviderFactory
from config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для всех тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_data_dir():
    """Создание временной директории для тестовых данных"""
    temp_dir = tempfile.mkdtemp(prefix="coreml_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def mock_redis():
    """Мок Redis для тестов"""
    async def async_iter_mock(match=None, **kwargs):
        """Async iterator для scan_iter"""
        keys = ["rag:search:query1", "rag:search:query2", "rag:context:query1"]
        pattern = match or "*"
        for key in keys:
            # Простая проверка паттерна
            if "*" in pattern:
                prefix = pattern.replace("*", "")
                if prefix == "" or key.startswith(prefix):
                    yield key
            elif pattern in key:
                yield key
    
    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_client.get = AsyncMock(return_value=None)
    mock_redis_client.setex = AsyncMock(return_value=True)
    mock_redis_client.delete = AsyncMock(return_value=1)
    mock_redis_client.scan_iter = async_iter_mock  # Async generator
    mock_redis_client.exists = AsyncMock(return_value=0)
    mock_redis_client.info = AsyncMock(return_value={
        "connected_clients": 1,
        "used_memory_human": "1M",
        "redis_version": "7.0.0"
    })
    mock_redis_client.close = AsyncMock()
    return mock_redis_client


@pytest.fixture(scope="function")
async def cache_service(mock_redis) -> CacheService:
    """Сервис кэширования с моком Redis"""
    cache = CacheService(redis_url="redis://localhost:6379/1")
    # Правильный путь для мока redis.asyncio.from_url
    with patch('redis.asyncio.from_url', return_value=mock_redis):
        cache._client = mock_redis  # Устанавливаем мок напрямую
    yield cache
    await cache.close()


@pytest.fixture(scope="function")
def mock_vector_store():
    """Мок векторного хранилища"""
    mock_store = Mock()
    mock_store.add_documents = Mock()
    mock_store.search = Mock(return_value=[
        {
            'text': 'Test document content',
            'metadata': {'source': 'test.pdf'},
            'distance': 0.1
        }
    ])
    return mock_store


@pytest.fixture(scope="function")
def rag_service_without_cache(mock_vector_store):
    """RAG сервис без кэша"""
    with patch('core.rag.rag_service.create_vector_store', return_value=mock_vector_store):
        service = RAGService(cache_service=None)
        service.vector_store = mock_vector_store
        return service


@pytest.fixture(scope="function")
async def rag_service_with_cache(cache_service, mock_vector_store):
    """RAG сервис с кэшем"""
    with patch('core.rag.rag_service.create_vector_store', return_value=mock_vector_store):
        service = RAGService(cache_service=cache_service)
        service.vector_store = mock_vector_store
        return service


@pytest.fixture(scope="function")
def mock_law_client():
    """Мок MCP Law клиента"""
    mock_client = Mock(spec=LawMCPClient)
    mock_client.search_cases = AsyncMock(return_value=[
        {
            'title': 'Test Case 1',
            'description': 'Test case description',
            'case_number': '123/2024'
        }
    ])
    mock_client.get_case_details = AsyncMock(return_value={
        'case_number': '123/2024',
        'title': 'Test Case 1',
        'details': 'Full case details'
    })
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture(scope="function")
def mock_llm_provider():
    """Мок LLM провайдера"""
    async def async_stream_generator(*args, **kwargs):
        """Async generator для stream_generate с поддержкой параметров"""
        chunks = ["Test ", "response ", "chunks"]
        for chunk in chunks:
            yield chunk
    
    mock_provider = Mock()
    mock_provider.generate = AsyncMock(return_value=Mock(
        content="Test LLM response",
        model="test-model",
        usage={"tokens": 100}
    ))
    mock_provider.stream_generate = async_stream_generator
    mock_provider.close = AsyncMock()
    return mock_provider


@pytest.fixture(scope="function")
def query_router(rag_service_without_cache, mock_law_client, cache_service, mock_llm_provider):
    """QueryRouter с моками"""
    router = QueryRouter(
        rag_service=rag_service_without_cache,
        law_client=mock_law_client,
        cache_service=cache_service
    )
    with patch.object(LLMProviderFactory, 'get_provider', return_value=mock_llm_provider):
        yield router


@pytest.fixture(scope="function")
def test_client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client для тестов"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="function", autouse=True)
def reset_llm_factory():
    """Сброс фабрики LLM перед каждым тестом"""
    LLMProviderFactory._providers.clear()
    yield
    LLMProviderFactory._providers.clear()


@pytest.fixture(scope="function")
def sample_document_content():
    """Пример содержимого документа для тестов"""
    return b"""
    This is a test document for integration testing.
    It contains some legal information about contracts and agreements.
    The document is used to test RAG functionality.
    """


@pytest.fixture(scope="function")
def sample_query():
    """Пример запроса для тестов"""
    return "What is the legal framework for contracts?"


@pytest.fixture(scope="function")
def mock_celery_app():
    """Мок Celery приложения"""
    mock_app = Mock()
    mock_app.AsyncResult = Mock(return_value=Mock(
        state="SUCCESS",
        result={"status": "success"},
        info={"status": "success"}
    ))
    return mock_app

