"""
Celery configuration.

Locally: runs in EAGER mode (tasks execute synchronously in-process).
Production: uses Redis as broker when CELERY_TASK_ALWAYS_EAGER is false.

The task code is identical in both environments.
"""
from celery import Celery
from app.core.config import settings


# Create Celery app
celery_app = Celery(
    "ecommerce_analytics",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.analytics_tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Local dev: run tasks synchronously, no worker needed
    task_always_eager=True,
    task_eager_propagates=True,
)