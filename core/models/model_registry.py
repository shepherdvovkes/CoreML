"""
Реестр версий моделей
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field
from loguru import logger
from config import settings


class ModelType(str, Enum):
    """Типы моделей"""
    EMBEDDING = "embedding"
    LLM = "llm"
    RERANKER = "reranker"


class ModelStatus(str, Enum):
    """Статусы моделей"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ModelVersion(BaseModel):
    """Версия модели"""
    version: str = Field(..., description="Версия модели (семантическое версионирование: major.minor.patch)")
    model_name: str = Field(..., description="Название модели")
    model_type: ModelType = Field(..., description="Тип модели")
    status: ModelStatus = Field(default=ModelStatus.DEVELOPMENT, description="Статус версии")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания")
    created_by: str = Field(default="system", description="Создатель версии")
    description: Optional[str] = Field(None, description="Описание версии")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")
    mlflow_run_id: Optional[str] = Field(None, description="ID запуска MLflow")
    performance_metrics: Dict[str, float] = Field(default_factory=dict, description="Метрики производительности")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Зависимости (модели, библиотеки)")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ModelMetadata(BaseModel):
    """Метаданные модели"""
    model_name: str
    model_type: ModelType
    current_version: str
    versions: List[ModelVersion] = Field(default_factory=list)
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ModelRegistry:
    """Реестр версий моделей"""
    
    def __init__(self, registry_path: Optional[str] = None):
        """
        Инициализация реестра
        
        Args:
            registry_path: Путь к файлу реестра (по умолчанию ./data/model_registry.json)
        """
        self.registry_path = registry_path or os.path.join(
            os.path.dirname(settings.rag_vector_db_path),
            "model_registry.json"
        )
        self.registry_dir = os.path.dirname(self.registry_path)
        os.makedirs(self.registry_dir, exist_ok=True)
        
        # Загрузка реестра
        self.registry: Dict[str, ModelMetadata] = self._load_registry()
    
    def _load_registry(self) -> Dict[str, ModelMetadata]:
        """Загрузка реестра из файла"""
        if not os.path.exists(self.registry_path):
            return {}
        
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            registry = {}
            for model_name, model_data in data.items():
                # Преобразование версий
                versions = [
                    ModelVersion(**version_data) for version_data in model_data.get('versions', [])
                ]
                # Преобразование дат
                model_data['created_at'] = datetime.fromisoformat(model_data['created_at'])
                model_data['updated_at'] = datetime.fromisoformat(model_data['updated_at'])
                model_data['versions'] = versions
                registry[model_name] = ModelMetadata(**model_data)
            
            return registry
        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            return {}
    
    def _save_registry(self):
        """Сохранение реестра в файл"""
        try:
            data = {}
            for model_name, model_metadata in self.registry.items():
                data[model_name] = model_metadata.dict()
            
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.debug(f"Registry saved to {self.registry_path}")
        except Exception as e:
            logger.error(f"Error saving registry: {e}")
            raise
    
    def register_model(
        self,
        model_name: str,
        model_type: ModelType,
        version: str,
        description: Optional[str] = None,
        status: ModelStatus = ModelStatus.DEVELOPMENT,
        created_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        mlflow_run_id: Optional[str] = None,
        performance_metrics: Optional[Dict[str, float]] = None,
        dependencies: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None
    ) -> ModelVersion:
        """
        Регистрация новой версии модели
        
        Args:
            model_name: Название модели
            model_type: Тип модели
            version: Версия (семантическое версионирование)
            description: Описание версии
            status: Статус версии
            created_by: Создатель версии
            metadata: Дополнительные метаданные
            mlflow_run_id: ID запуска MLflow
            performance_metrics: Метрики производительности
            dependencies: Зависимости
            tags: Теги модели
            
        Returns:
            ModelVersion: Зарегистрированная версия
        """
        # Создание версии
        model_version = ModelVersion(
            version=version,
            model_name=model_name,
            model_type=model_type,
            status=status,
            created_by=created_by,
            description=description,
            metadata=metadata or {},
            mlflow_run_id=mlflow_run_id,
            performance_metrics=performance_metrics or {},
            dependencies=dependencies or {}
        )
        
        # Добавление в реестр
        if model_name not in self.registry:
            self.registry[model_name] = ModelMetadata(
                model_name=model_name,
                model_type=model_type,
                current_version=version,
                description=description,
                tags=tags or []
            )
        else:
            # Обновление метаданных модели
            model_metadata = self.registry[model_name]
            model_metadata.updated_at = datetime.utcnow()
            if description:
                model_metadata.description = description
            if tags:
                model_metadata.tags = tags
        
        # Добавление версии
        self.registry[model_name].versions.append(model_version)
        self.registry[model_name].current_version = version
        
        # Сохранение
        self._save_registry()
        
        logger.info(f"Registered model {model_name} version {version}")
        return model_version
    
    def get_model(self, model_name: str) -> Optional[ModelMetadata]:
        """Получить метаданные модели"""
        return self.registry.get(model_name)
    
    def get_version(
        self,
        model_name: str,
        version: Optional[str] = None
    ) -> Optional[ModelVersion]:
        """
        Получить версию модели
        
        Args:
            model_name: Название модели
            version: Версия (если None, возвращается текущая)
            
        Returns:
            ModelVersion или None
        """
        if model_name not in self.registry:
            return None
        
        model_metadata = self.registry[model_name]
        
        if version is None:
            version = model_metadata.current_version
        
        for v in model_metadata.versions:
            if v.version == version:
                return v
        
        return None
    
    def list_models(self, model_type: Optional[ModelType] = None) -> List[str]:
        """
        Список моделей
        
        Args:
            model_type: Фильтр по типу модели
            
        Returns:
            Список названий моделей
        """
        if model_type is None:
            return list(self.registry.keys())
        
        return [
            name for name, metadata in self.registry.items()
            if metadata.model_type == model_type
        ]
    
    def list_versions(self, model_name: str) -> List[ModelVersion]:
        """Список версий модели"""
        if model_name not in self.registry:
            return []
        
        return self.registry[model_name].versions.copy()
    
    def set_current_version(self, model_name: str, version: str) -> bool:
        """
        Установить текущую версию модели
        
        Args:
            model_name: Название модели
            version: Версия для установки
            
        Returns:
            True если успешно, False если версия не найдена
        """
        if model_name not in self.registry:
            return False
        
        # Проверка существования версии
        if not self.get_version(model_name, version):
            return False
        
        self.registry[model_name].current_version = version
        self.registry[model_name].updated_at = datetime.utcnow()
        self._save_registry()
        
        logger.info(f"Set current version for {model_name} to {version}")
        return True
    
    def update_version_status(
        self,
        model_name: str,
        version: str,
        status: ModelStatus
    ) -> bool:
        """
        Обновить статус версии
        
        Args:
            model_name: Название модели
            version: Версия
            status: Новый статус
            
        Returns:
            True если успешно
        """
        model_version = self.get_version(model_name, version)
        if not model_version:
            return False
        
        model_version.status = status
        self._save_registry()
        
        logger.info(f"Updated status for {model_name} v{version} to {status}")
        return True
    
    def update_version_metrics(
        self,
        model_name: str,
        version: str,
        metrics: Dict[str, float]
    ) -> bool:
        """
        Обновить метрики версии
        
        Args:
            model_name: Название модели
            version: Версия
            metrics: Новые метрики
            
        Returns:
            True если успешно
        """
        model_version = self.get_version(model_name, version)
        if not model_version:
            return False
        
        model_version.performance_metrics.update(metrics)
        self._save_registry()
        
        logger.info(f"Updated metrics for {model_name} v{version}")
        return True

