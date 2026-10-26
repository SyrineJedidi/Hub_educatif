# Django API and Celery worker of the Hub Éducatif (same image, different commands).
# Build context: the repository root (see docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_MEDIA_ROOT=/data/media \
    DJANGO_STATIC_ROOT=/app/staticfiles

WORKDIR /app
COPY backend/requirements.lock .
RUN pip install -r requirements.lock

COPY backend/ .
COPY deploy/backend/entrypoint.sh /entrypoint.sh
# Runs as an unprivileged user; uploaded illustrations live in a volume.
RUN useradd --create-home --uid 1000 nexora \
    && mkdir -p /data/media /app/staticfiles \
    && chown -R nexora /data /app
USER nexora

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/health/').status != 200)"
ENTRYPOINT ["sh", "/entrypoint.sh"]
CMD ["web"]
