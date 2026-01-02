"""
Основной API сервер для CoreML_RAG_MCP_Prompt (Stateless)
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional, List
from loguru import logger
import uvicorn

from config import settings, LLMProvider
from core.router.query_router import QueryRouter
from core.rag.rag_service import RAGService
from core.mcp.law_client import LawMCPClient
from core.services.cache_service import CacheService
from core.tasks import process_document_task, process_documents_batch_task

# Настройка логирования
logger.add("logs/app.log", rotation="10 MB", level=settings.log_level)

app = FastAPI(
    title="CoreML RAG MCP Prompt Service",
    description="Stateless маршрутизатор для работы с RAG, MCP серверами и LLM",
    version="0.2.0"
)


# Dependency Injection для создания stateless сервисов
async def get_cache_service() -> CacheService:
    """Создание сервиса кэширования"""
    cache_service = CacheService()
    try:
        await cache_service._get_client()
    except Exception as e:
        logger.warning(f"Cache service unavailable: {e}, continuing without cache")
        return None
    return cache_service


async def get_rag_service(cache_service: CacheService = Depends(get_cache_service)) -> RAGService:
    """Создание RAG сервиса"""
    return RAGService(cache_service=cache_service)


async def get_law_client() -> LawMCPClient:
    """Создание Law MCP клиента"""
    return LawMCPClient()


async def get_query_router(
    rag_service: RAGService = Depends(get_rag_service),
    law_client: LawMCPClient = Depends(get_law_client),
    cache_service: CacheService = Depends(get_cache_service)
) -> QueryRouter:
    """Создание QueryRouter (stateless)"""
    return QueryRouter(
        rag_service=rag_service,
        law_client=law_client,
        cache_service=cache_service
)


# Модели запросов
class QueryRequest(BaseModel):
    query: str
    llm_provider: Optional[str] = None
    model: Optional[str] = None
    use_rag: Optional[bool] = None
    use_law: Optional[bool] = None


class SuggestedAction(BaseModel):
    id: str
    label: str
    type: str = "action"


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    model: Optional[str] = None
    usage: Optional[dict] = None
    metadata: Optional[dict] = None
    suggested_actions: Optional[List[SuggestedAction]] = None


@app.on_event("startup")
async def startup():
    """Инициализация при запуске"""
    logger.info("Starting CoreML RAG MCP Prompt Service (Stateless)")
    logger.info(f"Default LLM Provider: {settings.default_llm_provider}")
    logger.info(f"Vector DB Type: {settings.rag_vector_db_type}")
    logger.info(f"Vector DB URL: {settings.qdrant_url if settings.rag_vector_db_type == 'qdrant' else settings.rag_vector_db_path}")
    logger.info(f"Redis URL: {settings.redis_url}")
    
    # Проверка здоровья зависимостей
    try:
        cache_service = CacheService()
        health = await cache_service.health_check()
        if health["status"] == "healthy":
            logger.info(f"Redis cache: {health['status']}")
        else:
            logger.warning(f"Redis cache: {health.get('error', 'unhealthy')}")
    except Exception as e:
        logger.warning(f"Redis cache unavailable: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Очистка при остановке"""
    from core.llm.factory import LLMProviderFactory
    await LLMProviderFactory.close_all()
    logger.info("Service stopped")


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "CoreML RAG MCP Prompt Service",
        "version": "0.2.0",
        "status": "running",
        "architecture": "stateless"
    }


