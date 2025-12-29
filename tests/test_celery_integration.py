"""
Интеграционные тесты для Celery задач
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from core.tasks import process_document_task, process_documents_batch_task, health_check_task
from core.rag.rag_service import RAGService


class TestCeleryTasksIntegration:
    """Интеграционные тесты Celery задач"""
    
    def test_process_document_task_success(self, sample_document_content):
        """Тест успешной обработки документа"""
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
            f.write(sample_document_content)
            temp_file = f.name
        
        try:
            # Мокаем RAG сервис
            with patch('core.tasks.get_rag_service') as mock_get_rag:
                mock_rag = Mock(spec=RAGService)
                mock_rag.add_document = Mock()
                mock_get_rag.return_value = mock_rag
                
                # Выполняем задачу
                result = process_document_task(
                    file_path=temp_file,
                    metadata={"test": True},
                    filename="test_document.txt"
                )
                
                assert result["status"] == "success"
                assert result["filename"] == "test_document.txt"
                assert mock_rag.add_document.called
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_process_document_task_with_file_content(self, sample_document_content):
        """Тест обработки документа из содержимого файла"""
        with patch('core.tasks.get_rag_service') as mock_get_rag:
            mock_rag = Mock(spec=RAGService)
            mock_rag.add_document = Mock()
            mock_get_rag.return_value = mock_rag
            
            # Создаем временный файл для проверки
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
                f.write(sample_document_content)
                temp_file = f.name
            
            try:
                result = process_document_task(
                    file_path=None,
                    file_content=sample_document_content,
                    filename="test_document.txt",
                    metadata={"test": True}
                )
                
                assert result["status"] == "success"
                assert mock_rag.add_document.called
            finally:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
    
    def test_process_document_task_file_not_found(self):
        """Тест обработки ошибки при отсутствии файла"""
        with patch('core.tasks.get_rag_service') as mock_get_rag:
            mock_rag = Mock(spec=RAGService)
            mock_get_rag.return_value = mock_rag
            
            # Создаем мок задачи с retry
            mock_task = Mock()
            mock_task.request.retries = 0
            mock_task.max_retries = 3
            mock_task.retry = Mock(side_effect=Exception("Retry called"))
            
            # Заменяем self в задаче
            with patch.object(process_document_task, 'request', mock_task.request):
                with patch.object(process_document_task, 'max_retries', 3):
                    with patch.object(process_document_task, 'retry', mock_task.retry):
                        with pytest.raises(ValueError):
                            process_document_task(
                                file_path="/nonexistent/file.txt",
                                metadata={}
                            )
    
    def test_process_documents_batch_task(self, sample_document_content):
        """Тест пакетной обработки документов"""
        with patch('core.tasks.process_document_task') as mock_process:
            # Мокаем apply_async для каждой задачи
            mock_result = Mock()
            mock_result.id = "test-task-id"
            mock_process.apply_async = Mock(return_value=mock_result)
            
            documents = [
                {
                    "file_path": None,
                    "file_content": sample_document_content,
                    "filename": "doc1.txt",
                    "metadata": {"index": 1}
                },
                {
                    "file_path": None,
                    "file_content": sample_document_content,
                    "filename": "doc2.txt",
                    "metadata": {"index": 2}
                }
            ]
            
            # Создаем мок задачи
            mock_task = Mock()
            mock_task.request.retries = 0
            mock_task.max_retries = 2
            
            # Вызываем функцию напрямую, передавая мок как self
            # Используем __wrapped__ для получения оригинальной функции без декоратора
            original_func = process_documents_batch_task.__wrapped__ if hasattr(process_documents_batch_task, '__wrapped__') else process_documents_batch_task
            result = original_func(mock_task, documents)
            
            assert result["total"] == 2
            assert result["queued"] == 2
            assert len(result["results"]) == 2
            assert all("task_id" in r for r in result["results"])
    
    def test_process_documents_batch_with_errors(self, sample_document_content):
        """Тест пакетной обработки с ошибками"""
        with patch('core.tasks.process_document_task') as mock_process:
            # Первая задача успешна, вторая с ошибкой
            mock_result1 = Mock()
            mock_result1.id = "task-1"
            mock_result2 = Mock()
            mock_result2.id = "task-2"
            
            def side_effect(*args, **kwargs):
                if kwargs.get('filename') == 'doc2.txt':
                    raise Exception("Processing error")
                return mock_result1
            
            mock_process.apply_async = Mock(side_effect=side_effect)
            
            documents = [
                {
                    "file_path": None,
                    "file_content": sample_document_content,
                    "filename": "doc1.txt"
                },
                {
                    "file_path": None,
                    "file_content": sample_document_content,
                    "filename": "doc2.txt"
                }
            ]
            
            mock_task = Mock()
            mock_task.request.retries = 0
            mock_task.max_retries = 2
            
            # Вызываем функцию напрямую
            original_func = process_documents_batch_task.__wrapped__ if hasattr(process_documents_batch_task, '__wrapped__') else process_documents_batch_task
            result = original_func(mock_task, documents)
            
            assert result["total"] == 2
            assert result["errors"] > 0
            assert len(result.get("errors", [])) > 0
    
    def test_health_check_task(self):
        """Тест задачи проверки здоровья"""
        with patch('core.tasks.get_rag_service') as mock_get_rag:
            mock_rag = Mock(spec=RAGService)
            mock_get_rag.return_value = mock_rag
            
            result = health_check_task()
            
            assert result["status"] == "healthy"
            assert "rag_service" in result
    
    def test_health_check_task_error(self):
        """Тест задачи проверки здоровья с ошибкой"""
        with patch('core.tasks.get_rag_service', side_effect=Exception("Service error")):
            result = health_check_task()
            
            assert result["status"] == "unhealthy"
            assert "error" in result

