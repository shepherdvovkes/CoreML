#!/usr/bin/env python3
"""
Скрипт инициализации баз данных при развертывании
Создает все необходимые коллекции и проверяет доступ
"""
import sys
import os
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config import settings
from core.services.cache_service import CacheService


async def init_qdrant():
    """Инициализация Qdrant - создание коллекций"""
    try:
        from core.rag.vector_store import create_vector_store
        
        logger.info("🔧 Инициализация Qdrant...")
        logger.info(f"   URL: {settings.qdrant_url}")
        logger.info(f"   Collection: {settings.qdrant_collection_name}")
        
        # Создание векторного хранилища автоматически создаст коллекцию
        vector_store = create_vector_store()
        
        # Проверка доступа - коллекция уже создана при инициализации
        if hasattr(vector_store, 'client'):
            try:
                collections = vector_store.client.get_collections().collections
                collection_names = [c.name for c in collections]
                
                if settings.qdrant_collection_name in collection_names:
                    logger.info(f"✅ Коллекция '{settings.qdrant_collection_name}' существует")
                else:
                    logger.warning(f"⚠️  Коллекция '{settings.qdrant_collection_name}' не найдена")
            except Exception as e:
                logger.warning(f"⚠️  Не удалось проверить коллекции: {e}")
        
        logger.info("✅ Qdrant инициализирован успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Qdrant: {e}")
        return False


async def init_redis():
    """Инициализация Redis - проверка доступа"""
    try:
        logger.info("🔧 Инициализация Redis...")
        logger.info(f"   URL: {settings.redis_url}")
        
        cache_service = CacheService()
        
        # Проверка подключения
        health = await cache_service.health_check()
        
        if health["status"] == "healthy":
            logger.info("✅ Redis доступен и работает")
            
            # Тест записи/чтения
            test_key = "coreml_init_test"
            test_value = "test_value"
            
            await cache_service.set(test_key, test_value, ttl=10)
            cached_value = await cache_service.get(test_key)
            
            if cached_value == test_value:
                logger.info("✅ Redis: запись и чтение работают корректно")
                await cache_service.delete(test_key)
            else:
                logger.warning("⚠️  Redis: проблема с записью/чтением")
            
            await cache_service.close()
            return True
        else:
            logger.error(f"❌ Redis недоступен: {health.get('error', 'unknown')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Redis: {e}")
        return False


async def init_chromadb():
    """Инициализация ChromaDB (fallback) - создание коллекций"""
    try:
        if settings.rag_vector_db_type.lower() != "chroma":
            logger.info("ℹ️  ChromaDB не используется (пропуск)")
            return True
        
        logger.info("🔧 Инициализация ChromaDB...")
        logger.info(f"   Path: {settings.rag_vector_db_path}")
        
        from core.rag.vector_store import ChromaVectorStore
        
        # Создание хранилища автоматически создаст коллекцию
        vector_store = ChromaVectorStore(settings.rag_embedding_model)
        
        # Проверка коллекции
        collections = vector_store.client.list_collections()
        collection_names = [c.name for c in collections]
        
        if "legal_documents" in collection_names:
            logger.info("✅ Коллекция 'legal_documents' существует")
        else:
            logger.warning("⚠️  Коллекция 'legal_documents' не найдена")
        
        logger.info("✅ ChromaDB инициализирован успешно")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️  ChromaDB недоступен (это нормально если используется Qdrant): {e}")
        return True  # Не критично, если используется Qdrant


async def check_permissions():
    """Проверка прав доступа к данным"""
    logger.info("🔍 Проверка прав доступа...")
    
    issues = []
    
    # Проверка Qdrant API ключа
    if settings.qdrant_api_key:
        logger.info("✅ Qdrant API ключ установлен")
    else:
        logger.warning("⚠️  Qdrant API ключ не установлен (работает без аутентификации)")
    
    # Проверка Redis пароля
    redis_url = settings.redis_url
    if ":" in redis_url and "@" in redis_url:
        logger.info("✅ Redis пароль установлен в URL")
    else:
        logger.warning("⚠️  Redis пароль не найден в URL (работает без аутентификации)")
        issues.append("Redis password missing")
    
    # Проверка прав на директорию данных
    data_dir = Path("./data")
    if data_dir.exists():
        try:
            test_file = data_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            logger.info("✅ Права на запись в директорию data")
        except Exception as e:
            logger.error(f"❌ Нет прав на запись в директорию data: {e}")
            issues.append("Data directory write permission")
    
    if issues:
        logger.warning(f"⚠️  Обнаружены проблемы с доступом: {', '.join(issues)}")
        return False
    
    return True


async def main():
    """Основная функция инициализации"""
    logger.info("🚀 Начало инициализации баз данных...")
    logger.info("")
    
    results = {
        "qdrant": False,
        "redis": False,
        "chromadb": False,
        "permissions": False
    }
    
    # Инициализация Qdrant (основная БД)
    if settings.rag_vector_db_type.lower() == "qdrant":
        results["qdrant"] = await init_qdrant()
    else:
        results["chromadb"] = await init_chromadb()
    
    logger.info("")
    
    # Инициализация Redis
    results["redis"] = await init_redis()
    
    logger.info("")
    
    # Проверка прав доступа
    results["permissions"] = await check_permissions()
    
    logger.info("")
    logger.info("=" * 50)
    logger.info("📊 Результаты инициализации:")
    logger.info("")
    
    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        logger.info(f"   {status_icon} {service.upper()}: {'OK' if status else 'FAILED'}")
    
    logger.info("")
    
    # Итоговый результат
    all_ok = all(results.values())
    
    if all_ok:
        logger.info("✅ Все базы данных инициализированы успешно!")
        return 0
    else:
        logger.error("❌ Некоторые базы данных не инициализированы")
        logger.error("   Проверьте логи выше для деталей")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

