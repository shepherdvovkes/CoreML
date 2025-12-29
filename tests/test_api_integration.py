"""
Интеграционные тесты для API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, Mock, MagicMock
from httpx import AsyncClient

# Мокаем create_vector_store до импорта main, чтобы избежать проблем с инициализацией
mock_vector_store = MagicMock()
with patch('core.rag.vector_store.create_vector_store', return_value=mock_vector_store):
    with patch('core.rag.rag_service.create_vector_store', return_value=mock_vector_store):
        from main import app
        from core.router.query_router import QueryRouter
        from core.rag.rag_service import RAGService
        from core.mcp.law_client import LawMCPClient
        from core.services.cache_service import CacheService
        from core.llm.factory import LLMProviderFactory


class TestHealthEndpoints:
    """Тесты для health check endpoints"""
    
    def test_root_endpoint(self, test_client):
        """Тест корневого endpoint"""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "CoreML RAG MCP Prompt Service"
        assert data["status"] == "running"
        assert data["architecture"] == "stateless"
    
    def test_health_endpoint(self, test_client, mock_redis):
        """Тест health check endpoint"""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            with patch('core.rag.vector_store.create_vector_store') as mock_vs:
                mock_vs.return_value = Mock()
                response = test_client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert "status" in data
                assert "dependencies" in data


class TestQueryEndpoints:
    """Тесты для query endpoints"""
    
    def test_query_endpoint_success(self, test_client, mock_llm_provider, 
                                     mock_law_client, rag_service_without_cache, 
                                     cache_service, sample_query):
        """Тест успешного запроса через /query"""
        # Убеждаемся, что мок law_client возвращает данные
        mock_law_client.search_cases = AsyncMock(return_value=[
            {
                'title': 'Test Case 1',
                'description': 'Test case description',
                'case_number': '123/2024'
            }
        ])
        
        # Мокаем get_rag_service чтобы избежать инициализации vector_store
        with patch('main.get_rag_service', return_value=rag_service_without_cache):
            with patch('main.get_law_client', return_value=mock_law_client):
                with patch('main.get_query_router') as mock_router:
                    router = QueryRouter(
                        rag_service=rag_service_without_cache,
                        law_client=mock_law_client,
                        cache_service=cache_service
                    )
                    router.process_query = AsyncMock(return_value={
                        "answer": "Test answer",
                        "sources": ["RAG", "MCP_Law"],
                        "model": "test-model",
                        "usage": {"tokens": 100},
                        "metadata": {"used_rag": True, "used_law": True}
                    })
                    mock_router.return_value = router
                    
                    response = test_client.post(
                        "/query",
                        json={
                            "query": sample_query,
                            "use_rag": True,
                            "use_law": True
                        }
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert "answer" in data
                    assert "sources" in data
                    # Проверяем, что есть хотя бы один источник
                    assert len(data["sources"]) > 0
    
    def test_query_endpoint_with_invalid_provider(self, test_client, sample_query, rag_service_without_cache):
        """Тест запроса с невалидным провайдером"""
        # Мокаем get_rag_service чтобы избежать инициализации vector_store
        with patch('main.get_rag_service', return_value=rag_service_without_cache):
            response = test_client.post(
                "/query",
                json={
                    "query": sample_query,
                    "llm_provider": "invalid_provider"
                }
            )
            assert response.status_code == 400
            assert "Unknown LLM provider" in response.json()["detail"]
    
    def test_query_stream_endpoint(self, test_client, mock_llm_provider,
                                    mock_law_client, rag_service_without_cache,
                                    cache_service, sample_query):
        """Тест потокового endpoint"""
        # Мокаем get_rag_service чтобы избежать инициализации vector_store
        with patch('main.get_rag_service', return_value=rag_service_without_cache):
            with patch('main.get_law_client', return_value=mock_law_client):
                with patch('main.get_query_router') as mock_router:
                    router = QueryRouter(
                        rag_service=rag_service_without_cache,
                        law_client=mock_law_client,
                        cache_service=cache_service
                    )
                    
                    # Мокаем LLM провайдер в router
                    with patch.object(LLMProviderFactory, 'get_provider', return_value=mock_llm_provider):
                        async def stream_mock():
                            chunks = ["Test ", "streaming ", "response"]
                            for chunk in chunks:
                                yield chunk
                        
                        router.stream_process_query = stream_mock
                        mock_router.return_value = router
                        
                        response = test_client.post(
                            "/query/stream",
                            json={
                                "query": sample_query,
                                "use_rag": True
                            }
                        )
                        assert response.status_code == 200
                        assert response.headers["content-type"] == "text/plain; charset=utf-8"
                        content = response.text
                        assert "Test" in content


class TestRAGEndpoints:
    """Тесты для RAG endpoints"""
    
    def test_add_document_endpoint(self, test_client, sample_document_content):
        """Тест добавления документа"""
        with patch('main.process_document_task') as mock_task:
            mock_task.delay = Mock(return_value=Mock(id="test-task-id"))
            
            response = test_client.post(
                "/rag/add-document",
                files={"file": ("test.pdf", sample_document_content, "application/pdf")}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert "task_id" in data
            assert "check_status_url" in data
    
    def test_get_task_status_endpoint(self, test_client):
        """Тест получения статуса задачи"""
        from core.celery_app import celery_app
        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"status": "success", "filename": "test.pdf"}
        mock_result.info = {"status": "success"}
        
        with patch.object(celery_app, 'AsyncResult', return_value=mock_result):
            response = test_client.get("/rag/task/test-task-id")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "result" in data
    
    def test_rag_search_endpoint(self, test_client, rag_service_without_cache, sample_query):
        """Тест поиска в RAG"""
        # Мокаем get_rag_service чтобы избежать инициализации vector_store
        with patch('main.get_rag_service', return_value=rag_service_without_cache):
            rag_service_without_cache.search = AsyncMock(return_value=[
                {
                    'text': 'Test document',
                    'metadata': {'source': 'test.pdf'},
                    'distance': 0.1
                }
            ])
            
            response = test_client.get(
                "/rag/search",
                params={"query": sample_query, "top_k": 5}
            )
            assert response.status_code == 200
            data = response.json()
            assert "query" in data
            assert "results" in data
            assert len(data["results"]) > 0


class TestMCPEndpoints:
    """Тесты для MCP endpoints"""
    
    def test_search_cases_endpoint(self, test_client, mock_law_client, sample_query):
        """Тест поиска дел через MCP"""
        with patch('main.get_law_client', return_value=mock_law_client):
            response = test_client.post(
                "/mcp/law/search-cases",
                params={"query": sample_query, "instance": "3", "limit": 10}
            )
            assert response.status_code == 200
            data = response.json()
            assert "query" in data
            assert "results" in data
    
    def test_get_case_endpoint(self, test_client):
        """Тест получения деталей дела"""
        from core.mcp.law_client import LawMCPClient
        
        async def mock_get_case(case_number=None, doc_id=None):
            return {
                "case_number": "123/2024",
                "title": "Test Case 1",
                "details": "Full case details"
            }
        
        with patch.object(LawMCPClient, 'get_case_details', side_effect=mock_get_case):
            with patch('main.get_law_client') as mock_get:
                mock_law = Mock(spec=LawMCPClient)
                mock_law.get_case_details = mock_get_case
                mock_get.return_value = mock_law
                response = test_client.get("/mcp/law/case/123/2024")
                assert response.status_code == 200
                data = response.json()
                assert "case_number" in data or "title" in data
    
    def test_get_case_not_found(self, test_client):
        """Тест получения несуществующего дела"""
        # Мокаем LawMCPClient.get_case_details напрямую
        from core.mcp.law_client import LawMCPClient
        
        async def mock_get_case_none(case_number=None, doc_id=None):
            return None
        
        with patch.object(LawMCPClient, 'get_case_details', side_effect=mock_get_case_none):
            with patch('main.get_law_client') as mock_get:
                mock_law = Mock(spec=LawMCPClient)
                mock_law.get_case_details = mock_get_case_none
                mock_get.return_value = mock_law
                response = test_client.get("/mcp/law/case/nonexistent")
                assert response.status_code == 404

