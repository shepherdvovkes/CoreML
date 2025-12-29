"""
Интеграционные тесты для сервиса кэширования
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from core.services.cache_service import CacheService


class TestCacheServiceIntegration:
    """Интеграционные тесты сервиса кэширования"""
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache_service, mock_redis):
        """Тест сохранения и получения из кэша"""
        test_key = "test:key"
        test_value = {"data": "test", "number": 123}
        
        # Сохранение
        result = await cache_service.set(test_key, test_value, ttl=60)
        assert result is True
        assert mock_redis.setex.called
        
        # Получение
        mock_redis.get = AsyncMock(return_value=json.dumps(test_value))
        cached_value = await cache_service.get(test_key)
        assert cached_value == test_value
    
    @pytest.mark.asyncio
    async def test_cache_get_nonexistent_key(self, cache_service, mock_redis):
        """Тест получения несуществующего ключа"""
        mock_redis.get = AsyncMock(return_value=None)
        value = await cache_service.get("nonexistent:key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_service, mock_redis):
        """Тест удаления ключа"""
        result = await cache_service.delete("test:key")
        assert result is True
        assert mock_redis.delete.called
    
    @pytest.mark.asyncio
    async def test_cache_delete_pattern(self, cache_service, mock_redis):
        """Тест удаления по паттерну"""
        # scan_iter уже настроен в фикстуре как async generator
        mock_redis.delete = AsyncMock(return_value=3)
        
        deleted_count = await cache_service.delete_pattern("rag:*")
        assert deleted_count == 3
        assert mock_redis.delete.called
    
    @pytest.mark.asyncio
    async def test_cache_get_or_set(self, cache_service, mock_redis):
        """Тест get_or_set - получение из кэша"""
        test_value = {"cached": "data"}
        mock_redis.get = AsyncMock(return_value=json.dumps(test_value))
        
        async def compute_func():
            return {"computed": "data"}
        
        result = await cache_service.get_or_set("test:key", compute_func, ttl=60)
        assert result == test_value
        # compute_func не должна быть вызвана
        assert not hasattr(compute_func, '_called')
    
    @pytest.mark.asyncio
    async def test_cache_get_or_set_compute(self, cache_service, mock_redis):
        """Тест get_or_set - вычисление и сохранение"""
        mock_redis.get = AsyncMock(return_value=None)
        
        async def compute_func():
            return {"computed": "data"}
        
        result = await cache_service.get_or_set("test:key", compute_func, ttl=60)
        assert result == {"computed": "data"}
        # Должно быть сохранено в кэш
        assert mock_redis.setex.called
    
    @pytest.mark.asyncio
    async def test_cache_exists(self, cache_service, mock_redis):
        """Тест проверки существования ключа"""
        mock_redis.exists = AsyncMock(return_value=1)
        exists = await cache_service.exists("test:key")
        assert exists is True
        
        mock_redis.exists = AsyncMock(return_value=0)
        exists = await cache_service.exists("nonexistent:key")
        assert exists is False
    
    @pytest.mark.asyncio
    async def test_cache_health_check(self, cache_service, mock_redis):
        """Тест проверки здоровья кэша"""
        health = await cache_service.health_check()
        assert health["status"] == "healthy"
        assert "connected_clients" in health
        assert "redis_version" in health
    
    @pytest.mark.asyncio
    async def test_cache_health_check_error(self, cache_service, mock_redis):
        """Тест проверки здоровья при ошибке"""
        mock_redis.info = AsyncMock(side_effect=Exception("Connection error"))
        
        health = await cache_service.health_check()
        assert health["status"] == "unhealthy"
        assert "error" in health
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache_service):
        """Тест генерации ключей кэша"""
        key1 = cache_service._generate_key("prefix", "arg1", "arg2", param1="value1")
        key2 = cache_service._generate_key("prefix", "arg1", "arg2", param1="value1")
        
        # Ключи должны быть одинаковыми
        assert key1 == key2
        
        # Разные параметры - разные ключи
        key3 = cache_service._generate_key("prefix", "arg1", "arg2", param1="value2")
        assert key1 != key3
    
    @pytest.mark.asyncio
    async def test_cache_long_key_hashing(self, cache_service):
        """Тест хэширования длинных ключей"""
        long_string = "a" * 300
        key = cache_service._generate_key("prefix", long_string)
        
        # Длинный ключ должен быть хэширован
        assert len(key) < 300
        assert "prefix:" in key
    
    @pytest.mark.asyncio
    async def test_cache_string_value(self, cache_service, mock_redis):
        """Тест сохранения строкового значения"""
        await cache_service.set("test:str", "simple string", ttl=60)
        assert mock_redis.setex.called
        
        mock_redis.get = AsyncMock(return_value="simple string")
        value = await cache_service.get("test:str")
        assert value == "simple string"
    
    @pytest.mark.asyncio
    async def test_cache_list_value(self, cache_service, mock_redis):
        """Тест сохранения списка"""
        test_list = [1, 2, 3, "test"]
        await cache_service.set("test:list", test_list, ttl=60)
        
        mock_redis.get = AsyncMock(return_value=json.dumps(test_list))
        value = await cache_service.get("test:list")
        assert value == test_list
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_service, mock_redis):
        """Тест обработки ошибок кэша"""
        # Мокаем ошибку при получении
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
        value = await cache_service.get("test:key")
        assert value is None
        
        # Мокаем ошибку при сохранении
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        result = await cache_service.set("test:key", "value", ttl=60)
        assert result is False

