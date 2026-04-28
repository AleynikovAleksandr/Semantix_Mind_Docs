import os
from celery import Celery

broker = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

celery_app = Celery(
    "doc_processor",
    broker=broker,
    backend=backend,
    include=["worker.orchestrator"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    # Таймауты: задача не зависает вечно
    task_soft_time_limit=600,   # 10 мин — soft (ловим SoftTimeLimitExceeded)
    task_time_limit=660,        # 11 мин — hard kill
)
