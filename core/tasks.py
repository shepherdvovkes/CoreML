"""
Celery задачи для фоновой обработки
"""
import os
import tempfile
from typing import Dict, Any, Optional, List
from loguru import logger
from core.celery_app import celery_app
from core.rag.rag_service import RAGService


# Инициализация RAG сервиса для воркеров
# В production лучше использовать dependency injection
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Получить или создать RAG сервис (singleton для воркеров)"""
    global _rag_service
    if _rag_service is None:
        # Celery задачи не используют кэш (они выполняются в фоне)
        _rag_service = RAGService(cache_service=None)
        logger.info("RAG service initialized for Celery worker (without cache)")
    return _rag_service


@celery_app.task(
    name="core.tasks.process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    soft_time_limit=240,  # 4 minutes
    time_limit=300  # 5 minutes
)
def process_document_task(
    self,
    file_path: str,
    metadata: Optional[Dict[str, Any]] = None,
    file_content: Optional[bytes] = None,
    filename: Optional[str] = None
):
    """
    Фоновая задача для обработки и добавления документа в RAG систему
    
    Args:
        self: Celery task instance (для retry)
        file_path: Путь к файлу (если файл уже сохранен)
        metadata: Метаданные документа
        file_content: Содержимое файла в байтах (если файл еще не сохранен)
        filename: Имя файла (для временного сохранения)
        
    Returns:
        dict: Результат обработки
    """
    try:
        rag_service = get_rag_service()
        temp_file_path = None
        
        # Если передан контент, сохраняем во временный файл
        if file_content and filename:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=os.path.splitext(filename)[1]
            )
            temp_file.write(file_content)
            temp_file.close()
            temp_file_path = temp_file.name
            file_path = temp_file_path
        
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        # Подготовка метаданных
        if metadata is None:
            metadata = {}
        if filename:
            metadata['filename'] = filename
        metadata['processed_by'] = 'celery'
        
        # Обработка документа
        logger.info(f"Processing document: {file_path}")
        add_result = rag_service.add_document(file_path, metadata=metadata)
        
        # Очистка временного файла
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        
        # Формируем результат с информацией из add_document
        result = {
            "status": add_result.get("status", "success"),
            "file_path": file_path,
            "filename": filename or os.path.basename(file_path),
            "message": add_result.get("message", "Document processed and added to RAG system"),
            "chunks_count": add_result.get("chunks_count", 0),
            "collections": add_result.get("collections", [])
        }
        
        logger.info(f"Document processed successfully: {result['filename']} - {result.get('chunks_count', 0)} chunks in {result.get('collections', [])}")
        return result
        
    except Exception as exc:
        logger.error(f"Error processing document: {exc}")
        
        # Очистка временного файла при ошибке
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        # Retry при определенных ошибках
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying document processing (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=exc)
        else:
            # Максимальное количество retry достигнуто
            raise


@celery_app.task(
    name="core.tasks.process_documents_batch",
    bind=True,
    max_retries=2
)
def process_documents_batch_task(
    self,
    documents: List[Dict[str, Any]]
):
    """
    Пакетная обработка нескольких документов
    
    Args:
        self: Celery task instance
        documents: Список словарей с ключами:
            - file_path: путь к файлу
            - metadata: метаданные (опционально)
            - file_content: содержимое файла (опционально)
            - filename: имя файла (опционально)
            
    Returns:
        dict: Результаты обработки всех документов
    """
    results = []
    errors = []
    
    for i, doc in enumerate(documents):
        try:
            result = process_document_task.apply_async(
                args=(doc.get('file_path'),),
                kwargs={
                    'metadata': doc.get('metadata'),
                    'file_content': doc.get('file_content'),
                    'filename': doc.get('filename')
                }
            )
            results.append({
                'index': i,
                'task_id': result.id,
                'status': 'queued',
                'filename': doc.get('filename', 'unknown')
            })
        except Exception as e:
            errors.append({
                'index': i,
                'error': str(e),
                'filename': doc.get('filename', 'unknown')
            })
            logger.error(f"Error queuing document {i}: {e}")
    
    return {
        'total': len(documents),
        'queued': len(results),
        'errors': len(errors),
        'results': results,
        'errors': errors
    }


@celery_app.task(name="core.tasks.health_check")
def health_check_task():
    """
    Задача для проверки здоровья Celery воркеров
    
    Returns:
        dict: Статус здоровья
    """
    try:
        rag_service = get_rag_service()
        # Простая проверка доступности сервиса
        return {
            "status": "healthy",
            "rag_service": "available"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

