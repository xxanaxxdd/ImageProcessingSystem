import os
from celery import Celery

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://192.168.32.129:6379/0")
WORKER_THREADS = int(os.environ.get("WORKER_THREADS", 4))

print(f"[celery_worker] BROKER_URL = {BROKER_URL}")
print(f"[celery_worker] WORKER_THREADS = {WORKER_THREADS}")

celery = Celery(
    "worker",
    broker=BROKER_URL,
    backend=BROKER_URL,
    include=["worker.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
