"""
Тесты для проверки корректной инициализации баз данных и таблиц
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List

from config import settings
from core.services.cache_service import CacheService

# Проверка доступности библиотек
try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class TestQdrantInitialization:
    """Тесты инициализации Qdrant"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_qdrant
    async def test_qdrant_collection_exists(self):
        """Проверка существования коллекции в Qdrant"""
        if not QDRANT_AVAILABLE:
            pytest.fail("qdrant-client не установлен. Установите: pip install qdrant-client")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        from core.rag.vector_store import create_vector_store
        vector_store = create_vector_store()
        
        # Проверка что коллекция существует
        assert hasattr(vector_store, 'client'), "Qdrant клиент должен быть инициализирован"
        assert hasattr(vector_store, 'collection_name'), "Имя коллекции должно быть установлено"
        assert vector_store.collection_name == settings.qdrant_collection_name
        
        # Проверка что коллекция существует в Qdrant
        collections = vector_store.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        assert settings.qdrant_collection_name in collection_names, \
            f"Коллекция '{settings.qdrant_collection_name}' должна существовать в Qdrant"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_qdrant
    async def test_qdrant_collection_configuration(self):
        """Проверка конфигурации коллекции Qdrant"""
        if not QDRANT_AVAILABLE:
            pytest.fail("qdrant-client не установлен. Установите: pip install qdrant-client")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        from core.rag.vector_store import create_vector_store
        from qdrant_client.models import Distance
        
        vector_store = create_vector_store()
        
        # Получение информации о коллекции
        collection_info = vector_store.client.get_collection(
            collection_name=settings.qdrant_collection_name
        )
        
        # Проверка параметров коллекции
        assert collection_info.config is not None, "Конфигурация коллекции должна быть установлена"
        
        # Проверка размерности векторов
        vector_config = collection_info.config.params.vectors
        assert vector_config is not None, "Конфигурация векторов должна быть установлена"
        
        # Проверка что размерность соответствует embedding модели
        expected_dim = vector_store.embedding_dim
        if hasattr(vector_config, 'size'):
            assert vector_config.size == expected_dim, \
                f"Размерность векторов должна быть {expected_dim}, получено {vector_config.size}"
        
        # Проверка расстояния (должно быть COSINE)
        if hasattr(vector_config, 'distance'):
            assert vector_config.distance == Distance.COSINE, \
                f"Расстояние должно быть COSINE, получено {vector_config.distance}"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_qdrant
    async def test_qdrant_connection(self):
        """Проверка подключения к Qdrant"""
        if not QDRANT_AVAILABLE:
            pytest.fail("qdrant-client не установлен. Установите: pip install qdrant-client")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        from core.rag.vector_store import create_vector_store
        vector_store = create_vector_store()
        
        # Проверка что клиент может выполнять запросы
        try:
            collections = vector_store.client.get_collections()
            assert collections is not None, "Должна быть возможность получить список коллекций"
        except Exception as e:
            pytest.fail(f"Не удалось подключиться к Qdrant: {e}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_qdrant
    async def test_qdrant_collection_auto_creation(self):
        """Проверка автоматического создания коллекции при инициализации"""
        if not QDRANT_AVAILABLE:
            pytest.fail("qdrant-client не установлен. Установите: pip install qdrant-client")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        from core.rag.vector_store import QdrantVectorStore
        
        # Создание нового экземпляра должен автоматически создать коллекцию если её нет
        vector_store = QdrantVectorStore(settings.rag_embedding_model)
        
        # Проверка что коллекция существует
        collections = vector_store.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        assert settings.qdrant_collection_name in collection_names, \
            "Коллекция должна быть автоматически создана при инициализации"


class TestChromaDBInitialization:
    """Тесты инициализации ChromaDB"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chromadb_collection_exists(self):
        """Проверка существования коллекции в ChromaDB"""
        if not CHROMADB_AVAILABLE:
            pytest.skip("chromadb не установлен или несовместим с текущей версией pydantic")
        
        if settings.rag_vector_db_type.lower() != "chroma":
            pytest.skip("ChromaDB не используется в конфигурации")
        
        from core.rag.vector_store import ChromaVectorStore
        vector_store = ChromaVectorStore(settings.rag_embedding_model)
        
        # Проверка что коллекция существует
        assert hasattr(vector_store, 'collection'), "Коллекция должна быть инициализирована"
        assert vector_store.collection is not None, "Коллекция не должна быть None"
        
        # Проверка что коллекция существует в ChromaDB
        collections = vector_store.client.list_collections()
        collection_names = [c.name for c in collections]
        
        assert "legal_documents" in collection_names, \
            "Коллекция 'legal_documents' должна существовать в ChromaDB"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chromadb_collection_auto_creation(self):
        """Проверка автоматического создания коллекции при инициализации"""
        if not CHROMADB_AVAILABLE:
            pytest.skip("chromadb не установлен или несовместим с текущей версией pydantic")
        
        if settings.rag_vector_db_type.lower() != "chroma":
            pytest.skip("ChromaDB не используется в конфигурации")
        
        from core.rag.vector_store import ChromaVectorStore
        
        # Создание нового экземпляра должен автоматически создать коллекцию если её нет
        vector_store = ChromaVectorStore(settings.rag_embedding_model)
        
        # Проверка что коллекция существует
        collections = vector_store.client.list_collections()
        collection_names = [c.name for c in collections]
        
        assert "legal_documents" in collection_names, \
            "Коллекция должна быть автоматически создана при инициализации"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chromadb_storage_path(self):
        """Проверка пути хранения ChromaDB"""
        if not CHROMADB_AVAILABLE:
            pytest.skip("chromadb не установлен или несовместим с текущей версией pydantic")
        
        if settings.rag_vector_db_type.lower() != "chroma":
            pytest.skip("ChromaDB не используется в конфигурации")
        
        from core.rag.vector_store import ChromaVectorStore
        import os
        
        vector_store = ChromaVectorStore(settings.rag_embedding_model)
        
        # Проверка что директория для БД создана
        assert os.path.exists(settings.rag_vector_db_path), \
            f"Директория для ChromaDB должна существовать: {settings.rag_vector_db_path}"


class TestRedisInitialization:
    """Тесты инициализации Redis"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_redis
    async def test_redis_connection(self):
        """Проверка подключения к Redis"""
        cache_service = CacheService()
        
        try:
            health = await cache_service.health_check()
            assert health["status"] == "healthy", \
                f"Redis должен быть доступен, получен статус: {health.get('status')}"
        except Exception as e:
            pytest.fail(f"Не удалось подключиться к Redis: {e}")
        finally:
            await cache_service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_redis
    async def test_redis_read_write(self):
        """Проверка записи и чтения в Redis"""
        cache_service = CacheService()
        
        try:
            test_key = "coreml_test_db_init"
            test_value = {"test": "data", "number": 123}
            
            # Запись
            result = await cache_service.set(test_key, test_value, ttl=10)
            assert result is True, "Запись в Redis должна быть успешной"
            
            # Чтение
            cached_value = await cache_service.get(test_key)
            assert cached_value == test_value, \
                f"Прочитанное значение должно совпадать с записанным. Ожидалось: {test_value}, получено: {cached_value}"
            
            # Очистка
            await cache_service.delete(test_key)
            
        except Exception as e:
            pytest.fail(f"Ошибка при работе с Redis: {e}")
        finally:
            await cache_service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_redis
    async def test_redis_health_check(self):
        """Проверка health check Redis"""
        cache_service = CacheService()
        
        try:
            health = await cache_service.health_check()
            
            assert "status" in health, "Health check должен содержать поле 'status'"
            assert health["status"] in ["healthy", "unhealthy"], \
                f"Статус должен быть 'healthy' или 'unhealthy', получено: {health['status']}"
            
            if health["status"] == "healthy":
                assert "connected_clients" in health, \
                    "При здоровом состоянии должен быть 'connected_clients'"
                assert "redis_version" in health, \
                    "При здоровом состоянии должен быть 'redis_version'"
        except Exception as e:
            pytest.fail(f"Ошибка при health check Redis: {e}")
        finally:
            await cache_service.close()


class TestDatabaseInitializationIntegration:
    """Интеграционные тесты инициализации всех баз данных"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_all_databases_initialized(self):
        """Проверка что все необходимые базы данных инициализированы"""
        results = {
            "vector_db": False,
            "redis": False
        }
        
        # Проверка векторной БД
        try:
            from core.rag.vector_store import create_vector_store
            vector_store = create_vector_store()
            
            if settings.rag_vector_db_type.lower() == "qdrant":
                collections = vector_store.client.get_collections().collections
                collection_names = [c.name for c in collections]
                results["vector_db"] = settings.qdrant_collection_name in collection_names
            elif settings.rag_vector_db_type.lower() == "chroma":
                collections = vector_store.client.list_collections()
                collection_names = [c.name for c in collections]
                results["vector_db"] = "legal_documents" in collection_names
        except Exception as e:
            pytest.fail(f"Ошибка при проверке векторной БД: {e}")
        
        # Проверка Redis
        try:
            cache_service = CacheService()
            health = await cache_service.health_check()
            results["redis"] = health["status"] == "healthy"
            await cache_service.close()
        except Exception as e:
            pytest.fail(f"Ошибка при проверке Redis: {e}")
        
        # Проверка результатов
        failed = [name for name, status in results.items() if not status]
        if failed:
            pytest.fail(
                f"Следующие базы данных не инициализированы корректно: {', '.join(failed)}. "
                f"Результаты: {results}"
            )
        
        assert all(results.values()), \
            f"Все базы данных должны быть инициализированы. Результаты: {results}"
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_qdrant
    async def test_vector_store_embedding_dimension(self):
        """Проверка что размерность эмбеддингов корректна"""
        if not QDRANT_AVAILABLE:
            pytest.fail("qdrant-client не установлен. Установите: pip install qdrant-client")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Тест только для Qdrant")
        
        from core.rag.vector_store import create_vector_store
        vector_store = create_vector_store()
        
        # Проверка что размерность определена
        assert hasattr(vector_store, 'embedding_dim'), \
            "Векторное хранилище должно иметь атрибут 'embedding_dim'"
        assert vector_store.embedding_dim > 0, \
            f"Размерность эмбеддингов должна быть больше 0, получено: {vector_store.embedding_dim}"
        
        # Проверка что размерность соответствует конфигурации коллекции
        collection_info = vector_store.client.get_collection(
            collection_name=settings.qdrant_collection_name
        )
        
        vector_config = collection_info.config.params.vectors
        if hasattr(vector_config, 'size'):
            assert vector_config.size == vector_store.embedding_dim, (
                f"Размерность в коллекции ({vector_config.size}) должна совпадать с "
                f"размерностью модели ({vector_store.embedding_dim})"
            )
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vector_store_collection_name_config(self):
        """Проверка что имя коллекции берется из конфигурации"""
        from core.rag.vector_store import create_vector_store
        vector_store = create_vector_store()
        
        if settings.rag_vector_db_type.lower() == "qdrant":
            assert vector_store.collection_name == settings.qdrant_collection_name, (
                f"Имя коллекции должно совпадать с настройкой: "
                f"ожидалось {settings.qdrant_collection_name}, "
                f"получено {vector_store.collection_name}"
            )
        elif settings.rag_vector_db_type.lower() == "chroma":
            assert vector_store.collection.name == "legal_documents", \
                "Имя коллекции ChromaDB должно быть 'legal_documents'"


class TestDatabasePermissions:
    """Тесты прав доступа к базам данных"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_data_directory_permissions(self):
        """Проверка прав на запись в директорию данных"""
        import os
        from pathlib import Path
        
        data_dir = Path("./data")
        
        # Создание директории если её нет
        data_dir.mkdir(exist_ok=True)
        
        # Проверка прав на запись
        try:
            test_file = data_dir / ".test_write_permissions"
            test_file.write_text("test")
            test_file.unlink()
            assert True, "Должны быть права на запись в директорию data"
        except Exception as e:
            pytest.fail(f"Нет прав на запись в директорию data: {e}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_qdrant
    async def test_qdrant_api_access(self):
        """Проверка доступа к Qdrant API"""
        if not QDRANT_AVAILABLE:
            pytest.fail("qdrant-client не установлен. Установите: pip install qdrant-client")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        from core.rag.vector_store import create_vector_store
        vector_store = create_vector_store()
        
        # Попытка выполнить операцию (получение коллекций)
        try:
            collections = vector_store.client.get_collections()
            assert collections is not None, "Должен быть доступ к Qdrant API"
        except Exception as e:
            pytest.fail(f"Нет доступа к Qdrant API: {e}")

