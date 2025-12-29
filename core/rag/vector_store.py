"""
Векторное хранилище для RAG с поддержкой внешних БД и LangChain embeddings
"""
import os
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from loguru import logger
from config import settings

# LangChain embeddings
HuggingFaceEmbeddings = None
LANGCHAIN_EMBEDDINGS_AVAILABLE = False
try:
    # Пробуем разные пути импорта для разных версий LangChain
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        logger.info("LangChain HuggingFaceEmbeddings imported from langchain_community.embeddings")
        LANGCHAIN_EMBEDDINGS_AVAILABLE = True
    except ImportError:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            logger.info("LangChain HuggingFaceEmbeddings imported from langchain_huggingface")
            LANGCHAIN_EMBEDDINGS_AVAILABLE = True
        except ImportError:
            try:
                from langchain.embeddings import HuggingFaceEmbeddings
                logger.info("LangChain HuggingFaceEmbeddings imported from langchain.embeddings")
                LANGCHAIN_EMBEDDINGS_AVAILABLE = True
            except ImportError as e:
                raise ImportError(f"Could not import HuggingFaceEmbeddings from any known location: {e}")
except ImportError as e:
    LANGCHAIN_EMBEDDINGS_AVAILABLE = False
    HuggingFaceEmbeddings = None
    logger.warning(f"LangChain embeddings not available: {e}. Falling back to SentenceTransformer")

# Fallback на SentenceTransformer
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Импорты для разных БД
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    Filter = None
    FieldCondition = None
    MatchValue = None


