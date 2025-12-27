# Система версионирования моделей

## Обзор

Система версионирования моделей обеспечивает:
- Отслеживание версий моделей (эмбеддинги, LLM, reranker)
- Управление метаданными документов с версиями
- Миграцию между версиями моделей
- Интеграцию с MLflow для отслеживания экспериментов
- API для управления версиями

## Компоненты

### 1. Реестр моделей (ModelRegistry)

Реестр хранит информацию о всех версиях моделей и их метаданных.

**Основные возможности:**
- Регистрация новых версий моделей
- Управление текущей версией
- Отслеживание метрик производительности
- Хранение зависимостей и метаданных

**Пример использования:**

```python
from core.models.model_registry import ModelRegistry, ModelType, ModelStatus

registry = ModelRegistry()

# Регистрация новой версии
version = registry.register_model(
    model_name="paraphrase-multilingual-MiniLM-L12-v2",
    model_type=ModelType.EMBEDDING,
    version="1.0.0",
    description="Первая версия",
    status=ModelStatus.PRODUCTION,
    performance_metrics={"accuracy": 0.92}
)

# Получение информации о модели
model = registry.get_model("paraphrase-multilingual-MiniLM-L12-v2")
print(f"Текущая версия: {model.current_version}")

# Список версий
versions = registry.list_versions("paraphrase-multilingual-MiniLM-L12-v2")
```

### 2. Миграционный сервис (MigrationService)

Сервис для миграции данных между версиями моделей.

**Основные возможности:**
- Регистрация стратегий миграции
- Поиск пути миграции между версиями
- Выполнение миграции метаданных документов
- Поддержка dry-run режима

**Пример использования:**

```python
from core.models.migration_service import MigrationService

migration_service = MigrationService(registry)

# Регистрация стратегии миграции
def migrate_1_0_to_1_1(data):
    data['migration_version'] = '1.1.0'
    return data

migration_service.register_strategy(
    model_name="paraphrase-multilingual-MiniLM-L12-v2",
    from_version="1.0.0",
    to_version="1.1.0",
    migration_fn=migrate_1_0_to_1_1
)

# Выполнение миграции
migrated_data = migration_service.migrate(
    "paraphrase-multilingual-MiniLM-L12-v2",
    "1.0.0",
    "1.1.0",
    data
)
```

### 3. Интеграция с MLflow

Автоматическое отслеживание экспериментов и версий моделей в MLflow.

**Основные возможности:**
- Логирование параметров моделей
- Отслеживание метрик производительности
- Регистрация моделей в MLflow Model Registry
- Сохранение артефактов

**Пример использования:**

```python
from core.models.mlflow_integration import create_mlflow_integration

mlflow = create_mlflow_integration()

with mlflow.start_run(run_name="model_v1.1.0"):
    mlflow.log_model_params(
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        model_version="1.1.0",
        model_type="embedding",
        params={"chunk_size": 1000}
    )
    
    mlflow.log_metrics({
        "accuracy": 0.94,
        "latency_ms": 38.5
    })
```

### 4. Версионирование метаданных документов

Все документы в векторном хранилище автоматически получают метаданные о версии модели:

```python
{
    "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "embedding_model_version": "1.0.0",
    "indexed_at": "2024-01-15T10:30:00",
    "migration_history": [
        {
            "from_version": "1.0.0",
            "to_version": "1.1.0",
            "migrated_at": "2024-01-20T14:00:00"
        }
    ]
}
```

## API Endpoints

### Регистрация модели

```http
POST /models/register
Content-Type: application/json

{
    "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
    "model_type": "embedding",
    "version": "1.0.0",
    "description": "Первая версия",
    "status": "production",
    "performance_metrics": {
        "accuracy": 0.92
    }
}
```

### Список моделей

```http
GET /models?model_type=embedding
```

### Информация о модели

```http
GET /models/{model_name}
```

### Список версий

```http
GET /models/{model_name}/versions
```

### Установка текущей версии

```http
POST /models/{model_name}/versions/{version}/set-current
Content-Type: application/json

{
    "version": "1.1.0"
}
```

### Обновление статуса

```http
POST /models/{model_name}/versions/{version}/status
Content-Type: application/json

{
    "status": "production"
}
```

### Обновление метрик

```http
POST /models/{model_name}/versions/{version}/metrics
Content-Type: application/json

{
    "metrics": {
        "accuracy": 0.94,
        "latency_ms": 38.5
    }
}
```

### Миграция модели

```http
POST /models/{model_name}/migrate
Content-Type: application/json

{
    "from_version": "1.0.0",
    "to_version": "1.1.0",
    "dry_run": false
}
```

### Статус MLflow

```http
GET /mlflow/status
```

## Конфигурация

Настройки в `config.py`:

```python
# MLflow Configuration
mlflow_tracking_uri: str = "http://localhost:5000"
mlflow_experiment_name: str = "coreml_rag"

# Model Registry Configuration
model_registry_path: str = "./data/model_registry.json"
```

Или через переменные окружения:

```bash
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_EXPERIMENT_NAME=coreml_rag
MODEL_REGISTRY_PATH=./data/model_registry.json
```

## Типы моделей

- `embedding` - Модели эмбеддингов для RAG
- `llm` - Языковые модели
- `reranker` - Модели ранжирования

## Статусы версий

- `development` - В разработке
- `staging` - Тестирование
- `production` - Production версия
- `deprecated` - Устаревшая версия
- `archived` - Архивированная версия

## Семантическое версионирование

Используется формат `major.minor.patch`:
- `major` - Несовместимые изменения API
- `minor` - Новая функциональность с обратной совместимостью
- `patch` - Исправления ошибок

Примеры:
- `1.0.0` - Первая стабильная версия
- `1.1.0` - Добавлена новая функциональность
- `1.1.1` - Исправление ошибок
- `2.0.0` - Несовместимые изменения

## Миграция существующих документов

При добавлении документов через API автоматически добавляется версия модели:

```python
# В vector_store автоматически добавляется:
metadata['embedding_model_version'] = "1.0.0"
metadata['indexed_at'] = "2024-01-15T10:30:00"
```

## Интеграция с MLflow

1. Запустите MLflow tracking server:
```bash
mlflow ui --port 5000
```

2. Используйте интеграцию в коде:
```python
mlflow_integration = create_mlflow_integration()
```

3. Логируйте эксперименты:
```python
with mlflow_integration.start_run():
    mlflow_integration.log_metrics({"accuracy": 0.94})
```

## Примеры

См. `examples/model_versioning_example.py` для полных примеров использования.

## Лучшие практики

1. **Всегда регистрируйте новые версии** перед использованием в production
2. **Обновляйте метрики** после тестирования новой версии
3. **Используйте миграции** для обновления существующих данных
4. **Логируйте эксперименты** в MLflow для отслеживания изменений
5. **Тестируйте миграции** в dry-run режиме перед применением

## Troubleshooting

### MLflow недоступен

Если MLflow не установлен, система продолжит работать без интеграции. Установите:
```bash
pip install mlflow
```

### Ошибки миграции

Проверьте наличие стратегии миграции:
```python
can_migrate = migration_service.can_migrate(
    model_name, from_version, to_version
)
```

### Проблемы с реестром

Реестр сохраняется в JSON файл. Убедитесь, что директория существует и доступна для записи.

