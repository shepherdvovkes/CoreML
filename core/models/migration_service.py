"""
Сервис для миграции между версиями моделей
"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from loguru import logger
from .model_registry import ModelRegistry, ModelVersion, ModelType, ModelStatus


class MigrationStrategy:
    """Стратегия миграции между версиями"""
    
    def __init__(
        self,
        from_version: str,
        to_version: str,
        migration_fn: Callable[[Any], Any],
        description: Optional[str] = None
    ):
        self.from_version = from_version
        self.to_version = to_version
        self.migration_fn = migration_fn
        self.description = description or f"Migration from {from_version} to {to_version}"


class MigrationService:
    """Сервис для миграции между версиями моделей"""
    
    def __init__(self, registry: ModelRegistry):
        """
        Инициализация сервиса миграции
        
        Args:
            registry: Реестр моделей
        """
        self.registry = registry
        self.strategies: Dict[str, List[MigrationStrategy]] = {}
    
    def register_strategy(
        self,
        model_name: str,
        from_version: str,
        to_version: str,
        migration_fn: Callable[[Any], Any],
        description: Optional[str] = None
    ):
        """
        Регистрация стратегии миграции
        
        Args:
            model_name: Название модели
            from_version: Исходная версия
            to_version: Целевая версия
            migration_fn: Функция миграции
            description: Описание миграции
        """
        if model_name not in self.strategies:
            self.strategies[model_name] = []
        
        strategy = MigrationStrategy(from_version, to_version, migration_fn, description)
        self.strategies[model_name].append(strategy)
        
        logger.info(f"Registered migration strategy for {model_name}: {from_version} -> {to_version}")
    
    def find_migration_path(
        self,
        model_name: str,
        from_version: str,
        to_version: str
    ) -> List[MigrationStrategy]:
        """
        Поиск пути миграции между версиями
        
        Args:
            model_name: Название модели
            from_version: Исходная версия
            to_version: Целевая версия
            
        Returns:
            Список стратегий миграции
        """
        if model_name not in self.strategies:
            return []
        
        # Простой поиск прямого пути
        # В реальной системе можно использовать граф версий для поиска оптимального пути
        strategies = self.strategies[model_name]
        
        # Прямая миграция
        direct = [
            s for s in strategies
            if s.from_version == from_version and s.to_version == to_version
        ]
        if direct:
            return direct
        
        # Поиск через промежуточные версии (упрощенный алгоритм)
        # В production нужен более сложный алгоритм поиска пути
        path = []
        current_version = from_version
        
        # Получаем все версии модели
        versions = self.registry.list_versions(model_name)
        version_list = [v.version for v in sorted(versions, key=lambda v: v.created_at)]
        
        # Простая стратегия: миграция через последовательные версии
        if from_version in version_list and to_version in version_list:
            from_idx = version_list.index(from_version)
            to_idx = version_list.index(to_version)
            
            if from_idx < to_idx:
                # Миграция вперед
                for i in range(from_idx, to_idx):
                    next_version = version_list[i + 1]
                    strategy = [
                        s for s in strategies
                        if s.from_version == version_list[i] and s.to_version == next_version
                    ]
                    if strategy:
                        path.extend(strategy)
                    else:
                        logger.warning(
                            f"No migration strategy found for {model_name}: "
                            f"{version_list[i]} -> {next_version}"
                        )
                        return []
            elif from_idx > to_idx:
                # Миграция назад (rollback)
                for i in range(from_idx, to_idx, -1):
                    prev_version = version_list[i - 1]
                    strategy = [
                        s for s in strategies
                        if s.from_version == version_list[i] and s.to_version == prev_version
                    ]
                    if strategy:
                        path.extend(strategy)
                    else:
                        logger.warning(
                            f"No migration strategy found for {model_name}: "
                            f"{version_list[i]} -> {prev_version}"
                        )
                        return []
        
        return path
    
    def migrate(
        self,
        model_name: str,
        from_version: str,
        to_version: str,
        data: Any,
        dry_run: bool = False
    ) -> Any:
        """
        Выполнить миграцию данных
        
        Args:
            model_name: Название модели
            from_version: Исходная версия
            to_version: Целевая версия
            data: Данные для миграции
            dry_run: Если True, только проверка без выполнения
            
        Returns:
            Мигрированные данные
        """
        if from_version == to_version:
            logger.info(f"No migration needed: {from_version} == {to_version}")
            return data
        
        path = self.find_migration_path(model_name, from_version, to_version)
        
        if not path:
            logger.warning(
                f"No migration path found for {model_name}: {from_version} -> {to_version}"
            )
            if not dry_run:
                raise ValueError(
                    f"Cannot migrate {model_name} from {from_version} to {to_version}: "
                    "no migration path found"
                )
            return data
        
        logger.info(
            f"Migrating {model_name} from {from_version} to {to_version} "
            f"({len(path)} steps, dry_run={dry_run})"
        )
        
        migrated_data = data
        
        for i, strategy in enumerate(path):
            logger.info(
                f"Migration step {i+1}/{len(path)}: "
                f"{strategy.from_version} -> {strategy.to_version}"
            )
            
            if not dry_run:
                try:
                    migrated_data = strategy.migration_fn(migrated_data)
                except Exception as e:
                    logger.error(f"Migration step failed: {e}")
                    raise
        
        return migrated_data
    
    def migrate_documents_metadata(
        self,
        model_name: str,
        from_version: str,
        to_version: str,
        documents_metadata: List[Dict[str, Any]],
        dry_run: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Миграция метаданных документов
        
        Args:
            model_name: Название модели
            from_version: Исходная версия
            to_version: Целевая версия
            documents_metadata: Список метаданных документов
            dry_run: Если True, только проверка
            
        Returns:
            Мигрированные метаданные
        """
        migrated = []
        
        for doc_metadata in documents_metadata:
            # Добавление информации о миграции
            if not dry_run:
                import json
                # migration_history хранится как JSON строка для совместимости с ChromaDB
                if 'migration_history' not in doc_metadata:
                    migration_history = []
                elif isinstance(doc_metadata['migration_history'], str):
                    try:
                        migration_history = json.loads(doc_metadata['migration_history'])
                    except (json.JSONDecodeError, TypeError):
                        migration_history = []
                else:
                    migration_history = list(doc_metadata['migration_history'])
                
                migration_history.append({
                    'from_version': from_version,
                    'to_version': to_version,
                    'migrated_at': datetime.utcnow().isoformat(),
                    'model_name': model_name
                })
                
                # Сохраняем как JSON строку
                doc_metadata['migration_history'] = json.dumps(migration_history)
            
            # Обновление версии модели в метаданных
            doc_metadata['model_version'] = to_version
            doc_metadata['model_name'] = model_name
            
            migrated.append(doc_metadata)
        
        return migrated
    
    def can_migrate(
        self,
        model_name: str,
        from_version: str,
        to_version: str
    ) -> bool:
        """
        Проверка возможности миграции
        
        Args:
            model_name: Название модели
            from_version: Исходная версия
            to_version: Целевая версия
            
        Returns:
            True если миграция возможна
        """
        if from_version == to_version:
            return True
        
        path = self.find_migration_path(model_name, from_version, to_version)
        return len(path) > 0