class VectorStoreBase(ABC):
    """Базовый класс для векторных хранилищ с поддержкой LangChain embeddings"""
    
    def __init__(self, embedding_model_name: str):
        """
        Инициализация embedding модели
        
        Args:
            embedding_model_name: Имя модели для embeddings (поддерживает SentenceTransformer модели)
        """
        # Используем LangChain embeddings если доступны
        if LANGCHAIN_EMBEDDINGS_AVAILABLE and HuggingFaceEmbeddings is not None:
            try:
                # HuggingFaceEmbeddings поддерживает SentenceTransformer модели
                self.embedding_model = HuggingFaceEmbeddings(
                    model_name=embedding_model_name,
                    model_kwargs={'device': 'cpu'},  # Можно настроить через config
                    encode_kwargs={'normalize_embeddings': False}
                )
                logger.info(f"Using LangChain HuggingFaceEmbeddings with model: {embedding_model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize LangChain embeddings: {e}. Falling back to SentenceTransformer")
                if SENTENCE_TRANSFORMERS_AVAILABLE:
                    # Используем CPU для избежания проблем с MPS в Celery workers
                    import os
                    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
                    self.embedding_model = SentenceTransformer(
                        embedding_model_name,
                        device='cpu'  # Принудительно используем CPU
                    )
                else:
                    raise ImportError("Neither LangChain embeddings nor SentenceTransformer are available")
        elif SENTENCE_TRANSFORMERS_AVAILABLE:
            # Используем CPU для избежания проблем с MPS в Celery workers
            import os
            os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            self.embedding_model = SentenceTransformer(
                embedding_model_name,
                device='cpu'  # Принудительно используем CPU
            )
            logger.info(f"Using SentenceTransformer with model: {embedding_model_name} (device: cpu)")
        else:
            raise ImportError("No embedding library available. Install langchain-community or sentence-transformers")
    
    def _embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Генерация эмбеддингов для списка текстов
        
        Args:
            texts: Список текстов для эмбеддинга
            
        Returns:
            Список эмбеддингов (каждый эмбеддинг - список float)
        """
        if LANGCHAIN_EMBEDDINGS_AVAILABLE and HuggingFaceEmbeddings is not None and isinstance(self.embedding_model, HuggingFaceEmbeddings):
            # Используем LangChain API
            embeddings = self.embedding_model.embed_documents(texts)
            return embeddings
        elif SENTENCE_TRANSFORMERS_AVAILABLE and isinstance(self.embedding_model, SentenceTransformer):
            # Используем SentenceTransformer API
            embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
            return embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings
        else:
            raise RuntimeError("No valid embedding model available")
    
    def _embed_query(self, text: str) -> List[float]:
        """
        Генерация эмбеддинга для одного текста (запроса)
        
        Args:
            text: Текст для эмбеддинга
            
        Returns:
            Эмбеддинг как список float
        """
        if LANGCHAIN_EMBEDDINGS_AVAILABLE and HuggingFaceEmbeddings is not None and isinstance(self.embedding_model, HuggingFaceEmbeddings):
            # Используем LangChain API
            embedding = self.embedding_model.embed_query(text)
            return embedding
        elif SENTENCE_TRANSFORMERS_AVAILABLE and isinstance(self.embedding_model, SentenceTransformer):
            # Используем SentenceTransformer API
            embedding = self.embedding_model.encode([text])[0]
            return embedding.tolist() if hasattr(embedding, 'tolist') else embedding
        else:
            raise RuntimeError("No valid embedding model available")
    
    def _get_embedding_dimension(self) -> int:
        """
        Получение размерности эмбеддингов
        
        Returns:
            Размерность эмбеддингов
        """
        # Тестовый эмбеддинг для определения размерности
        test_embedding = self._embed_query("test")
        return len(test_embedding)
    
    @abstractmethod
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        model_version: Optional[str] = None
    ):
        """Добавление документов в векторное хранилище"""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Поиск релевантных документов"""
        pass
    
    @abstractmethod
    def get_document_chunks(self, filename: str) -> List[Dict[str, Any]]:
        """
        Получение всех чанков документа по имени файла
        
        Args:
            filename: Имя файла документа
            
        Returns:
            Список чанков документа с текстом и метаданными
        """
        pass
    
    @abstractmethod
    def delete_document(self, filename: str) -> bool:
        """
        Удаление документа по имени файла
        
        Args:
            filename: Имя файла документа
            
        Returns:
            True если документ удален, False иначе
        """
        pass
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        Получение списка всех уникальных документов с их метаданными
        
        Returns:
            Список документов с метаданными (filename, file_path, chunks_count и т.д.)
        """
        # Базовая реализация - возвращает пустой список
        # Должна быть переопределена в подклассах
        return []
    
    def has_documents(self) -> bool:
        """
        Проверка наличия документов в хранилище
        
        Returns:
            True если есть документы, False иначе
        """
        # По умолчанию делаем тестовый поиск
        try:
            results = self.search("test", top_k=1)
            return len(results) > 0
        except Exception:
            return False


class QdrantVectorStore(VectorStoreBase):
    """Векторное хранилище на основе Qdrant (внешняя БД)"""
    
    def __init__(self, embedding_model_name: str):
        super().__init__(embedding_model_name)
        
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is not installed. Install it with: pip install qdrant-client")
        
        # Инициализация Qdrant клиента
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            timeout=settings.qdrant_timeout
        )
        
        self.collection_name = settings.qdrant_collection_name
        
        # Получение размерности эмбеддингов
        self.embedding_dim = self._get_embedding_dimension()
        
        # Создание коллекции если её нет
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Using existing Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error initializing Qdrant collection: {e}")
            raise
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        model_version: Optional[str] = None
    ):
        """Добавление документов в Qdrant"""
        if not documents:
            return
        
        # Генерация эмбеддингов через LangChain API
        embeddings = self._embed_documents(documents)
        
        # Подготовка метаданных
        if metadatas is None:
            metadatas = [{}] * len(documents)
        
        # Добавление версионирования в метаданные
        from datetime import datetime
        embedding_model_name = settings.rag_embedding_model
        
        for i, metadata in enumerate(metadatas):
            metadata['embedding_model'] = embedding_model_name
            metadata['embedding_model_version'] = model_version or "1.0.0"
            metadata['indexed_at'] = datetime.utcnow().isoformat()
            if 'migration_history' not in metadata:
                metadata['migration_history'] = []
        
        # Генерация ID
        import uuid
        points = []
        for i, (doc, embedding, metadata) in enumerate(zip(documents, embeddings, metadatas)):
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "text": doc,
                        **metadata
                    }
                )
            )
        
        # Добавление в коллекцию
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        logger.info(f"Added {len(documents)} documents to Qdrant with model version {model_version or '1.0.0'}")
    
    def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Поиск релевантных документов в Qdrant"""
        top_k = top_k or settings.rag_top_k
        
        # Генерация эмбеддинга для запроса через LangChain API
        query_embedding = self._embed_query(query)
        
        # Поиск в коллекции (используем query_points для новых версий qdrant-client)
        try:
            # Пробуем новый API (query_points)
            query_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=top_k
            )
            points = query_result.points if hasattr(query_result, 'points') else []
        except AttributeError:
            # Fallback на старый API (search) для совместимости
            try:
                points = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=top_k
                )
            except Exception as e:
                logger.error(f"Error searching in Qdrant: {e}")
                return []
        
        # Форматирование результатов
        documents = []
        for point in points:
            payload = point.payload if hasattr(point, 'payload') else (point if isinstance(point, dict) else {})
            if not isinstance(payload, dict):
                payload = {}
            
            score = point.score if hasattr(point, 'score') else None
            
            documents.append({
                'text': payload.get('text', ''),
                'metadata': {k: v for k, v in payload.items() if k != 'text'},
                'distance': score
            })
        
        return documents
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """Получение списка всех уникальных документов из Qdrant"""
        try:
            from collections import defaultdict
            
            # Получаем все точки из коллекции
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,  # Максимальное количество для получения
                with_payload=True,
                with_vectors=False
            )
            
            # scroll_result может быть кортежем (points, next_page_offset) или просто списком
            if isinstance(scroll_result, tuple):
                points = scroll_result[0]
            else:
                points = scroll_result
            
            # Группируем по filename или file_path для получения уникальных документов
            documents_map = defaultdict(lambda: {
                'filename': None,
                'file_path': None,
                'chunks_count': 0,
                'uploaded_at': None,
                'metadata': {}
            })
            
            logger.debug(f"Processing {len(points)} points from Qdrant")
            
            for point in points:
                payload = point.payload or {}
                
                # Логируем первые несколько payload для отладки
                if len(documents_map) < 3:
                    logger.debug(f"Sample payload keys: {list(payload.keys())}")
                
                filename = payload.get('filename') or payload.get('file_path') or payload.get('source')
                
                if filename:
                    if documents_map[filename]['filename'] is None:
                        documents_map[filename]['filename'] = filename
                        documents_map[filename]['file_path'] = payload.get('file_path', filename)
                        documents_map[filename]['uploaded_at'] = payload.get('uploaded_at') or payload.get('indexed_at')
                        documents_map[filename]['metadata'] = {k: v for k, v in payload.items() 
                                                              if k not in ['text', 'filename', 'file_path', 'uploaded_at', 'indexed_at', 'source']}
                    documents_map[filename]['chunks_count'] += 1
                else:
                    # Если нет filename, используем source или создаем уникальный ключ
                    source = payload.get('source')
                    if source:
                        filename = os.path.basename(source) if source else f"unknown_{point.id}"
                        if documents_map[filename]['filename'] is None:
                            documents_map[filename]['filename'] = filename
                            documents_map[filename]['file_path'] = source
                            documents_map[filename]['uploaded_at'] = payload.get('uploaded_at') or payload.get('indexed_at')
                            documents_map[filename]['metadata'] = {k: v for k, v in payload.items() 
                                                                  if k not in ['text', 'filename', 'file_path', 'uploaded_at', 'indexed_at', 'source']}
                        documents_map[filename]['chunks_count'] += 1
                    else:
                        logger.warning(f"Point {point.id} has no filename, file_path, or source in payload")
            
            logger.debug(f"Grouped into {len(documents_map)} unique documents")
            
            return list(documents_map.values())
        except Exception as e:
            logger.warning(f"Error listing documents from Qdrant: {e}")
            return []
    
    def get_document_chunks(self, filename: str) -> List[Dict[str, Any]]:
        """Получение всех чанков документа по имени файла из Qdrant"""
        try:
            logger.debug(f"Getting document chunks for filename: '{filename}'")
            points = []
            
            # Пробуем использовать Filter если доступен
            if Filter is not None and FieldCondition is not None and MatchValue is not None:
                # Получаем все точки с фильтром по filename
                try:
                    filter_obj = Filter(
                        must=[
                            FieldCondition(
                                key="filename",
                                match=MatchValue(value=filename)
                            )
                        ]
                    )
                    scroll_result = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=filter_obj,
                        limit=10000,
                        with_payload=True,
                        with_vectors=False
                    )
                    if isinstance(scroll_result, tuple):
                        points = scroll_result[0]
                    else:
                        points = scroll_result
                except Exception as e:
                    logger.debug(f"Error using Filter API: {e}, trying alternative method")
                    points = []
            
            # Если не нашли по filename, пробуем по file_path
            if not points and Filter is not None and FieldCondition is not None and MatchValue is not None:
                try:
                    filter_obj = Filter(
                        must=[
                            FieldCondition(
                                key="file_path",
                                match=MatchValue(value=filename)
                            )
                        ]
                    )
                    scroll_result = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=filter_obj,
                        limit=10000,
                        with_payload=True,
                        with_vectors=False
                    )
                    if isinstance(scroll_result, tuple):
                        points = scroll_result[0]
                    else:
                        points = scroll_result
                except Exception:
                    pass
            
            # Если не нашли, пробуем по source (базовое имя файла)
            if not points and Filter is not None and FieldCondition is not None and MatchValue is not None:
                try:
                    import os
                    basename = os.path.basename(filename)
                    filter_obj = Filter(
                        must=[
                            FieldCondition(
                                key="source",
                                match=MatchValue(value=basename)
                            )
                        ]
                    )
                    scroll_result = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=filter_obj,
                        limit=10000,
                        with_payload=True,
                        with_vectors=False
                    )
                    if isinstance(scroll_result, tuple):
                        points = scroll_result[0]
                    else:
                        points = scroll_result
                except Exception:
                    pass
            
            # Fallback: получаем все точки и фильтруем вручную
            if not points:
                logger.debug(f"Using fallback method: getting all points and filtering manually for filename: {filename}")
                scroll_result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )
                if isinstance(scroll_result, tuple):
                    all_points = scroll_result[0]
                else:
                    all_points = scroll_result
                
                logger.debug(f"Found {len(all_points)} total points in collection")
                
                import os
                basename = os.path.basename(filename)
                logger.debug(f"Searching for filename: '{filename}', basename: '{basename}'")
                
                for point in all_points:
                    payload = point.payload or {}
                    payload_filename = payload.get('filename')
                    payload_file_path = payload.get('file_path')
                    payload_source = payload.get('source')
                    
                    # Логируем первые несколько payload для отладки
                    if len(points) < 3:
                        logger.debug(f"Sample payload - filename: '{payload_filename}', file_path: '{payload_file_path}', source: '{payload_source}'")
                    
                    if (payload_filename == filename or
                        payload_file_path == filename or
                        payload_source == filename or
                        (payload_source and os.path.basename(payload_source) == basename) or
                        (payload_filename and os.path.basename(payload_filename) == basename)):
                        points.append(point)
                
                logger.debug(f"Found {len(points)} chunks matching filename '{filename}'")
            
            # Форматируем результаты
            chunks = []
            for point in points:
                payload = point.payload or {}
                text = payload.get('text', '')
                chunks.append({
                    'text': text,
                    'metadata': {k: v for k, v in payload.items() if k != 'text'},
                    'chunk_id': str(point.id) if hasattr(point, 'id') else None
                })
            
            # Сортируем чанки по порядку (если есть индекс в метаданных)
            chunks.sort(key=lambda x: x['metadata'].get('chunk_index', 0))
            
            total_text_length = sum(len(chunk.get('text', '')) for chunk in chunks)
            logger.debug(f"Returning {len(chunks)} chunks with total text length: {total_text_length} characters")
            
            return chunks
        except Exception as e:
            logger.warning(f"Error getting document chunks from Qdrant: {e}")
            return []
    
    def delete_document(self, filename: str) -> bool:
        """Удаление документа по имени файла из Qdrant"""
        try:
            # Получаем все чанки документа
            chunks = self.get_document_chunks(filename)
            if not chunks:
                logger.warning(f"Document '{filename}' not found for deletion")
                return False
            
            # Собираем ID точек для удаления
            point_ids = []
            for chunk in chunks:
                chunk_id = chunk.get('chunk_id')
                if chunk_id:
                    point_ids.append(chunk_id)
            
            if not point_ids:
                logger.warning(f"No point IDs found for document '{filename}'")
                return False
            
            # Удаляем точки по ID
            try:
                from qdrant_client.models import PointIdsList
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=PointIdsList(points=point_ids)
                )
            except Exception as e:
                # Fallback: пробуем без PointIdsList
                try:
                    self.client.delete(
                        collection_name=self.collection_name,
                        points_selector=point_ids
                    )
                except Exception as e2:
                    logger.error(f"Error deleting points from Qdrant: {e2}")
                    return False
            
            logger.info(f"Deleted document '{filename}' with {len(point_ids)} chunks from Qdrant")
            return True
        except Exception as e:
            logger.error(f"Error deleting document '{filename}' from Qdrant: {e}")
            return False
    
    def has_documents(self) -> bool:
        """Проверка наличия документов в Qdrant"""
        try:
            # Получаем информацию о коллекции
            collection_info = self.client.get_collection(self.collection_name)
            # Проверяем количество точек в коллекции
            points_count = collection_info.points_count if hasattr(collection_info, 'points_count') else 0
            return points_count > 0
        except Exception as e:
            logger.warning(f"Error checking documents in Qdrant: {e}")
            return False


