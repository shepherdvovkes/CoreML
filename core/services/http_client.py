"""
HTTP клиент для межсервисной коммуникации
"""
import httpx
from typing import Optional, Dict, Any, List
from loguru import logger
from core.resilience import resilient_http


class ServiceHTTPClient:
    """Базовый HTTP клиент для межсервисной коммуникации"""
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_headers = headers or {}
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.default_headers
        )
    
    @resilient_http(name="http_get")
    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """GET запрос с retry, circuit breaker и timeout"""
        try:
            response = await self.client.get(
                path,
                params=params,
                headers={**self.default_headers, **(headers or {})}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error in GET request to {self.base_url}{path}: {e}")
            raise
    
    @resilient_http(name="http_post")
    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """POST запрос с retry, circuit breaker и timeout"""
        try:
            response = await self.client.post(
                path,
                json=json,
                data=data,
                headers={**self.default_headers, **(headers or {})}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error in POST request to {self.base_url}{path}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Проверка здоровья сервиса"""
        try:
            response = await self.client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for {self.base_url}: {e}")
            return False
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()


class RAGServiceClient(ServiceHTTPClient):
    """HTTP клиент для RAG сервиса"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        super().__init__(base_url, timeout=30.0)
    
    async def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Поиск в RAG системе"""
        response = await self.get(
            "/rag/search",
            params={"query": query, "top_k": top_k}
        )
        return response.get("results", [])
    
    async def add_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Добавление документа (синхронное, если нужно)"""
        # В production лучше использовать async upload
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"metadata": metadata} if metadata else {}
            response = await self.client.post(
                "/rag/add-document",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()


class EmbeddingServiceClient(ServiceHTTPClient):
    """HTTP клиент для Embedding сервиса (альтернатива ZeroMQ)"""
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        super().__init__(base_url, timeout=10.0)
    
    async def encode(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """Получение эмбеддингов для текстов"""
        # Батчинг для больших списков
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.post(
                "/embed",
                json={"texts": batch}
            )
            embeddings = response.get("embeddings", [])
            all_embeddings.extend(embeddings)
        return all_embeddings
    
    async def encode_single(self, text: str) -> List[float]:
        """Получение эмбеддинга для одного текста"""
        response = await self.post(
            "/embed",
            json={"texts": [text]}
        )
        embeddings = response.get("embeddings", [])
        return embeddings[0] if embeddings else []

