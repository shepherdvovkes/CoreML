"""
Примеры использования Celery задач
"""
import asyncio
import httpx
import time


async def example_add_document():
    """Пример добавления документа через Celery"""
    async with httpx.AsyncClient() as client:
        # Загрузка файла
        with open("path/to/document.pdf", "rb") as f:
            files = {"file": ("document.pdf", f, "application/pdf")}
            response = await client.post(
                "http://localhost:8000/rag/add-document",
                files=files
            )
            result = response.json()
            print(f"Task queued: {result['task_id']}")
            
            # Проверка статуса
            task_id = result['task_id']
            while True:
                status_response = await client.get(
                    f"http://localhost:8000/rag/task/{task_id}"
                )
                status = status_response.json()
                print(f"Status: {status['status']}")
                
                if status['status'] == 'success':
                    print(f"Document processed: {status['result']}")
                    break
                elif status['status'] == 'failure':
                    print(f"Error: {status.get('error', 'Unknown error')}")
                    break
                
                await asyncio.sleep(2)  # Проверка каждые 2 секунды


async def example_batch_upload():
    """Пример пакетной загрузки документов"""
    async with httpx.AsyncClient() as client:
        files = []
        file_paths = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
        
        for path in file_paths:
            with open(path, "rb") as f:
                files.append(("files", (path, f.read(), "application/pdf")))
        
        response = await client.post(
            "http://localhost:8000/rag/add-documents-batch",
            files=files
        )
        result = response.json()
        print(f"Batch task queued: {result['task_id']}")
        print(f"Total documents: {result['total_documents']}")


async def example_check_task_status():
    """Пример проверки статуса задачи"""
    async with httpx.AsyncClient() as client:
        task_id = "your-task-id-here"
        response = await client.get(
            f"http://localhost:8000/rag/task/{task_id}"
        )
        status = response.json()
        print(f"Task {task_id}: {status['status']}")
        if status['status'] == 'success':
            print(f"Result: {status['result']}")


if __name__ == "__main__":
    # Раскомментируйте нужный пример
    # asyncio.run(example_add_document())
    # asyncio.run(example_batch_upload())
    # asyncio.run(example_check_task_status())
    pass

