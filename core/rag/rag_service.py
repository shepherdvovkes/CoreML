"""
Сервис RAG для работы с документами с поддержкой кэширования
"""
from typing import List, Dict, Any, Optional
from .document_processor import DocumentProcessor
from .vector_store import create_vector_store
from core.services.cache_service import CacheService
from core.resilience import resilient_rag
from loguru import logger


class RAGService:
    """Сервис для работы с RAG с кэшированием"""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Инициализация RAG сервиса
        
        Args:
            cache_service: Сервис кэширования (опционально)
        """
        self.processor = DocumentProcessor()
        self.vector_store = create_vector_store()
        self.cache_service = cache_service
    
    def add_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Добавление документа в RAG систему
        
        Args:
            file_path: Путь к файлу
            metadata: Метаданные документа
        """
        # Извлечение текста
        text = self.processor.process_document(file_path)
        if not text:
            logger.warning(f"Could not extract text from {file_path}")
            return
        
        # Разбиение на чанки
        chunks = self.processor.chunk_text(text)
        
        # Подготовка метаданных
        if metadata is None:
            metadata = {}
        metadata['source'] = file_path
        
        metadatas = [metadata.copy() for _ in chunks]
        
        # Добавление в векторное хранилище
        self.vector_store.add_documents(chunks, metadatas)
        
        # Инвалидация кэша для этого источника (async, но вызывается из sync метода)
        if self.cache_service:
            import asyncio
            try:
                # Проверяем, есть ли уже event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если loop уже запущен, создаем задачу
                        asyncio.create_task(self.cache_service.delete_pattern("rag:*"))
                    else:
                        # Если loop не запущен, запускаем
                        loop.run_until_complete(self.cache_service.delete_pattern("rag:*"))
                except RuntimeError:
                    # Нет event loop, создаем новый
                    asyncio.run(self.cache_service.delete_pattern("rag:*"))
            except Exception as e:
                logger.warning(f"Failed to invalidate cache: {e}")
        
        logger.info(f"Document {file_path} added to RAG system")
    
    @resilient_rag(name="rag_search")
    async def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов с кэшированием
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            
        Returns:
            Список релевантных документов
        """
        top_k = top_k or 5
        
        # Попытка получить из кэша
        if self.cache_service:
            cache_key = self.cache_service._generate_key("rag:search", query, top_k=top_k)
            cached_result = await self.cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"RAG search cache hit for query: {query[:50]}...")
                return cached_result
        
        # Поиск в векторном хранилище
        results = self.vector_store.search(query, top_k)
        
        # Сохранение в кэш
        if self.cache_service:
            cache_key = self.cache_service._generate_key("rag:search", query, top_k=top_k)
            await self.cache_service.set(cache_key, results, ttl=3600)  # 1 час
        
        return results
    
    @resilient_rag(name="rag_get_context")
    async def get_context(self, query: str, top_k: int = None) -> str:
        """
        Получение контекста для запроса с кэшированием
        
        Args:
            query: Поисковый запрос
            top_k: Количество документов для контекста
            
        Returns:
            Контекст в виде текста
        """
        top_k = top_k or 5
        
        # Попытка получить из кэша
        if self.cache_service:
            cache_key = self.cache_service._generate_key("rag:context", query, top_k=top_k)
            cached_context = await self.cache_service.get(cache_key)
            if cached_context is not None:
                logger.debug(f"RAG context cache hit for query: {query[:50]}...")
                return cached_context
        
        # Получение результатов поиска
        results = await self.search(query, top_k)
        
        # Формирование контекста
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Документ {i}]\n{result['text']}\n")
        
        context = "\n".join(context_parts)
        
        # Сохранение в кэш
        if self.cache_service:
            cache_key = self.cache_service._generate_key("rag:context", query, top_k=top_k)
            await self.cache_service.set(cache_key, context, ttl=3600)  # 1 час
        
        return context
