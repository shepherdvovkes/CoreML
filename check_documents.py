#!/usr/bin/env python3
"""
Скрипт для проверки загруженных документов в RAG системе
"""
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from core.rag.rag_service import RAGService
from core.services.cache_service import CacheService


async def check_documents():
    """Проверка загруженных документов"""
    logger.info("🔍 Проверяю загруженные документы...")
    
    try:
        # Создаем сервисы
        cache_service = CacheService()
        rag_service = RAGService(cache_service=cache_service)
        
        # Проверяем наличие документов
        has_docs = await rag_service.has_documents()
        
        if not has_docs:
            logger.warning("❌ Документы не найдены в векторном хранилище")
            return
        
        logger.info("✅ Документы найдены, получаю список...")
        
        # Получаем список документов
        documents = await rag_service.list_documents()
        
        if not documents:
            logger.warning("⚠️  Документы есть, но список пуст (возможна проблема с метаданными)")
            return
        
        logger.info(f"\n📄 Найдено документов: {len(documents)}\n")
        
        for i, doc in enumerate(documents, 1):
            logger.info(f"{i}. {doc.get('filename', 'Без имени')}")
            logger.info(f"   Путь: {doc.get('file_path', 'Не указан')}")
            logger.info(f"   Чанков: {doc.get('chunks_count', 0)}")
            if doc.get('uploaded_at'):
                logger.info(f"   Загружен: {doc.get('uploaded_at')}")
            if doc.get('metadata'):
                metadata_str = ", ".join([f"{k}={v}" for k, v in doc['metadata'].items() 
                                         if k not in ['text', 'filename', 'file_path', 'uploaded_at', 'indexed_at']])
                if metadata_str:
                    logger.info(f"   Метаданные: {metadata_str}")
            logger.info("")
        
        logger.info(f"✅ Всего документов: {len(documents)}")
        logger.info(f"✅ Всего чанков: {sum(doc.get('chunks_count', 0) for doc in documents)}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке документов: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_documents())

