"""
Конфигурация сервиса CoreML_RAG_MCP_Prompt
"""
from pydantic_settings import BaseSettings
from typing import Literal
from enum import Enum


class LLMProvider(str, Enum):
    """Поддерживаемые провайдеры LLM"""
    OPENAI = "openai"
    LMSTUDIO = "lmstudio"
    CUSTOM = "custom"


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # LLM Providers
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    custom_llm_base_url: str = "http://localhost:8000/v1"
    default_llm_provider: LLMProvider = LLMProvider.OPENAI
    
    # RAG Configuration
    rag_vector_db_path: str = "./data/vector_db"  # Для локальной ChromaDB (fallback)
    rag_vector_db_type: str = "qdrant"  # qdrant, chroma, weaviate
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    rag_top_k: int = 5
    
    # Qdrant Configuration
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "legal_documents"
    qdrant_timeout: int = 30
    
    # MCP Configuration
    mcp_law_server_url: str = "http://localhost:3000"
    mcp_law_api_key: str = ""
    
    # Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    
    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: list = ["json"]
    celery_timezone: str = "UTC"
    celery_enable_utc: bool = True
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 300  # 5 minutes
    celery_task_soft_time_limit: int = 240  # 4 minutes
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600  # 1 hour
    
    # MLflow Configuration
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "coreml_rag"
    
    # Model Registry Configuration
    model_registry_path: str = "./data/model_registry.json"
    
    # Resilience Configuration (Retry, Circuit Breaker, Timeout)
    # Retry настройки
    resilience_retry_max_attempts: int = 3
    resilience_retry_min_wait: int = 1  # секунды
    resilience_retry_max_wait: int = 10  # секунды
    resilience_retry_multiplier: int = 2
    
    # Circuit Breaker настройки
    resilience_cb_fail_max: int = 5  # количество ошибок для открытия circuit
    resilience_cb_timeout: int = 60  # секунды до попытки восстановления
    
    # Timeout настройки (в секундах)
    resilience_default_timeout: int = 30
    resilience_llm_timeout: int = 120  # LLM запросы обычно медленнее
    resilience_rag_timeout: int = 60
    resilience_mcp_timeout: int = 45
    resilience_http_timeout: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

