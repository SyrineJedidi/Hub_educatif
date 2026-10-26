try:
    # Celery is optional: without it, AI jobs run in an in-process thread pool.
    from .celery import app as celery_app
except ImportError:  # pragma: no cover
    celery_app = None