@app.get("/health")
async def health(cache_service: CacheService = Depends(get_cache_service)):
    """Проверка здоровья сервиса и зависимостей"""
    health_status = {
        "status": "healthy",
        "dependencies": {}
    }
    
    # Проверка Redis
    if cache_service:
        cache_health = await cache_service.health_check()
        health_status["dependencies"]["redis"] = cache_health
        if cache_health["status"] != "healthy":
            health_status["status"] = "degraded"
    else:
        health_status["dependencies"]["redis"] = {"status": "unavailable"}
        health_status["status"] = "degraded"
    
    # Проверка векторной БД
    try:
        from core.rag.vector_store import create_vector_store
        vector_store = create_vector_store()
        health_status["dependencies"]["vector_db"] = {
            "status": "healthy",
            "type": settings.rag_vector_db_type
        }
    except Exception as e:
        health_status["dependencies"]["vector_db"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    return health_status


@app.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    router: QueryRouter = Depends(get_query_router)
):
    """
    Обработка запроса пользователя
    
    Args:
        request: Запрос с вопросом и параметрами
        router: QueryRouter (stateless, создается через DI)
        
    Returns:
        Ответ с результатами обработки
    """
    try:
        llm_provider = None
        if request.llm_provider:
            try:
                llm_provider = LLMProvider(request.llm_provider.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown LLM provider: {request.llm_provider}"
                )
        
        result = await router.process_query(
            query=request.query,
            llm_provider=llm_provider,
            model=request.model,
            use_rag=request.use_rag,
            use_law=request.use_law
        )
        
        # Преобразуем suggested_actions в SuggestedAction объекты, если они есть
        if result.get("suggested_actions"):
            result["suggested_actions"] = [
                SuggestedAction(**action) if isinstance(action, dict) else action
                for action in result["suggested_actions"]
            ]
        
        return QueryResponse(**result)
    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    router: QueryRouter = Depends(get_query_router)
):
    """
    Потоковая обработка запроса
    
    Args:
        request: Запрос с вопросом и параметрами
        router: QueryRouter (stateless, создается через DI)
        
    Returns:
        Поток ответа
    """
    try:
        llm_provider = None
        if request.llm_provider:
            try:
                llm_provider = LLMProvider(request.llm_provider.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown LLM provider: {request.llm_provider}"
                )
        
        async def generate():
            async for chunk in router.stream_process_query(
                query=request.query,
                llm_provider=llm_provider,
                model=request.model,
                use_rag=request.use_rag,
                use_law=request.use_law
            ):
                yield chunk
        
        return StreamingResponse(generate(), media_type="text/plain")
    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        logger.error(f"Error streaming query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/add-document")
