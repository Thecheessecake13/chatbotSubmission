from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery('smart_document_qa', broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(task_track_started=True, worker_prefetch_multiplier=1, task_acks_late=True)

import app.tasks.document_tasks  # noqa: E402,F401
