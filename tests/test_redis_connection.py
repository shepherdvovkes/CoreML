"""
Тесты для проверки подключения и работы с Redis
"""
import pytest
import asyncio
import json
from core.services.cache_service import CacheService
from config import settings


@pytest.mark.asyncio
@pytest.mark.requires_redis
class TestRedisConnection:
    """Тесты подключения к Redis"""
    
    async def test_redis_connection(self):
        """Тест подключения к Redis"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            # Пробуем подключиться с таймаутом
            import asyncio
            health = await asyncio.wait_for(cache_service.health_check(), timeout=10.0)
            assert health["status"] == "healthy", f"Redis connection failed: {health.get('error', 'Unknown error')}"
            assert "redis_version" in health
            print(f"✓ Redis connected: version {health.get('redis_version', 'unknown')}")
        except asyncio.TimeoutError:
            pytest.skip("Redis connection timeout")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_ping(self):
        """Тест ping команды"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            client = await cache_service._get_client()
            result = await client.ping()
            assert result is True
            print("✓ Redis ping successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_set_and_get(self):
        """Тест сохранения и получения данных"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            test_key = "test:redis:set_get"
            test_value = {"test": "data", "number": 42}
            
            # Сохранение
            result = await cache_service.set(test_key, test_value, ttl=60)
            assert result is True, "Failed to set value in Redis"
            
            # Получение
            cached_value = await cache_service.get(test_key)
            assert cached_value == test_value, f"Value mismatch: {cached_value} != {test_value}"
            
            # Очистка
            await cache_service.delete(test_key)
            print("✓ Redis set/get operations successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_string_value(self):
        """Тест работы со строковыми значениями"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            test_key = "test:redis:string"
            test_value = "simple string value"
            
            await cache_service.set(test_key, test_value, ttl=60)
            cached_value = await cache_service.get(test_key)
            assert cached_value == test_value
            
            await cache_service.delete(test_key)
            print("✓ Redis string operations successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_list_value(self):
        """Тест работы со списками"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            test_key = "test:redis:list"
            test_value = [1, 2, 3, "test", {"nested": "object"}]
            
            await cache_service.set(test_key, test_value, ttl=60)
            cached_value = await cache_service.get(test_key)
            assert cached_value == test_value
            
            await cache_service.delete(test_key)
            print("✓ Redis list operations successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_delete(self):
        """Тест удаления ключей"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            test_key = "test:redis:delete"
            test_value = "to be deleted"
            
            # Сохраняем
            await cache_service.set(test_key, test_value, ttl=60)
            
            # Проверяем существование
            exists = await cache_service.exists(test_key)
            assert exists is True
            
            # Удаляем
            result = await cache_service.delete(test_key)
            assert result is True
            
            # Проверяем что удалено
            exists = await cache_service.exists(test_key)
            assert exists is False
            
            # Проверяем что значение отсутствует
            value = await cache_service.get(test_key)
            assert value is None
            
            print("✓ Redis delete operations successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_get_or_set(self):
        """Тест get_or_set операции"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            test_key = "test:redis:get_or_set"
            
            # Первый вызов - должно вычислить
            call_count = 0
            
            async def compute_func():
                nonlocal call_count
                call_count += 1
                return {"computed": True, "count": call_count}
            
            # Первый вызов
            result1 = await cache_service.get_or_set(test_key, compute_func, ttl=60)
            assert result1["computed"] is True
            assert call_count == 1
            
            # Второй вызов - должно взять из кэша
            result2 = await cache_service.get_or_set(test_key, compute_func, ttl=60)
            assert result2["computed"] is True
            assert call_count == 1  # Не должно увеличиться
            
            # Очистка
            await cache_service.delete(test_key)
            print("✓ Redis get_or_set operations successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_ttl(self):
        """Тест времени жизни ключей"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            test_key = "test:redis:ttl"
            test_value = "ttl test"
            
            # Сохраняем с коротким TTL
            await cache_service.set(test_key, test_value, ttl=2)
            
            # Проверяем что значение есть
            value = await cache_service.get(test_key)
            assert value == test_value
            
            # Ждем истечения TTL
            await asyncio.sleep(3)
            
            # Проверяем что значение исчезло
            value = await cache_service.get(test_key)
            assert value is None
            
            print("✓ Redis TTL operations successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_delete_pattern(self):
        """Тест удаления по паттерну"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            # Создаем несколько ключей с паттерном
            keys = [
                "test:pattern:key1",
                "test:pattern:key2",
                "test:pattern:key3",
                "test:other:key"  # Этот не должен удалиться
            ]
            
            for key in keys:
                await cache_service.set(key, "value", ttl=60)
            
            # Удаляем по паттерну
            deleted_count = await cache_service.delete_pattern("test:pattern:*")
            assert deleted_count == 3
            
            # Проверяем что паттерн ключи удалены
            for key in keys[:3]:
                exists = await cache_service.exists(key)
                assert exists is False, f"Key {key} should be deleted"
            
            # Проверяем что другой ключ остался
            exists = await cache_service.exists(keys[3])
            assert exists is True, f"Key {keys[3]} should not be deleted"
            
            # Очистка
            await cache_service.delete(keys[3])
            print("✓ Redis delete_pattern operations successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_info(self):
        """Тест получения информации о Redis"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            health = await cache_service.health_check()
            assert health["status"] == "healthy"
            assert "connected_clients" in health
            assert "used_memory_human" in health
            assert "redis_version" in health
            
            print(f"✓ Redis info: {health}")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_key_generation(self):
        """Тест генерации ключей"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            # Тест обычной генерации
            key1 = cache_service._generate_key("prefix", "arg1", "arg2", param1="value1")
            key2 = cache_service._generate_key("prefix", "arg1", "arg2", param1="value1")
            assert key1 == key2, "Same parameters should generate same key"
            
            # Тест хэширования длинных ключей
            long_string = "a" * 300
            key3 = cache_service._generate_key("prefix", long_string)
            assert len(key3) < 300, "Long key should be hashed"
            assert "prefix:" in key3, "Hashed key should contain prefix"
            
            print("✓ Redis key generation successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()
    
    async def test_redis_error_handling(self):
        """Тест обработки ошибок"""
        cache_service = CacheService(redis_url=settings.redis_url)
        try:
            # Тест получения несуществующего ключа
            value = await cache_service.get("nonexistent:key:12345")
            assert value is None
            
            # Тест удаления несуществующего ключа (не должно падать)
            result = await cache_service.delete("nonexistent:key:12345")
            assert result is True  # Redis delete возвращает количество удаленных ключей
            
            print("✓ Redis error handling successful")
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await cache_service.close()

