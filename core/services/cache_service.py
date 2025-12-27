"""
Сервис кэширования с использованием Redis
"""
import json
import hashlib
from typing import Any, Optional, Dict
import redis.asyncio as redis
from loguru import logger
from config import settings


class CacheService:
    """Сервис для кэширования данных в Redis"""
    
    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = None):
        """
        Инициализация сервиса кэширования
        
        Args:
            redis_url: URL подключения к Redis
            default_ttl: Время жизни кэша по умолчанию (в секундах)
        """
        self.redis_url = redis_url or settings.redis_url
        self.default_ttl = default_ttl or settings.redis_cache_ttl
        self._client: Optional[redis.Redis] = None
    
    async def _get_client(self) -> redis.Redis:
        """Получение или создание Redis клиента"""
        if self._client is None:
            try:
                self._client = await redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Проверка подключения
                await self._client.ping()
                logger.info(f"Connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._client
    
    async def close(self):
        """Закрытие соединения с Redis"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Генерация ключа кэша
        
        Args:
            prefix: Префикс ключа
            *args: Позиционные аргументы для ключа
            **kwargs: Именованные аргументы для ключа
            
        Returns:
            Сгенерированный ключ
        """
        # Создаем строку из аргументов
        key_parts = [prefix]
        if args:
            key_parts.extend(str(arg) for arg in args)
        if kwargs:
            # Сортируем kwargs для консистентности
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend(f"{k}:{v}" for k, v in sorted_kwargs)
        
        key_string = ":".join(key_parts)
        # Хэшируем если ключ слишком длинный
        if len(key_string) > 250:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        return key_string
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получение значения из кэша
        
        Args:
            key: Ключ кэша
            
        Returns:
            Значение из кэша или None
        """
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value is None:
                return None
            
            # Попытка десериализации JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Если не JSON, возвращаем как есть
                return value
        except Exception as e:
            logger.warning(f"Error getting cache key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Сохранение значения в кэш
        
        Args:
            key: Ключ кэша
            value: Значение для сохранения
            ttl: Время жизни в секундах (если None, используется default_ttl)
            
        Returns:
            True если успешно, False иначе
        """
        try:
            client = await self._get_client()
            ttl = ttl if ttl is not None else self.default_ttl
            
            # Сериализация значения
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, ensure_ascii=False)
            else:
                serialized_value = str(value)
            
            await client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.warning(f"Error setting cache key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Удаление ключа из кэша
        
        Args:
            key: Ключ для удаления
            
        Returns:
            True если успешно, False иначе
        """
        try:
            client = await self._get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Error deleting cache key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Удаление всех ключей по паттерну
        
        Args:
            pattern: Паттерн для поиска ключей (например, "rag:*")
            
        Returns:
            Количество удаленных ключей
        """
        try:
            client = await self._get_client()
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Error deleting cache pattern {pattern}: {e}")
            return 0
    
    async def get_or_set(
        self,
        key: str,
        callable_func,
        ttl: Optional[int] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Получение значения из кэша или вычисление и сохранение
        
        Args:
            key: Ключ кэша
            callable_func: Функция для вычисления значения (может быть async)
            ttl: Время жизни в секундах
            *args: Аргументы для функции
            **kwargs: Именованные аргументы для функции
            
        Returns:
            Значение из кэша или результат выполнения функции
        """
        # Попытка получить из кэша
        cached_value = await self.get(key)
        if cached_value is not None:
            logger.debug(f"Cache hit for key: {key}")
            return cached_value
        
        # Вычисление значения
        logger.debug(f"Cache miss for key: {key}, computing...")
        if hasattr(callable_func, '__call__'):
            import asyncio
            if asyncio.iscoroutinefunction(callable_func):
                value = await callable_func(*args, **kwargs)
            else:
                value = callable_func(*args, **kwargs)
        else:
            value = callable_func
        
        # Сохранение в кэш
        await self.set(key, value, ttl)
        return value
    
    async def exists(self, key: str) -> bool:
        """
        Проверка существования ключа
        
        Args:
            key: Ключ для проверки
            
        Returns:
            True если ключ существует, False иначе
        """
        try:
            client = await self._get_client()
            return bool(await client.exists(key))
        except Exception as e:
            logger.warning(f"Error checking cache key {key}: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья Redis соединения
        
        Returns:
            Словарь со статусом здоровья
        """
        try:
            client = await self._get_client()
            info = await client.info()
            return {
                "status": "healthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown")
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

