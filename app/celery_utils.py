from celery import Celery

from app.config import settings
from app.offline import enforce_offline

enforce_offline()
celery_app = Celery(
    "mydubber",
    broker=settings.redis_url,
    backend=settings.redis_result_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=5,
    broker_transport_options={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        # Long videos can run for hours. The Redis broker restores unacknowledged
        # messages after this timeout, so it must exceed the longest task.
        "visibility_timeout": settings.task_visibility_timeout,
    },
    redis_socket_connect_timeout=5,
    redis_socket_timeout=5,
    # The pipeline acknowledges tasks when the worker receives them, so a long
    # running job is never delivered twice. Progress is resumable from checkpoints.
    task_acks_late=False,
    task_reject_on_worker_lost=False,
    task_time_limit=None,
    task_soft_time_limit=None,
    result_expires=settings.result_expires,
    timezone="UTC",
    enable_utc=True,
)
