"""
Векторное хранилище для RAG с поддержкой внешних БД и LangChain embeddings
"""
import os
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from loguru import logger
from config import settings

# LangChain embeddings
try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    LANGCHAIN_EMBEDDINGS_AVAILABLE = True
except ImportError:
    LANGCHAIN_EMBEDDINGS_AVAILABLE = False
    logger.warning("LangChain embeddings not available, falling back to SentenceTransformer")

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
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


class VectorStoreBase(ABC):
    """Базовый класс для векторных хранилищ с поддержкой LangChain embeddings"""
    
    def __init__(self, embedding_model_name: str):
        """
        Инициализация embedding модели
        
        Args:
            embedding_model_name: Имя модели для embeddings (поддерживает SentenceTransformer модели)
        """
        # Используем LangChain embeddings если доступны
        if LANGCHAIN_EMBEDDINGS_AVAILABLE:
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
                    self.embedding_model = SentenceTransformer(embedding_model_name)
                else:
                    raise ImportError("Neither LangChain embeddings nor SentenceTransformer are available")
        elif SENTENCE_TRANSFORMERS_AVAILABLE:
            self.embedding_model = SentenceTransformer(embedding_model_name)
            logger.info(f"Using SentenceTransformer with model: {embedding_model_name}")
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
        if LANGCHAIN_EMBEDDINGS_AVAILABLE and isinstance(self.embedding_model, HuggingFaceEmbeddings):
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
        if LANGCHAIN_EMBEDDINGS_AVAILABLE and isinstance(self.embedding_model, HuggingFaceEmbeddings):
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
        
        # Поиск в коллекции
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k
        )
        
        # Форматирование результатов
        documents = []
        for result in results:
            payload = result.payload or {}
            documents.append({
                'text': payload.get('text', ''),
                'metadata': {k: v for k, v in payload.items() if k != 'text'},
                'distance': result.score if hasattr(result, 'score') else None
            })
        
        return documents


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
                    return ChromaVectorStore(settings.rag_embedding_model)
                raise
        else:
            logger.warning("Qdrant not available, falling back to ChromaDB")
            if CHROMADB_AVAILABLE:
                return ChromaVectorStore(settings.rag_embedding_model)
            raise ImportError("Neither Qdrant nor ChromaDB are available")
    
    elif db_type == "chroma":
        if CHROMADB_AVAILABLE:
            return ChromaVectorStore(settings.rag_embedding_model)
        raise ImportError("ChromaDB is not installed")
    
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