class ChromaVectorStore(VectorStoreBase):
    """Векторное хранилище на основе ChromaDB (локальная БД, fallback)"""
    
    def __init__(self, embedding_model_name: str):
        super().__init__(embedding_model_name)
        
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb is not installed. Install it with: pip install chromadb")
        
        # Создаем директорию для БД если её нет
        os.makedirs(settings.rag_vector_db_path, exist_ok=True)
        
        # Инициализация ChromaDB
        self.client = chromadb.PersistentClient(
            path=settings.rag_vector_db_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Коллекция для документов
        self.collection = self.client.get_or_create_collection(
            name="legal_documents",
            metadata={"description": "Юридические документы, справки, договоры"}
        )
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        model_version: Optional[str] = None
    ):
        """Добавление документов в ChromaDB"""
        if not documents:
            return
        
        # Генерация эмбеддингов через LangChain API
        embeddings = self._embed_documents(documents)
        
        # Подготовка метаданных
        if metadatas is None:
            metadatas = [{}] * len(documents)
        
        # Добавление версионирования в метаданные
        from datetime import datetime
        embedding_model_name = settings.rag_embedding_model
        
        for i, metadata in enumerate(metadatas):
            metadata['embedding_model'] = embedding_model_name
            metadata['embedding_model_version'] = model_version or "1.0.0"
            metadata['indexed_at'] = datetime.utcnow().isoformat()
            if 'migration_history' not in metadata:
                metadata['migration_history'] = []
        
        # Генерация ID
        ids = [f"doc_{i}_{hash(doc[:50])}" for i, doc in enumerate(documents)]
        
        # Добавление в коллекцию
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(documents)} documents to ChromaDB with model version {model_version or '1.0.0'}")
    
    def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Поиск релевантных документов в ChromaDB"""
        top_k = top_k or settings.rag_top_k
        
        # Генерация эмбеддинга для запроса через LangChain API
        query_embedding = self._embed_query(query)
        
        # Поиск в коллекции
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Форматирование результатов
        documents = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                documents.append({
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else None
                })
        
        return documents
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """Получение списка всех уникальных документов из ChromaDB"""
        try:
            from collections import defaultdict
            
            # Получаем все документы из коллекции
            results = self.collection.get(
                include=['metadatas', 'documents']
            )
            
            # Группируем по filename или file_path для получения уникальных документов
            documents_map = defaultdict(lambda: {
                'filename': None,
                'file_path': None,
                'chunks_count': 0,
                'uploaded_at': None,
                'metadata': {}
            })
            
            metadatas = results.get('metadatas', [])
            for i, metadata in enumerate(metadatas):
                filename = metadata.get('filename') or metadata.get('file_path')
                
                if filename:
                    if documents_map[filename]['filename'] is None:
                        documents_map[filename]['filename'] = filename
                        documents_map[filename]['file_path'] = metadata.get('file_path', filename)
                        documents_map[filename]['uploaded_at'] = metadata.get('uploaded_at') or metadata.get('indexed_at')
                        documents_map[filename]['metadata'] = {k: v for k, v in metadata.items() 
                                                              if k not in ['filename', 'file_path', 'uploaded_at', 'indexed_at']}
                    documents_map[filename]['chunks_count'] += 1
            
            return list(documents_map.values())
        except Exception as e:
            logger.warning(f"Error listing documents from ChromaDB: {e}")
            return []
    
    def get_document_chunks(self, filename: str) -> List[Dict[str, Any]]:
        """Получение всех чанков документа по имени файла из ChromaDB"""
        try:
            # Получаем все документы с фильтром по filename
            results = self.collection.get(
                where={"filename": filename},
                include=['metadatas', 'documents']
            )
            
            # Если не нашли по filename, пробуем по file_path
            if not results['documents']:
                results = self.collection.get(
                    where={"file_path": filename},
                    include=['metadatas', 'documents']
                )
            
            # Если не нашли, пробуем по source (базовое имя файла)
            if not results['documents']:
                import os
                basename = os.path.basename(filename)
                all_results = self.collection.get(
                    include=['metadatas', 'documents']
                )
                # Фильтруем вручную
                filtered_docs = []
                filtered_metas = []
                for i, meta in enumerate(all_results.get('metadatas', [])):
                    if (meta.get('filename') == basename or 
                        meta.get('file_path') == filename or
                        meta.get('source') == filename or
                        (meta.get('source') and os.path.basename(meta.get('source')) == basename)):
                        filtered_docs.append(all_results['documents'][i])
                        filtered_metas.append(meta)
                results = {
                    'documents': filtered_docs,
                    'metadatas': filtered_metas
                }
            
            # Форматируем результаты
            chunks = []
            documents = results.get('documents', [])
            metadatas = results.get('metadatas', [])
            
            for i, doc in enumerate(documents):
                metadata = metadatas[i] if i < len(metadatas) else {}
                chunks.append({
                    'text': doc,
                    'metadata': metadata,
                    'chunk_id': results.get('ids', [])[i] if i < len(results.get('ids', [])) else None
                })
            
            # Сортируем чанки по порядку (если есть индекс в метаданных)
            chunks.sort(key=lambda x: x['metadata'].get('chunk_index', 0))
            
            return chunks
        except Exception as e:
            logger.warning(f"Error getting document chunks from ChromaDB: {e}")
            return []
    
    def delete_document(self, filename: str) -> bool:
        """Удаление документа по имени файла из ChromaDB"""
        try:
            # Получаем все чанки документа
            chunks = self.get_document_chunks(filename)
            if not chunks:
                logger.warning(f"Document '{filename}' not found for deletion")
                return False
            
            # Собираем ID для удаления
            ids_to_delete = []
            for chunk in chunks:
                chunk_id = chunk.get('chunk_id')
                if chunk_id:
                    ids_to_delete.append(chunk_id)
            
            if not ids_to_delete:
                logger.warning(f"No IDs found for document '{filename}'")
                return False
            
            # Удаляем из коллекции
            self.collection.delete(ids=ids_to_delete)
            
            logger.info(f"Deleted document '{filename}' with {len(ids_to_delete)} chunks from ChromaDB")
            return True
        except Exception as e:
            logger.error(f"Error deleting document '{filename}' from ChromaDB: {e}")
            return False
    
    def has_documents(self) -> bool:
        """Проверка наличия документов в ChromaDB"""
        try:
            # Получаем количество документов в коллекции
            count = self.collection.count()
            return count > 0
        except Exception as e:
            logger.warning(f"Error checking documents in ChromaDB: {e}")
            return False


class DummyVectorStore(VectorStoreBase):
    """Заглушка векторного хранилища, когда ни Qdrant, ни ChromaDB недоступны"""
    
    def __init__(self, embedding_model_name: str):
        super().__init__(embedding_model_name)
        logger.warning("Using DummyVectorStore - vector search will return empty results")
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        model_version: Optional[str] = None
    ):
        """Заглушка - документы не сохраняются"""
        logger.warning(f"DummyVectorStore: {len(documents)} documents not saved (vector store unavailable)")
    
    def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Заглушка - возвращает пустой список"""
        logger.warning(f"DummyVectorStore: search for '{query[:50]}...' returned empty results")
        return []
    
    def get_document_chunks(self, filename: str) -> List[Dict[str, Any]]:
        """Заглушка - возвращает пустой список"""
        logger.warning(f"DummyVectorStore: get_document_chunks for '{filename}' returned empty results")
        return []
    
    def delete_document(self, filename: str) -> bool:
        """Заглушка - возвращает False"""
        logger.warning(f"DummyVectorStore: delete_document for '{filename}' - no documents to delete")
        return False
    
    def has_documents(self) -> bool:
        """DummyVectorStore всегда пустой"""
        return False


