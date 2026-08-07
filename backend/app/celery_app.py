"""Celery application configuration."""

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "echokey",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.transcribe"],
)
