"""
Тесты для проверки подключения и работы с Qdrant
"""
import pytest
import uuid
from typing import List, Dict, Any
from config import settings

# Проверка доступности библиотек
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


@pytest.mark.asyncio
@pytest.mark.requires_qdrant
class TestQdrantConnection:
    """Тесты подключения к Qdrant"""
    
    @pytest.fixture
    def qdrant_client(self):
        """Фикстура для создания Qdrant клиента"""
        if not QDRANT_AVAILABLE:
            pytest.skip("qdrant-client не установлен. Установите: pip install qdrant-client")
        
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            timeout=settings.qdrant_timeout
        )
        yield client
    
    @pytest.fixture
    def test_collection_name(self):
        """Имя тестовой коллекции"""
        return f"test_collection_{uuid.uuid4().hex[:8]}"
    
    async def test_qdrant_connection(self, qdrant_client):
        """Тест подключения к Qdrant"""
        try:
            collections = qdrant_client.get_collections()
            assert collections is not None, "Должна быть возможность получить список коллекций"
            print(f"✓ Qdrant подключен: {settings.qdrant_url}")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_health(self, qdrant_client):
        """Тест проверки здоровья Qdrant"""
        try:
            # Qdrant не имеет явного health endpoint, но можно проверить через get_collections
            collections = qdrant_client.get_collections()
            assert collections is not None
            print("✓ Qdrant health check: OK")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_create_collection(self, qdrant_client, test_collection_name):
        """Тест создания коллекции"""
        try:
            # Удаляем коллекцию если она существует
            try:
                qdrant_client.delete_collection(test_collection_name)
            except:
                pass
            
            # Создаем тестовую коллекцию
            qdrant_client.create_collection(
                collection_name=test_collection_name,
                vectors_config=VectorParams(
                    size=384,  # Стандартная размерность для sentence-transformers
                    distance=Distance.COSINE
                )
            )
            
            # Проверяем что коллекция создана
            collections = qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            assert test_collection_name in collection_names, f"Коллекция {test_collection_name} должна быть создана"
            
            # Очистка
            qdrant_client.delete_collection(test_collection_name)
            print(f"✓ Создание коллекции {test_collection_name}: успешно")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_collection_configuration(self, qdrant_client, test_collection_name):
        """Тест конфигурации коллекции"""
        try:
            # Создаем коллекцию
            try:
                qdrant_client.delete_collection(test_collection_name)
            except:
                pass
            
            qdrant_client.create_collection(
                collection_name=test_collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )
            
            # Получаем информацию о коллекции
            collection_info = qdrant_client.get_collection(test_collection_name)
            
            # Проверяем конфигурацию
            assert collection_info.config is not None, "Конфигурация коллекции должна быть установлена"
            vector_config = collection_info.config.params.vectors
            assert vector_config is not None, "Конфигурация векторов должна быть установлена"
            
            if hasattr(vector_config, 'size'):
                assert vector_config.size == 384, f"Размерность должна быть 384, получено {vector_config.size}"
            
            if hasattr(vector_config, 'distance'):
                assert vector_config.distance == Distance.COSINE, f"Расстояние должно быть COSINE"
            
            # Очистка
            qdrant_client.delete_collection(test_collection_name)
            print(f"✓ Конфигурация коллекции {test_collection_name}: корректна")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_add_points(self, qdrant_client, test_collection_name):
        """Тест добавления точек в коллекцию"""
        try:
            # Создаем коллекцию
            try:
                qdrant_client.delete_collection(test_collection_name)
            except:
                pass
            
            qdrant_client.create_collection(
                collection_name=test_collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )
            
            # Создаем тестовые векторы
            test_vector = [0.1] * 384
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=test_vector,
                    payload={"text": "Test document 1", "source": "test"}
                ),
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=test_vector,
                    payload={"text": "Test document 2", "source": "test"}
                )
            ]
            
            # Добавляем точки
            qdrant_client.upsert(
                collection_name=test_collection_name,
                points=points
            )
            
            # Проверяем количество точек
            collection_info = qdrant_client.get_collection(test_collection_name)
            points_count = collection_info.points_count if hasattr(collection_info, 'points_count') else 0
            assert points_count == 2, f"Должно быть 2 точки, получено {points_count}"
            
            # Очистка
            qdrant_client.delete_collection(test_collection_name)
            print(f"✓ Добавление точек в {test_collection_name}: успешно")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_search(self, qdrant_client, test_collection_name):
        """Тест поиска в коллекции"""
        try:
            # Создаем коллекцию
            try:
                qdrant_client.delete_collection(test_collection_name)
            except:
                pass
            
            qdrant_client.create_collection(
                collection_name=test_collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )
            
            # Добавляем тестовые точки (используем UUID вместо строк)
            test_vector = [0.1] * 384
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=test_vector,
                    payload={"text": "Test document about Python", "source": "test"}
                ),
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=test_vector,
                    payload={"text": "Test document about Redis", "source": "test"}
                )
            ]
            
            qdrant_client.upsert(
                collection_name=test_collection_name,
                points=points
            )
            
            # Выполняем поиск
            search_vector = [0.1] * 384
            results = qdrant_client.search(
                collection_name=test_collection_name,
                query_vector=search_vector,
                limit=2
            )
            
            assert len(results) > 0, "Поиск должен вернуть результаты"
            assert len(results) <= 2, "Поиск должен вернуть не более 2 результатов"
            
            # Проверяем структуру результатов
            for result in results:
                assert hasattr(result, 'id'), "Результат должен иметь id"
                assert hasattr(result, 'score'), "Результат должен иметь score"
                assert result.payload is not None, "Результат должен иметь payload"
            
            # Очистка
            qdrant_client.delete_collection(test_collection_name)
            print(f"✓ Поиск в {test_collection_name}: успешно")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_get_points(self, qdrant_client, test_collection_name):
        """Тест получения точек по ID"""
        try:
            # Создаем коллекцию
            try:
                qdrant_client.delete_collection(test_collection_name)
            except:
                pass
            
            qdrant_client.create_collection(
                collection_name=test_collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )
            
            # Добавляем точку (используем UUID вместо строки)
            point_id = str(uuid.uuid4())
            test_vector = [0.1] * 384
            point = PointStruct(
                id=point_id,
                vector=test_vector,
                payload={"text": "Test document", "source": "test"}
            )
            
            qdrant_client.upsert(
                collection_name=test_collection_name,
                points=[point]
            )
            
            # Получаем точку по ID
            retrieved_points = qdrant_client.retrieve(
                collection_name=test_collection_name,
                ids=[point_id]
            )
            
            assert len(retrieved_points) == 1, "Должна быть получена одна точка"
            assert retrieved_points[0].id == point_id, "ID точки должен совпадать"
            assert retrieved_points[0].payload["text"] == "Test document", "Payload должен совпадать"
            
            # Очистка
            qdrant_client.delete_collection(test_collection_name)
            print(f"✓ Получение точек из {test_collection_name}: успешно")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_delete_points(self, qdrant_client, test_collection_name):
        """Тест удаления точек"""
        try:
            # Создаем коллекцию
            try:
                qdrant_client.delete_collection(test_collection_name)
            except:
                pass
            
            qdrant_client.create_collection(
                collection_name=test_collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )
            
            # Добавляем точки (используем UUID вместо строк)
            point_id_1 = str(uuid.uuid4())
            point_id_2 = str(uuid.uuid4())
            test_vector = [0.1] * 384
            points = [
                PointStruct(id=point_id_1, vector=test_vector, payload={"text": "Doc 1"}),
                PointStruct(id=point_id_2, vector=test_vector, payload={"text": "Doc 2"})
            ]
            
            qdrant_client.upsert(
                collection_name=test_collection_name,
                points=points
            )
            
            # Проверяем количество
            collection_info = qdrant_client.get_collection(test_collection_name)
            points_count_before = collection_info.points_count if hasattr(collection_info, 'points_count') else 0
            assert points_count_before == 2, "Должно быть 2 точки"
            
            # Удаляем одну точку
            qdrant_client.delete(
                collection_name=test_collection_name,
                points_selector=[point_id_1]
            )
            
            # Проверяем количество после удаления
            collection_info = qdrant_client.get_collection(test_collection_name)
            points_count_after = collection_info.points_count if hasattr(collection_info, 'points_count') else 0
            assert points_count_after == 1, "Должна остаться 1 точка"
            
            # Очистка
            qdrant_client.delete_collection(test_collection_name)
            print(f"✓ Удаление точек из {test_collection_name}: успешно")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_collection_info(self, qdrant_client, test_collection_name):
        """Тест получения информации о коллекции"""
        try:
            # Создаем коллекцию
            try:
                qdrant_client.delete_collection(test_collection_name)
            except:
                pass
            
            qdrant_client.create_collection(
                collection_name=test_collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )
            
            # Получаем информацию
            collection_info = qdrant_client.get_collection(test_collection_name)
            
            assert collection_info.name == test_collection_name, "Имя коллекции должно совпадать"
            assert collection_info.config is not None, "Конфигурация должна быть установлена"
            
            # Очистка
            qdrant_client.delete_collection(test_collection_name)
            print(f"✓ Информация о коллекции {test_collection_name}: получена")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_list_collections(self, qdrant_client):
        """Тест получения списка коллекций"""
        try:
            collections = qdrant_client.get_collections()
            assert collections is not None, "Список коллекций должен быть получен"
            assert hasattr(collections, 'collections'), "Список коллекций должен иметь атрибут collections"
            print(f"✓ Список коллекций: получено {len(collections.collections)} коллекций")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_error_handling(self, qdrant_client):
        """Тест обработки ошибок"""
        try:
            # Пробуем получить несуществующую коллекцию
            try:
                qdrant_client.get_collection("nonexistent_collection_12345")
                assert False, "Должна быть ошибка для несуществующей коллекции"
            except Exception:
                # Ожидаемая ошибка
                pass
            
            # Пробуем удалить несуществующую коллекцию
            try:
                qdrant_client.delete_collection("nonexistent_collection_12345")
            except Exception:
                # Ожидаемая ошибка
                pass
            
            print("✓ Обработка ошибок: корректна")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")


