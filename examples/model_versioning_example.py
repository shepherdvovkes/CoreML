"""
Пример использования системы версионирования моделей
"""
import asyncio
from core.models.model_registry import ModelRegistry, ModelType, ModelStatus
from core.models.migration_service import MigrationService
from core.models.mlflow_integration import create_mlflow_integration


async def example_model_registry():
    """Пример работы с реестром моделей"""
    print("=" * 60)
    print("Пример работы с реестром моделей")
    print("=" * 60)
    
    # Инициализация реестра
    registry = ModelRegistry()
    
    # Регистрация новой версии модели эмбеддингов
    version1 = registry.register_model(
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        model_type=ModelType.EMBEDDING,
        version="1.0.0",
        description="Первая версия модели эмбеддингов",
        status=ModelStatus.PRODUCTION,
        created_by="admin",
        performance_metrics={
            "accuracy": 0.92,
            "latency_ms": 45.2
        },
        tags=["multilingual", "legal"]
    )
    print(f"Зарегистрирована версия: {version1.version}")
    
    # Регистрация новой версии
    version2 = registry.register_model(
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        model_type=ModelType.EMBEDDING,
        version="1.1.0",
        description="Улучшенная версия с оптимизацией",
        status=ModelStatus.STAGING,
        created_by="admin",
        performance_metrics={
            "accuracy": 0.94,
            "latency_ms": 38.5
        },
        dependencies={
            "sentence-transformers": "2.2.2"
        }
    )
    print(f"Зарегистрирована версия: {version2.version}")
    
    # Получение информации о модели
    model = registry.get_model("paraphrase-multilingual-MiniLM-L12-v2")
    print(f"\nТекущая версия модели: {model.current_version}")
    print(f"Всего версий: {len(model.versions)}")
    
    # Список всех версий
    versions = registry.list_versions("paraphrase-multilingual-MiniLM-L12-v2")
    print("\nВсе версии:")
    for v in versions:
        print(f"  - {v.version} ({v.status.value}) - {v.description}")
    
    # Установка текущей версии
    registry.set_current_version("paraphrase-multilingual-MiniLM-L12-v2", "1.1.0")
    print("\nТекущая версия установлена на 1.1.0")
    
    # Обновление статуса
    registry.update_version_status(
        "paraphrase-multilingual-MiniLM-L12-v2",
        "1.1.0",
        ModelStatus.PRODUCTION
    )
    print("Статус версии 1.1.0 обновлен на PRODUCTION")


def example_migration_service():
    """Пример работы с миграционным сервисом"""
    print("\n" + "=" * 60)
    print("Пример работы с миграционным сервисом")
    print("=" * 60)
    
    registry = ModelRegistry()
    migration_service = MigrationService(registry)
    
    # Регистрация стратегии миграции
    def migrate_1_0_to_1_1(data):
        """Миграция данных с версии 1.0.0 на 1.1.0"""
        # Пример миграции метаданных
        if isinstance(data, dict):
            data['migrated'] = True
            data['migration_version'] = '1.1.0'
        return data
    
    migration_service.register_strategy(
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        from_version="1.0.0",
        to_version="1.1.0",
        migration_fn=migrate_1_0_to_1_1,
        description="Миграция метаданных документов"
    )
    
    # Проверка возможности миграции
    can_migrate = migration_service.can_migrate(
        "paraphrase-multilingual-MiniLM-L12-v2",
        "1.0.0",
        "1.1.0"
    )
    print(f"Миграция возможна: {can_migrate}")
    
    # Выполнение миграции (dry run)
    test_data = {"version": "1.0.0", "content": "test"}
    migrated_data = migration_service.migrate(
        "paraphrase-multilingual-MiniLM-L12-v2",
        "1.0.0",
        "1.1.0",
        test_data,
        dry_run=True
    )
    print(f"Результат миграции (dry run): {migrated_data}")


def example_mlflow_integration():
    """Пример интеграции с MLflow"""
    print("\n" + "=" * 60)
    print("Пример интеграции с MLflow")
    print("=" * 60)
    
    mlflow_integration = create_mlflow_integration()
    
    if mlflow_integration is None:
        print("MLflow недоступен. Убедитесь, что MLflow установлен и запущен.")
        return
    
    # Начало нового запуска
    with mlflow_integration.start_run(
        run_name="embedding_model_v1.1.0",
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        model_version="1.1.0"
    ):
        # Логирование параметров
        mlflow_integration.log_model_params(
            model_name="paraphrase-multilingual-MiniLM-L12-v2",
            model_version="1.1.0",
            model_type="embedding",
            params={
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "top_k": 5
            }
        )
        
        # Логирование метрик
        mlflow_integration.log_metrics({
            "accuracy": 0.94,
            "latency_ms": 38.5,
            "throughput": 26.0
        })
        
        run_id = mlflow_integration.get_run_id()
        print(f"MLflow run ID: {run_id}")
        print("Параметры и метрики залогированы в MLflow")


if __name__ == "__main__":
    # Примеры использования
    asyncio.run(example_model_registry())
    example_migration_service()
    example_mlflow_integration()
    
    print("\n" + "=" * 60)
    print("Примеры завершены!")
    print("=" * 60)

