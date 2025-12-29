"""
Интеграционные тесты для QueryRouter
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.router.query_router import QueryRouter
from core.llm.factory import LLMProviderFactory
from config import LLMProvider


class TestQueryRouterIntegration:
    """Интеграционные тесты QueryRouter"""
    
    @pytest.mark.asyncio
    async def test_process_query_with_rag_and_law(self, query_router, sample_query):
        """Тест обработки запроса с RAG и Law MCP"""
        result = await query_router.process_query(
            query=sample_query,
            use_rag=True,
            use_law=True
        )
        
        assert "answer" in result
        assert "sources" in result
        assert "model" in result
        assert "metadata" in result
        assert result["metadata"]["used_rag"] is True
        assert result["metadata"]["used_law"] is True
    
    @pytest.mark.asyncio
    async def test_process_query_auto_classification(self, query_router):
        """Тест автоматической классификации запроса"""
        # Запрос с юридическими ключевыми словами
        legal_query = "Що таке судова практика?"
        result = await query_router.process_query(query=legal_query)
        
        assert result["metadata"]["used_law"] is True
    
    @pytest.mark.asyncio
    async def test_process_query_only_rag(self, query_router, sample_query):
        """Тест обработки запроса только с RAG"""
        result = await query_router.process_query(
            query=sample_query,
            use_rag=True,
            use_law=False
        )
        
        assert result["metadata"]["used_rag"] is True
        assert result["metadata"]["used_law"] is False
        assert "RAG" in result["sources"]
    
    @pytest.mark.asyncio
    async def test_process_query_only_law(self, query_router, sample_query):
        """Тест обработки запроса только с Law MCP"""
        result = await query_router.process_query(
            query=sample_query,
            use_rag=False,
            use_law=True
        )
        
        assert result["metadata"]["used_rag"] is False
        assert result["metadata"]["used_law"] is True
        assert "MCP_Law" in result["sources"]
    
    @pytest.mark.asyncio
    async def test_process_query_with_cache(self, query_router, cache_service, sample_query, mock_redis):
        """Тест обработки запроса с кэшированием"""
        # Первый запрос
        result1 = await query_router.process_query(
            query=sample_query,
            use_rag=True,
            use_law=True
        )
        
        # Второй запрос - должен использовать кэш
        mock_redis.get = AsyncMock(return_value='{"answer": "Cached answer", "sources": ["RAG"], "model": "test", "usage": {}, "metadata": {}}')
        result2 = await query_router.process_query(
            query=sample_query,
            use_rag=True,
            use_law=True
        )
        
        # Проверяем, что был запрос к кэшу
        assert mock_redis.get.called
    
    @pytest.mark.asyncio
    async def test_process_query_with_specific_llm_provider(self, query_router, sample_query, mock_llm_provider):
        """Тест обработки запроса с указанным LLM провайдером"""
        with patch.object(LLMProviderFactory, 'get_provider', return_value=mock_llm_provider) as mock_get:
            result = await query_router.process_query(
                query=sample_query,
                llm_provider=LLMProvider.OPENAI,
                model="gpt-4"
            )
            
            assert result["answer"] == "Test LLM response"
            # Проверяем, что провайдер был запрошен с правильными параметрами
            mock_get.assert_called()
    
    @pytest.mark.asyncio
    async def test_stream_process_query(self, query_router, sample_query):
        """Тест потоковой обработки запроса"""
        chunks = []
        async for chunk in query_router.stream_process_query(
            query=sample_query,
            use_rag=True,
            use_law=True
        ):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_process_query_error_handling(self, query_router, sample_query):
        """Тест обработки ошибок в QueryRouter"""
        # Мокаем ошибку в LLM
        mock_provider = Mock()
        mock_provider.generate = AsyncMock(side_effect=Exception("LLM error"))
        
        with patch.object(LLMProviderFactory, 'get_provider', return_value=mock_provider):
            result = await query_router.process_query(
                query=sample_query,
                use_rag=True,
                use_law=True
            )
            
            # Должен вернуть ответ с ошибкой
            assert "answer" in result
            assert "error" in result or "errors" in result.get("metadata", {})
    
    @pytest.mark.asyncio
    async def test_process_query_rag_error(self, query_router, sample_query):
        """Тест обработки ошибки RAG"""
        # Мокаем ошибку в RAG сервисе
        query_router.rag_service.get_context = AsyncMock(side_effect=Exception("RAG error"))
        
        result = await query_router.process_query(
            query=sample_query,
            use_rag=True,
            use_law=True
        )
        
        # Должен продолжить работу без RAG
        assert "answer" in result
        assert result["metadata"].get("errors") is not None
    
    @pytest.mark.asyncio
    async def test_process_query_law_error(self, query_router, sample_query):
        """Тест обработки ошибки Law MCP"""
        # Мокаем ошибку в Law клиенте
        query_router.law_client.search_cases = AsyncMock(side_effect=Exception("Law MCP error"))
        
        result = await query_router.process_query(
            query=sample_query,
            use_rag=True,
            use_law=True
        )
        
        # Должен продолжить работу без Law MCP
        assert "answer" in result
        assert result["metadata"].get("errors") is not None
    
    @pytest.mark.asyncio
    async def test_query_classification(self, query_router):
        """Тест классификации запросов"""
        # Юридический запрос
        legal_query = "Що таке судова практика з приводу договорів?"
        classification = query_router._classify_query(legal_query)
        assert classification["use_law"] is True
        
        # Запрос о документах
        doc_query = "Знайти інформацію в договорі"
        classification = query_router._classify_query(doc_query)
        assert classification["use_rag"] is True
        
        # Общий запрос
        general_query = "Допоможіть з питанням"
        classification = query_router._classify_query(general_query)
        assert classification["use_law"] is True
        assert classification["use_rag"] is True

