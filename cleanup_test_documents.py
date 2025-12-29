#!/usr/bin/env python3
"""
Скрипт для очистки тестовых документов из RAG системы
"""
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from core.rag.rag_service import RAGService
from core.services.cache_service import CacheService


async def cleanup_test_documents():
    """Очистка тестовых документов"""
    logger.info("🧹 Начинаю очистку тестовых документов...")
    
    try:
        # Создаем сервисы
        cache_service = CacheService()
        rag_service = RAGService(cache_service=cache_service)
        
        # Получаем список всех документов
        documents = await rag_service.list_documents()
        
        if not documents:
            logger.info("✅ Документов не найдено, нечего удалять")
            return
        
        logger.info(f"📄 Найдено документов: {len(documents)}")
        
        # Ищем тестовые документы
        test_documents = []
        for doc in documents:
            filename = doc.get('filename', '')
            file_path = doc.get('file_path', '')
            source = doc.get('metadata', {}).get('source', '')
            
            # Проверяем, является ли документ тестовым
            is_test = (
                filename.lower() == 'test' or
                file_path.lower() == 'test' or
                source.lower() == 'test' or
                'test' in filename.lower() or
                'test' in file_path.lower()
            )
            
            if is_test:
                test_documents.append(doc)
                logger.info(f"  🗑️  Найден тестовый документ: {filename} (путь: {file_path})")
        
        if not test_documents:
            logger.info("✅ Тестовые документы не найдены")
            return
        
        logger.info(f"\n🗑️  Найдено тестовых документов для удаления: {len(test_documents)}")
        
        # Удаляем тестовые документы
        deleted_count = 0
        for doc in test_documents:
            filename = doc.get('filename', '') or doc.get('file_path', '')
            if filename:
                logger.info(f"  Удаляю: {filename}...")
                deleted = await rag_service.delete_document(filename)
                if deleted:
                    deleted_count += 1
                    logger.info(f"    ✅ Удален: {filename}")
                else:
                    logger.warning(f"    ⚠️  Не удалось удалить: {filename}")
        
        logger.info(f"\n✅ Очистка завершена: удалено {deleted_count} из {len(test_documents)} тестовых документов")
        
        # Проверяем оставшиеся документы
        remaining = await rag_service.list_documents()
        logger.info(f"📄 Осталось документов в системе: {len(remaining)}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке документов: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(cleanup_test_documents())