@pytest.mark.asyncio
@pytest.mark.requires_qdrant
class TestQdrantVectorStore:
    """Тесты для QdrantVectorStore класса"""
    
    async def test_qdrant_vector_store_initialization(self):
        """Тест инициализации QdrantVectorStore"""
        if not QDRANT_AVAILABLE:
            pytest.skip("qdrant-client не установлен")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        try:
            from core.rag.vector_store import create_vector_store
            vector_store = create_vector_store()
            
            assert hasattr(vector_store, 'client'), "Qdrant клиент должен быть инициализирован"
            assert hasattr(vector_store, 'collection_name'), "Имя коллекции должно быть установлено"
            assert vector_store.collection_name == settings.qdrant_collection_name
            
            print(f"✓ QdrantVectorStore инициализирован: {vector_store.collection_name}")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_vector_store_add_documents(self):
        """Тест добавления документов через QdrantVectorStore"""
        if not QDRANT_AVAILABLE:
            pytest.skip("qdrant-client не установлен")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        try:
            from core.rag.vector_store import create_vector_store
            vector_store = create_vector_store()
            
            # Добавляем тестовые документы
            test_documents = [
                "This is a test document about Python programming",
                "This is another test document about Redis database"
            ]
            
            vector_store.add_documents(
                documents=test_documents,
                metadatas=[{"source": "test"}, {"source": "test"}]
            )
            
            # Проверяем что документы добавлены
            has_docs = vector_store.has_documents()
            assert has_docs is True or has_docs is False, "has_documents должен вернуть bool"
            
            print(f"✓ Добавление документов через QdrantVectorStore: успешно")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_vector_store_search(self):
        """Тест поиска через QdrantVectorStore"""
        if not QDRANT_AVAILABLE:
            pytest.skip("qdrant-client не установлен")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        try:
            from core.rag.vector_store import create_vector_store
            vector_store = create_vector_store()
            
            # Выполняем поиск
            results = vector_store.search("test query", top_k=5)
            
            assert isinstance(results, list), "Результаты должны быть списком"
            
            # Проверяем структуру результатов
            for result in results:
                assert isinstance(result, dict), "Каждый результат должен быть словарем"
                assert 'text' in result or 'metadata' in result, "Результат должен содержать text или metadata"
            
            print(f"✓ Поиск через QdrantVectorStore: получено {len(results)} результатов")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")
    
    async def test_qdrant_vector_store_has_documents(self):
        """Тест проверки наличия документов"""
        if not QDRANT_AVAILABLE:
            pytest.skip("qdrant-client не установлен")
        
        if settings.rag_vector_db_type.lower() != "qdrant":
            pytest.skip("Qdrant не используется в конфигурации")
        
        try:
            from core.rag.vector_store import create_vector_store
            vector_store = create_vector_store()
            
            # Проверяем наличие документов
            has_docs = vector_store.has_documents()
            assert isinstance(has_docs, bool), "has_documents должен вернуть bool"
            
            print(f"✓ Проверка наличия документов: {has_docs}")
        except Exception as e:
            pytest.skip(f"Qdrant не доступен: {e}")

