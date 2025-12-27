"""
Интеграция с MLflow для отслеживания экспериментов
"""
import os
from typing import Dict, Optional, Any
from loguru import logger

try:
    import mlflow
    import mlflow.sklearn
    import mlflow.pytorch
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not available. Install with: pip install mlflow")


class MLflowIntegration:
    """Интеграция с MLflow для отслеживания экспериментов"""
    
    def __init__(self, tracking_uri: Optional[str] = None, experiment_name: str = "coreml_rag"):
        """
        Инициализация интеграции с MLflow
        
        Args:
            tracking_uri: URI для MLflow tracking server (по умолчанию локальный)
            experiment_name: Название эксперимента
        """
        if not MLFLOW_AVAILABLE:
            raise ImportError("MLflow is not installed. Install with: pip install mlflow")
        
        self.tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(self.tracking_uri)
        
        self.experiment_name = experiment_name
        self.experiment = mlflow.get_experiment_by_name(experiment_name)
        
        if self.experiment is None:
            self.experiment_id = mlflow.create_experiment(experiment_name)
            logger.info(f"Created MLflow experiment: {experiment_name}")
        else:
            self.experiment_id = self.experiment.experiment_id
            logger.info(f"Using existing MLflow experiment: {experiment_name}")
    
    def start_run(
        self,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> mlflow.ActiveRun:
        """
        Начать новый запуск
        
        Args:
            run_name: Название запуска
            tags: Теги для запуска
            model_name: Название модели
            model_version: Версия модели
            
        Returns:
            Активный запуск MLflow
        """
        mlflow.set_experiment(self.experiment_name)
        
        tags = tags or {}
        if model_name:
            tags["model_name"] = model_name
        if model_version:
            tags["model_version"] = model_version
        
        return mlflow.start_run(run_name=run_name, tags=tags)
    
    def log_model_params(
        self,
        model_name: str,
        model_version: str,
        model_type: str,
        params: Dict[str, Any]
    ):
        """
        Логирование параметров модели
        
        Args:
            model_name: Название модели
            model_version: Версия модели
            model_type: Тип модели
            params: Параметры модели
        """
        mlflow.log_params({
            "model_name": model_name,
            "model_version": model_version,
            "model_type": model_type,
            **params
        })
    
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """
        Логирование метрик
        
        Args:
            metrics: Словарь метрик
            step: Шаг (для временных рядов)
        """
        mlflow.log_metrics(metrics, step=step)
    
    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """
        Логирование артефакта
        
        Args:
            local_path: Локальный путь к файлу
            artifact_path: Путь в MLflow
        """
        mlflow.log_artifact(local_path, artifact_path)
    
    def log_model(
        self,
        model: Any,
        artifact_path: str = "model",
        registered_model_name: Optional[str] = None
    ):
        """
        Логирование модели
        
        Args:
            model: Модель для логирования
            artifact_path: Путь для сохранения модели
            registered_model_name: Название зарегистрированной модели
        """
        # Определение типа модели и использование соответствующего метода
        if hasattr(model, 'save'):
            # PyTorch модель
            mlflow.pytorch.log_model(model, artifact_path, registered_model_name=registered_model_name)
        elif hasattr(model, 'save_pretrained'):
            # HuggingFace модель
            mlflow.pytorch.log_model(model, artifact_path, registered_model_name=registered_model_name)
        else:
            # Общий случай - сохранение как pickle
            import pickle
            import tempfile
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
                pickle.dump(model, f)
                temp_path = f.name
            
            mlflow.log_artifact(temp_path, artifact_path)
            os.unlink(temp_path)
    
    def register_model_version(
        self,
        model_name: str,
        model_version: str,
        run_id: str,
        artifact_path: str = "model"
    ) -> str:
        """
        Регистрация версии модели в MLflow Model Registry
        
        Args:
            model_name: Название модели
            model_version: Версия модели
            run_id: ID запуска
            artifact_path: Путь к модели в артефактах
            
        Returns:
            Версия зарегистрированной модели
        """
        model_uri = f"runs:/{run_id}/{artifact_path}"
        mv = mlflow.register_model(model_uri, model_name)
        
        logger.info(
            f"Registered model {model_name} version {mv.version} "
            f"(requested version: {model_version})"
        )
        
        return mv.version
    
    def get_run_id(self) -> Optional[str]:
        """Получить ID текущего запуска"""
        active_run = mlflow.active_run()
        if active_run:
            return active_run.info.run_id
        return None
    
    @staticmethod
    def end_run():
        """Завершить текущий запуск"""
        mlflow.end_run()


def create_mlflow_integration(
    tracking_uri: Optional[str] = None,
    experiment_name: str = "coreml_rag"
) -> Optional[MLflowIntegration]:
    """
    Создать интеграцию с MLflow (если доступна)
    
    Args:
        tracking_uri: URI для MLflow tracking server
        experiment_name: Название эксперимента
        
    Returns:
        MLflowIntegration или None если MLflow недоступен
    """
    if not MLFLOW_AVAILABLE:
        logger.warning("MLflow not available, skipping integration")
        return None
    
    try:
        return MLflowIntegration(tracking_uri, experiment_name)
    except Exception as e:
        logger.error(f"Failed to initialize MLflow integration: {e}")
        return None