async def add_document(file: UploadFile = File(...)):
    """
    Добавление документа в RAG систему (асинхронная обработка через Celery)
    
    Args:
        file: Загружаемый файл
        
    Returns:
        Результат с task_id для отслеживания статуса
    """
    try:
        # Чтение содержимого файла
        content = await file.read()
        
        # Запуск фоновой задачи через Celery
        task = process_document_task.delay(
            file_path=None,  # Файл еще не сохранен
            file_content=content,
            filename=file.filename,
            metadata={"filename": file.filename, "uploaded_at": "now"}
        )
        
        return {
            "status": "queued",
            "task_id": task.id,
            "message": f"Document {file.filename} queued for processing",
            "check_status_url": f"/rag/task/{task.id}"
        }
    except Exception as e:
        logger.error(f"Error queuing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Получение статуса задачи обработки документа
    
    Args:
        task_id: ID задачи Celery
        
    Returns:
        Статус задачи и результат (если готов)
    """
    try:
        from core.celery_app import celery_app
        
        task = celery_app.AsyncResult(task_id)
        
        if task.state == "PENDING":
            response = {
                "task_id": task_id,
                "status": "pending",
                "message": "Task is waiting to be processed"
            }
        elif task.state == "PROGRESS":
            response = {
                "task_id": task_id,
                "status": "processing",
                "message": "Task is being processed",
                "progress": task.info.get("progress", 0) if isinstance(task.info, dict) else None
            }
        elif task.state == "SUCCESS":
            response = {
                "task_id": task_id,
                "status": "success",
                "result": task.result
            }
        else:  # FAILURE или другие состояния
            response = {
                "task_id": task_id,
                "status": task.state.lower(),
                "error": str(task.info) if task.info else "Unknown error"
            }
        
        return response
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/add-documents-batch")
async def add_documents_batch(files: List[UploadFile] = File(...)):
    """
    Пакетное добавление документов в RAG систему
    
    Args:
        files: Список загружаемых файлов
        
    Returns:
        Результат со списком task_id для каждого документа
    """
    try:
        # Создаем отдельные задачи для каждого документа
        # Это позволяет фронтенду отслеживать статус каждого документа отдельно
        individual_tasks = []
        for file in files:
            content = await file.read()
            task = process_document_task.delay(
                file_path=None,
                file_content=content,
                filename=file.filename,
                metadata={"filename": file.filename, "uploaded_at": "now"}
            )
            individual_tasks.append({
                "task_id": task.id,
                "filename": file.filename
            })
        
        return {
            "status": "queued",
            "total_documents": len(individual_tasks),
            "message": f"{len(individual_tasks)} documents queued for processing",
            "results": individual_tasks  # Список task_id для каждого документа
        }
    except Exception as e:
        logger.error(f"Error queuing documents batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/search")
async def rag_search(
    query: str = Query(...),
    top_k: int = Query(5),
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Поиск в RAG системе
    
    Args:
        query: Поисковый запрос
        top_k: Количество результатов
        rag_service: RAG сервис (stateless, создается через DI)
        
    Returns:
        Результаты поиска
    """
    try:
        results = await rag_service.search(query, top_k)
        return {"query": query, "results": results}
    except Exception as e:
        logger.error(f"Error searching RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/documents")
async def list_documents(
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Получение списка всех загруженных документов
    
    Args:
        rag_service: RAG сервис (stateless, создается через DI)
        
    Returns:
        Список документов с метаданными
    """
    try:
        documents = await rag_service.list_documents()
        return {
            "total": len(documents),
            "documents": documents
        }
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/documents/{filename}/chunks")
async def get_document_chunks(
    filename: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Получение всех чанков документа по имени файла
    
    Args:
        filename: Имя файла документа
        rag_service: RAG сервис (stateless, создается через DI)
        
    Returns:
        Список чанков документа с текстом и метаданными
    """
    try:
        chunks = await rag_service.get_document_chunks(filename)
        return {
            "filename": filename,
            "chunks_count": len(chunks),
            "chunks": chunks
        }
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/documents/{filename}/preview")
async def get_document_preview(
    filename: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Получение изображения первой страницы документа (превью)
    
    Args:
        filename: Имя файла документа
        rag_service: RAG сервис (stateless, создается через DI)
        
    Returns:
        Изображение PNG первой страницы документа
    """
    try:
        image_bytes = await rag_service.get_document_preview_image(filename)
        if image_bytes is None:
            raise HTTPException(status_code=404, detail="Preview image not available for this document")
        
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="{filename}_preview.png"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/rag/documents/{filename}")
async def delete_document(
    filename: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Удаление документа по имени файла
    
    Args:
        filename: Имя файла документа
        rag_service: RAG сервис (stateless, создается через DI)
        
    Returns:
        Результат удаления
    """
    try:
        deleted = await rag_service.delete_document(filename)
        if deleted:
            return {
                "status": "success",
                "message": f"Document '{filename}' deleted successfully"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/rag/documents")
async def delete_all_documents(
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Удаление всех документов
    
    Args:
        rag_service: RAG сервис (stateless, создается через DI)
        
    Returns:
        Результат удаления
    """
    try:
        documents = await rag_service.list_documents()
        if not documents:
            return {
                "status": "success",
                "message": "No documents to delete",
                "deleted_count": 0
            }
        
        deleted_count = 0
        errors = []
        for doc in documents:
            filename = doc.get('filename') or doc.get('file_path')
            if filename:
                try:
                    deleted = await rag_service.delete_document(filename)
                    if deleted:
                        deleted_count += 1
                except Exception as e:
                    errors.append(f"Error deleting '{filename}': {str(e)}")
                    logger.error(f"Error deleting document '{filename}': {e}")
        
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} out of {len(documents)} documents",
            "deleted_count": deleted_count,
            "total_count": len(documents),
            "errors": errors if errors else None
        }
    except Exception as e:
        logger.error(f"Error deleting all documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/law/search-cases")
async def search_cases(
    query: str = Query(...),
    instance: str = Query("3"),
    limit: int = Query(25),
    law_client: LawMCPClient = Depends(get_law_client)
):
    """
    Поиск судебных дел через MCP
    
    Args:
        query: Поисковый запрос
        instance: Инстанция суда
        limit: Максимальное количество результатов
        law_client: Law MCP клиент (stateless, создается через DI)
        
    Returns:
        Результаты поиска
    """
    try:
        results = await law_client.search_cases(query, instance, limit)
        return {"query": query, "results": results}
    except Exception as e:
        logger.error(f"Error searching cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mcp/law/case/{case_number}")
async def get_case(
    case_number: str,
    law_client: LawMCPClient = Depends(get_law_client)
):
    """
    Получение деталей дела
    
    Args:
        case_number: Номер дела
        law_client: Law MCP клиент (stateless, создается через DI)
        
    Returns:
        Детали дела
    """
    try:
        details = await law_client.get_case_details(case_number=case_number)
        if not details:
            raise HTTPException(status_code=404, detail="Case not found")
        return details
    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        logger.error(f"Error getting case: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mcp/law/case/{case_number}/full-text")
async def get_case_full_text_by_number(
    case_number: str,
    law_client: LawMCPClient = Depends(get_law_client)
):
    """
    Получение полного текста дела по номеру дела (напрямую из MCP, без LLM)
    
    Args:
        case_number: Номер дела (формат: число/число/число)
        law_client: Law MCP клиент (stateless, создается через DI)
        
    Returns:
        Полный текст дела в формате для клиента
    """
    try:
        # Получаем детали дела по номеру
        details = await law_client.get_case_details(case_number=case_number)
        if not details or not details.get('success'):
            raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
        
        cases_list = details.get('cases', [])
        if not cases_list:
            raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
        
        # Берем первое дело из списка
        case = cases_list[0]
        doc_id = case.get('doc_id') or case.get('id')
        
        if not doc_id:
            raise HTTPException(status_code=404, detail=f"Case {case_number} has no doc_id")
        
        # Получаем полный текст
        full_text_data = await law_client.get_case_full_text(str(doc_id))
        if not full_text_data or not full_text_data.get('success'):
            raise HTTPException(status_code=404, detail=f"Full text for case {case_number} not found")
        
        text = full_text_data.get('text', '')
        if not text:
            raise HTTPException(status_code=404, detail=f"Full text for case {case_number} is empty")
        
        # Форматируем ответ для клиента
        return {
            "success": True,
            "case_number": case_number,
            "title": case.get('title', 'N/A'),
            "text": text,
            "doc_id": str(doc_id)
        }
    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        logger.error(f"Error getting case full text by number: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mcp/law/case/{doc_id}/full-text")
async def get_case_full_text(
    doc_id: str,
    law_client: LawMCPClient = Depends(get_law_client)
):
    """
    Получение полного текста дела по doc_id
    
    Args:
        doc_id: ID документа
        law_client: Law MCP клиент (stateless, создается через DI)
        
    Returns:
        Полный текст дела
    """
    try:
        full_text = await law_client.get_case_full_text(doc_id)
        if not full_text:
            raise HTTPException(status_code=404, detail="Case full text not found")
        return full_text
    except HTTPException:
        # Пробрасываем HTTPException как есть
        raise
    except Exception as e:
        logger.error(f"Error getting case full text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/llm/providers")
async def get_llm_providers():
    """
    Получение списка доступных LLM провайдеров
    
    Returns:
        Список провайдеров с их конфигурацией
    """
    try:
        from core.llm.factory import LLMProviderFactory
        providers = LLMProviderFactory.get_available_providers()
        return {
            "providers": providers,
            "default_provider": settings.default_llm_provider.value
        }
    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/providers/{provider_name}/validate")
async def validate_llm_provider(
    provider_name: str,
    model: Optional[str] = Query(None)
):
    """
    Проверка валидности LLM провайдера
    
    Args:
        provider_name: Имя провайдера (openai, ollama, lmstudio, custom)
        model: Название модели (опционально)
        
    Returns:
        Результат проверки валидности
    """
    try:
        from core.llm.factory import LLMProviderFactory
        
        # Преобразуем строку в enum
        try:
            provider_type = LLMProvider(provider_name.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider: {provider_name}. Available: {[p.value for p in LLMProvider]}"
            )
        
        # Проверяем валидность
        result = await LLMProviderFactory.validate_provider(provider_type, model)
        
        return {
            "provider": provider_name,
            "model": model,
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        reload=True
    )
