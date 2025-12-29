"""
Конфигурация Celery для фоновых задач
"""
from celery import Celery
from config import settings
from loguru import logger

# Создание экземпляра Celery
celery_app = Celery(
    "coreml_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["core.tasks"]
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    # Оптимизация для production
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    # Retry настройки
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Результаты
    result_expires=3600,  # 1 hour
    # Мониторинг
    worker_send_task_events=True,
    task_send_sent_event=True,
)

logger.info(f"Celery configured with broker: {settings.celery_broker_url}")