def create_vector_store() -> VectorStoreBase:
    """
    Фабрика для создания векторного хранилища
    
    Returns:
        Экземпляр векторного хранилища
    """
    db_type = settings.rag_vector_db_type.lower()
    
    if db_type == "qdrant":
        if QDRANT_AVAILABLE:
            try:
                return QdrantVectorStore(settings.rag_embedding_model)
            except Exception as e:
                logger.warning(f"Failed to initialize Qdrant, falling back to ChromaDB: {e}")
                if CHROMADB_AVAILABLE:
                    try:
                        return ChromaVectorStore(settings.rag_embedding_model)
                    except Exception as chroma_error:
                        logger.error(f"Failed to initialize ChromaDB: {chroma_error}")
                        logger.warning("Falling back to DummyVectorStore - vector search will be disabled")
                        return DummyVectorStore(settings.rag_embedding_model)
                else:
                    logger.warning("ChromaDB not available, using DummyVectorStore")
                    return DummyVectorStore(settings.rag_embedding_model)
        else:
            logger.warning("Qdrant not available, falling back to ChromaDB")
            if CHROMADB_AVAILABLE:
                try:
                    return ChromaVectorStore(settings.rag_embedding_model)
                except Exception as chroma_error:
                    logger.error(f"Failed to initialize ChromaDB: {chroma_error}")
                    logger.warning("Falling back to DummyVectorStore - vector search will be disabled")
                    return DummyVectorStore(settings.rag_embedding_model)
            else:
                logger.warning("ChromaDB not available, using DummyVectorStore")
                return DummyVectorStore(settings.rag_embedding_model)
    
    elif db_type == "chroma":
        if CHROMADB_AVAILABLE:
            try:
                return ChromaVectorStore(settings.rag_embedding_model)
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}")
                logger.warning("Falling back to DummyVectorStore - vector search will be disabled")
                return DummyVectorStore(settings.rag_embedding_model)
        else:
            logger.warning("ChromaDB not available, using DummyVectorStore")
            return DummyVectorStore(settings.rag_embedding_model)
    
    else:
        raise ValueError(f"Unknown vector DB type: {db_type}. Supported: qdrant, chroma")


# Для обратной совместимости
class VectorStore:
    """Обертка для обратной совместимости"""
    
    def __init__(self):
        self._store = create_vector_store()
        # Делегируем embedding_model для обратной совместимости
        self.embedding_model = self._store.embedding_model
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        model_version: Optional[str] = None
    ):
        return self._store.add_documents(documents, metadatas, model_version)
    
    def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        return self._store.search(query, top_k)
    
    def delete_collection(self):
        """Удаление коллекции (только для ChromaDB)"""
        if isinstance(self._store, ChromaVectorStore):
            self._store.client.delete_collection(name="legal_documents")
            logger.info("Vector store collection deleted")
        else:
            logger.warning("delete_collection is only supported for ChromaDB")
