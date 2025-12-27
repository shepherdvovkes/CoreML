"""
Сервисы для межсервисной коммуникации и кэширования
"""
from .cache_service import CacheService
from .http_client import ServiceHTTPClient, RAGServiceClient, EmbeddingServiceClient

__all__ = ["CacheService", "ServiceHTTPClient", "RAGServiceClient", "EmbeddingServiceClient"]

