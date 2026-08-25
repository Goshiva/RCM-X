from __future__ import annotations

import os
from celery import Celery

from backend.app.core.config import DATABASE_URL

REDIS_BROKER_URL = os.getenv('REDIS_BROKER_URL', '')
CELERY_BACKEND = os.getenv('CELERY_BACKEND', REDIS_BROKER_URL or 'rpc://')

def make_celery(app_name: str = 'risk_adjustment') -> Celery:
    broker = REDIS_BROKER_URL or None
    celery = Celery(app_name, broker=broker, backend=CELERY_BACKEND)

    # In development without a broker, run tasks eagerly for local testing
    if not broker:
        celery.conf.task_always_eager = True
        celery.conf.task_eager_propagates = True

    celery.conf.update({
        'task_serializer': 'json',
        'result_serializer': 'json',
        'accept_content': ['json'],
    })

    return celery

celery_app = make_celery()
