"""
Сервис RAG для работы с документами с поддержкой кэширования
"""
import os
from typing import List, Dict, Any, Optional
from .document_processor import DocumentProcessor
from .document_classifier import DocumentClassifier
from .vector_store import create_vector_store, DummyVectorStore
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
        # Используем тот же алгоритм, что и в тестах: явно включаем Vision API
        self.processor = DocumentProcessor(use_vision_api=True)
        self.vector_store = create_vector_store()
        self.cache_service = cache_service
    
    def add_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Добавление документа в RAG систему
        
        Args:
            file_path: Путь к файлу
            metadata: Метаданные документа
            
        Returns:
            dict: Результат обработки с информацией о коллекциях и количестве чанков
        """
        # Подготовка метаданных
        if metadata is None:
            metadata = {}
        
        filename = metadata.get('filename') or os.path.basename(file_path)
        metadata['filename'] = filename
        metadata['file_path'] = file_path
        
        # Извлечение текста
        text = self.processor.process_document(file_path)
        if not text:
            logger.warning(f"Could not extract text from {file_path}")
            
            # Сохраняем метаданные в Redis даже если текст не извлечен
            self._save_document_metadata(filename, file_path, metadata, chunks_count=0, status='error', 
                                        message='Could not extract text from document')
            
            return {
                "status": "error",
                "message": "Could not extract text from document",
                "chunks_count": 0,
                "collections": [],
                "filename": filename
            }
        
        # Определение типа документа
        doc_type_info = DocumentClassifier.detect_document_type(text, filename)
        doc_type = doc_type_info.get("type", "unknown")
        doc_confidence = doc_type_info.get("confidence", 0.0)
        
        logger.info(f"Detected document type: {doc_type} (confidence: {doc_confidence:.2f}) for {filename}")
        
        # Разбиение на чанки
        chunks = self.processor.chunk_text(text)
        chunks_count = len(chunks)
        
        # Подготовка метаданных
        if metadata is None:
            metadata = {}
        metadata['source'] = file_path
        metadata['document_type'] = doc_type
        metadata['document_type_confidence'] = doc_confidence
        
        metadatas = [metadata.copy() for _ in chunks]
        
        # Добавление в векторное хранилище
        self.vector_store.add_documents(chunks, metadatas)
        
        # Получение информации о коллекциях
        collections = []
        try:
            if hasattr(self.vector_store, 'collection_name'):
                # Qdrant
                collections.append(self.vector_store.collection_name)
            elif hasattr(self.vector_store, 'collection'):
                # ChromaDB
                if hasattr(self.vector_store.collection, 'name'):
                    collections.append(self.vector_store.collection.name)
                else:
                    collections.append("legal_documents")  # Default для ChromaDB
            else:
                # DummyVectorStore или другие
                collections.append("vector_store")
        except Exception as e:
            logger.warning(f"Could not get collection name: {e}")
            collections.append("unknown")
        
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
        
        logger.info(f"Document {file_path} added to RAG system: {chunks_count} chunks in {collections}")
        
        # Сохраняем метаданные в Redis
        filename = metadata.get('filename') or os.path.basename(file_path)
        self._save_document_metadata(filename, file_path, metadata, chunks_count=chunks_count, 
                                    status='success', collections=collections)
        
        return {
            "status": "success",
            "message": f"Document processed and added to RAG system ({chunks_count} chunks)",
            "chunks_count": chunks_count,
            "collections": collections,
            "file_path": file_path,
            "filename": filename
        }
    
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
        
        # Формирование контекста без технических меток
        context_parts = []
        for result in results:
            text = result.get('text', '').strip()
            if text:
                context_parts.append(text)
        
        context = "\n\n".join(context_parts)
        
        # Сохранение в кэш
        if self.cache_service:
            cache_key = self.cache_service._generate_key("rag:context", query, top_k=top_k)
            await self.cache_service.set(cache_key, context, ttl=3600)  # 1 час
        
        return context
    
    def _save_document_metadata(self, filename: str, file_path: str, metadata: Dict[str, Any], 
                                chunks_count: int = 0, status: str = 'success', 
                                message: str = None, collections: List[str] = None):
        """
        Сохранение метаданных документа в Redis (синхронный метод для использования в Celery tasks)
        
        Args:
            filename: Имя файла
            file_path: Путь к файлу
            metadata: Метаданные документа
            chunks_count: Количество чанков
            status: Статус обработки
            message: Сообщение о статусе
            collections: Список коллекций
        """
        if not self.cache_service:
            return
        
        try:
            from datetime import datetime
            import json
            import redis
            
            doc_metadata = {
                'filename': filename,
                'file_path': file_path,
                'chunks_count': chunks_count,
                'status': status,
                'uploaded_at': datetime.utcnow().isoformat(),
                'collections': collections or [],
                **{k: v for k, v in metadata.items() if k not in ['filename', 'file_path', 'source']}
            }
            
            if message:
                doc_metadata['message'] = message
            
            cache_key = f"document:metadata:{filename}"
            
            # Используем синхронный Redis клиент напрямую
            try:
                # Получаем URL Redis из настроек
                from config import settings
                redis_url = settings.redis_url
                
                # Создаем синхронный клиент
                sync_client = redis.from_url(redis_url, decode_responses=False)
                
                # Сохраняем метаданные как JSON
                value = json.dumps(doc_metadata).encode('utf-8')
                sync_client.setex(cache_key.encode('utf-8'), 2592000, value)  # 30 дней
                sync_client.close()
                
                logger.debug(f"Saved document metadata to Redis: {cache_key}")
            except Exception as redis_error:
                logger.warning(f"Failed to save document metadata using sync Redis client: {redis_error}")
                # Fallback: пытаемся через async (если есть event loop)
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если loop запущен, создаем задачу (но она может не выполниться)
                        asyncio.create_task(self.cache_service.set(cache_key, doc_metadata, ttl=2592000))
                    else:
                        loop.run_until_complete(self.cache_service.set(cache_key, doc_metadata, ttl=2592000))
                except Exception as async_error:
                    logger.warning(f"Failed to save document metadata via async: {async_error}")
        except Exception as e:
            logger.warning(f"Failed to save document metadata to cache: {e}")
    
    async def has_documents(self) -> bool:
        """
        Проверка наличия документов в векторном хранилище
        
        Returns:
            True если есть документы, False иначе
        """
        try:
            # Проверяем наличие документов в хранилище
            if isinstance(self.vector_store, DummyVectorStore):
                return False
            return self.vector_store.has_documents()
        except Exception as e:
            logger.warning(f"Error checking documents: {e}")
            return False
    
    async def list_documents(self) -> List[Dict[str, Any]]:
        """
        Получение списка всех загруженных документов
        Комбинирует данные из векторной БД и из Redis (где хранятся метаданные о всех загруженных файлах)
        
        Returns:
            Список документов с метаданными
        """
        try:
            # Сначала получаем метаданные из Redis (приоритет - там есть все документы, даже без чанков)
            documents_from_cache = []
            if self.cache_service:
                try:
                    # Получаем все ключи с метаданными документов
                    pattern = "document:metadata:*"
                    client = await self.cache_service._get_client()
                    keys = []
                    async for key in client.scan_iter(match=pattern):
                        keys.append(key)
                    
                    logger.debug(f"Found {len(keys)} document metadata keys in Redis")
                    
                    # Получаем метаданные для каждого документа
                    for key in keys:
                        key_str = key.decode() if isinstance(key, bytes) else key
                        metadata = await self.cache_service.get(key_str)
                        if metadata:
                            documents_from_cache.append(metadata)
                except Exception as e:
                    logger.warning(f"Error getting documents from cache: {e}")
            
            # Получаем документы из векторной БД (для документов с чанками)
            documents_from_vector = []
            if not isinstance(self.vector_store, DummyVectorStore):
                try:
                    documents_from_vector = self.vector_store.list_documents()
                    logger.debug(f"Found {len(documents_from_vector)} documents in vector store")
                except Exception as e:
                    logger.warning(f"Error getting documents from vector store: {e}")
            
            # Объединяем документы из векторной БД и из кэша
            # Создаем словарь для быстрого поиска по filename
            documents_map = {}
            
            # Сначала добавляем документы из кэша (приоритет - там есть все документы)
            for doc in documents_from_cache:
                filename = doc.get('filename') or doc.get('file_path')
                if filename:
                    documents_map[filename] = doc.copy()
            
            # Затем обновляем/дополняем документами из векторной БД (для обновления chunks_count)
            for doc in documents_from_vector:
                filename = doc.get('filename') or doc.get('file_path')
                if filename:
                    if filename in documents_map:
                        # Обновляем chunks_count из векторной БД (более точное значение)
                        documents_map[filename]['chunks_count'] = doc.get('chunks_count', 0)
                        # Обновляем другие поля если они есть
                        if doc.get('uploaded_at'):
                            documents_map[filename]['uploaded_at'] = doc.get('uploaded_at')
                    else:
                        # Добавляем новый документ из векторной БД (если его нет в кэше)
                        documents_map[filename] = doc
            
            result = list(documents_map.values())
            logger.debug(f"Total documents after merge: {len(result)}")
            return result
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def delete_document(self, filename: str) -> bool:
        """
        Удаление документа по имени файла
        
        Args:
            filename: Имя файла документа
            
        Returns:
            True если документ удален, False иначе
        """
        try:
            # Удаляем из векторного хранилища
            deleted = self.vector_store.delete_document(filename)
            
            if deleted:
                # Удаляем метаданные из Redis
                if self.cache_service:
                    cache_key = f"document:metadata:{filename}"
                    await self.cache_service.delete(cache_key)
                
                # Инвалидируем кэш RAG
                if self.cache_service:
                    await self.cache_service.delete_pattern("rag:*")
                
                logger.info(f"Document '{filename}' deleted successfully")
            
            return deleted
        except Exception as e:
            logger.error(f"Error deleting document '{filename}': {e}")
            return False
    
    async def get_document_chunks(self, filename: str) -> List[Dict[str, Any]]:
        """
        Получение всех чанков документа по имени файла
        
        Args:
            filename: Имя файла документа
            
        Returns:
            Список чанков документа с текстом и метаданными
        """
        try:
            chunks = self.vector_store.get_document_chunks(filename)
            return chunks
        except Exception as e:
            logger.error(f"Error getting document chunks: {e}")
            return []
    
    async def get_document_preview_image(self, filename: str) -> Optional[bytes]:
        """
        Получение изображения первой страницы документа (превью)
        
        Args:
            filename: Имя файла документа
            
        Returns:
            Байты изображения (PNG) или None если не удалось получить
        """
        try:
            # Получаем путь к файлу из метаданных
            file_path = None
            
            # Пробуем получить из кэша
            if self.cache_service:
                cache_key = f"document:metadata:{filename}"
                metadata = await self.cache_service.get(cache_key)
                if metadata and isinstance(metadata, dict):
                    file_path = metadata.get('file_path')
            
            # Если не нашли в кэше, пробуем найти в списке документов
            if not file_path:
                documents = await self.list_documents()
                for doc in documents:
                    if doc.get('filename') == filename or doc.get('file_path') == filename:
                        file_path = doc.get('file_path')
                        break
            
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File not found for document '{filename}': {file_path}")
                return None
            
            # Проверяем, является ли файл PDF
            if not file_path.lower().endswith('.pdf'):
                logger.debug(f"Document '{filename}' is not a PDF, cannot generate preview")
                return None
            
            # Конвертируем первую страницу PDF в изображение
            images = self.processor._pdf_to_images(file_path)
            if images and len(images) > 0:
                return images[0]  # Возвращаем первую страницу
            
            return None
        except Exception as e:
            logger.error(f"Error getting document preview image: {e}")
            return None