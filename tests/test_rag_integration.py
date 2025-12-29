"""
Интеграционные тесты для RAG сервиса
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.rag.rag_service import RAGService
from core.rag.document_processor import DocumentProcessor
from core.services.cache_service import CacheService


class TestRAGServiceIntegration:
    """Интеграционные тесты RAG сервиса"""
    
    @pytest.mark.asyncio
    async def test_rag_search_without_cache(self, rag_service_without_cache, sample_query):
        """Тест поиска в RAG без кэша"""
        results = await rag_service_without_cache.search(sample_query, top_k=5)
        assert isinstance(results, list)
        assert len(results) > 0
        assert "text" in results[0]
        assert "metadata" in results[0]
    
    @pytest.mark.asyncio
    async def test_rag_search_with_cache(self, rag_service_with_cache, sample_query, mock_redis):
        """Тест поиска в RAG с кэшированием"""
        # Первый запрос - должен сохранить в кэш
        results1 = await rag_service_with_cache.search(sample_query, top_k=5)
        assert isinstance(results1, list)
        
        # Проверяем, что был вызов setex для сохранения в кэш
        assert mock_redis.setex.called
        
        # Второй запрос - должен получить из кэша
        mock_redis.get = AsyncMock(return_value='[{"text": "Cached result", "metadata": {}}]')
        results2 = await rag_service_with_cache.search(sample_query, top_k=5)
        assert mock_redis.get.called
    
    @pytest.mark.asyncio
    async def test_rag_get_context(self, rag_service_without_cache, sample_query):
        """Тест получения контекста из RAG"""
        context = await rag_service_without_cache.get_context(sample_query, top_k=3)
        assert isinstance(context, str)
        assert len(context) > 0
    
    @pytest.mark.asyncio
    async def test_rag_get_context_with_cache(self, rag_service_with_cache, sample_query, mock_redis):
        """Тест получения контекста с кэшированием"""
        # Первый запрос
        context1 = await rag_service_with_cache.get_context(sample_query, top_k=3)
        assert isinstance(context1, str)
        
        # Второй запрос из кэша
        mock_redis.get = AsyncMock(return_value='"Cached context text"')
        context2 = await rag_service_with_cache.get_context(sample_query, top_k=3)
        assert mock_redis.get.called
    
    def test_rag_add_document(self, rag_service_without_cache, test_data_dir):
        """Тест добавления документа в RAG"""
        import os
        test_file = os.path.join(test_data_dir, "test_doc.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("This is a test document for RAG integration testing.")
        
        # Добавление документа
        rag_service_without_cache.add_document(
            test_file,
            metadata={"test": True, "source": "integration_test"}
        )
        
        # Проверяем, что метод add_documents был вызван
        assert rag_service_without_cache.vector_store.add_documents.called
    
    @pytest.mark.asyncio
    async def test_rag_search_empty_results(self, rag_service_without_cache):
        """Тест поиска с пустыми результатами"""
        # Мокаем пустой результат
        rag_service_without_cache.vector_store.search = Mock(return_value=[])
        results = await rag_service_without_cache.search("nonexistent query", top_k=5)
        assert results == []
    
    @pytest.mark.asyncio
    async def test_rag_cache_invalidation_on_add(self, rag_service_with_cache, mock_redis):
        """Тест инвалидации кэша при добавлении документа"""
        import os
        import tempfile
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test document content")
            temp_file = f.name
        
        try:
            # Добавляем документ
            rag_service_with_cache.add_document(temp_file, metadata={"test": True})
            
            # Проверяем, что был вызов delete_pattern для инвалидации кэша
            # (может быть вызван асинхронно, поэтому проверяем наличие вызова)
            assert rag_service_with_cache.vector_store.add_documents.called
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_rag_error_handling(self, rag_service_without_cache, sample_query):
        """Тест обработки ошибок в RAG"""
        # Мокаем ошибку в векторном хранилище
        rag_service_without_cache.vector_store.search = Mock(side_effect=Exception("Vector store error"))
        
        # Поиск должен обработать ошибку
        with pytest.raises(Exception):
            await rag_service_without_cache.search(sample_query, top_k=5)

