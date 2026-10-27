#!/bin/sh
# web: apply migrations, collect static files, then serve the API with gunicorn.
# worker: run the Celery worker that processes AI generations.
# courses-worker: extract and transcribe course resources (PDF, audio) queued by the courses module.
set -e
case "$1" in
  web)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput >/dev/null
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --threads "${GUNICORN_THREADS:-2}" \
      --timeout 120 \
      --access-logfile - \
      --forwarded-allow-ips "*"
    ;;
  worker)
    exec celery -A config worker --loglevel=info --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;
  courses-worker)
    exec python manage.py process_course_jobs --sleep "${COURSES_WORKER_SLEEP:-5}"
    ;;
  *)
    exec "$@"
    ;;
esac
