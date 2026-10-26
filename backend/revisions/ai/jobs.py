"""Background processing of AI generations.

The HTTP request only validates the input and records an AIJob (202 Accepted); the slow
call to Gemini / Hugging Face runs elsewhere and the client polls the job. Backends:

- ``celery``: a Celery worker fed by Redis (``CELERY_BROKER_URL``) — production setup;
- ``thread``: an in-process thread pool — zero-infrastructure default for development;
- ``sync``: inline execution — automated tests only.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.conf import settings
from django.db import DatabaseError, close_old_connections
from django.db.models import F
from django.utils import timezone
from django_mongodb_backend import transaction
from rest_framework.exceptions import APIException, ValidationError
from accounts.models import AdminGuard
from .clients import generate_summary, hf_illustration
from .metrics import summary_quality
from ..models import AIJob, Illustration, RevisionSheet, MAX_ILLUSTRATIONS
from ..services import normalized_image, store_image, next_position, remove_files

logger = logging.getLogger(__name__)
_pool = None


class JobAborted(Exception):
    """The sheet changed while the AI was working; the result is discarded."""


def dispatch(job):
    backend = settings.AI_JOB_BACKEND
    if backend == 'sync':
        return run_job(job.pk)
    if backend == 'celery':
        try:
            from ..tasks import run_ai_job
            run_ai_job.delay(str(job.pk))
            return
        except Exception:  # Broker unreachable: keep the feature working in-process.
            logger.warning('Celery indisponible, exécution de la tâche IA %s dans un thread.', job.pk, exc_info=True)
    global _pool
    if _pool is None: _pool = ThreadPoolExecutor(max_workers=settings.AI_JOB_WORKERS, thread_name_prefix='ai-job')
    _pool.submit(_run_in_thread, job.pk)


def _run_in_thread(job_id):
    try: run_job(job_id)
    finally: close_old_connections()


def _guarded(write):
    """Run ``write`` in a transaction holding the shared guard, like every other mutation."""
    AdminGuard.objects.get_or_create(key='accounts')
    for attempt in range(3):
        try:
            with transaction.atomic():
                AdminGuard.objects.filter(key='accounts').update(revision=F('revision') + 1)
                return write()
        except DatabaseError:
            if attempt == 2: raise


def run_job(job_id):
    job = AIJob.objects.filter(pk=job_id, status=AIJob.Status.QUEUED).first()
    if not job: return
    now = timezone.now()
    AIJob.objects.filter(pk=job.pk).update(status=AIJob.Status.RUNNING, started_at=now,
                                           queue_ms=int((now - job.created_at).total_seconds() * 1000))
    job.refresh_from_db()
    started = timezone.now()
    try:
        (_summary if job.kind == AIJob.Kind.SUMMARY else _illustration)(job)
        job.status = AIJob.Status.SUCCEEDED
    except (APIException, ValidationError, JobAborted) as exc:
        job.status, job.error = AIJob.Status.FAILED, _message(exc)
    except Exception:
        logger.exception('Tâche IA %s en échec', job.pk)
        job.status, job.error = AIJob.Status.FAILED, 'Erreur interne pendant la génération. Réessayez.'
    job.finished_at = timezone.now()
    job.duration_ms = int((job.finished_at - started).total_seconds() * 1000)
    job.source_text = ''  # Course content is not kept once processed.
    job.save()


def _message(exc):
    detail = getattr(exc, 'detail', None) or str(exc)
    if isinstance(detail, dict): detail = next(iter(detail.values()))
    if isinstance(detail, list): detail = detail[0]
    return str(detail)[:500]


def _summary(job):
    params = job.params
    result = generate_summary(job.source_text, title=job.sheet_title, course=params['course'], length=params['length'])
    job.engine = 'ollama' if result['model'].startswith('ollama/') else 'gemini'
    job.model, job.fallback = result['model'], result.get('fallback', False)
    job.metrics = summary_quality(job.source_text, result, params['length'])

    def write():
        sheet = RevisionSheet.objects.filter(pk=job.sheet_id).first()
        if not sheet or sheet.status != RevisionSheet.Status.DRAFT:
            raise JobAborted('La fiche a été publiée, archivée ou supprimée pendant la génération : le résultat n’a pas été appliqué.')
        sheet.summary, sheet.key_points, sheet.glossary = result['summary'], result['key_points'], result['glossary']
        sheet.tags = list(dict.fromkeys(sheet.tags + result['tags']))[:8]
        sheet.illustration_prompt = result['illustration_prompt']
        sheet.ai_generated, sheet.ai_reviewed, sheet.ai_model = True, False, result['model']
        sheet.generated_at, sheet.source_name = timezone.now(), job.source_name
        sheet.save()
    _guarded(write)


def _illustration(job):
    params = job.params
    raw, model, _ = hf_illustration(params['prompt'], params['style'])
    job.engine, job.model = 'huggingface', model
    content, width, height = normalized_image(raw, max_bytes=20 * 1024 * 1024)
    name = store_image(content)

    def write():
        sheet = RevisionSheet.objects.filter(pk=job.sheet_id).first()
        if not sheet or sheet.status == RevisionSheet.Status.ARCHIVED:
            raise JobAborted('La fiche a été archivée ou supprimée pendant la génération.')
        if Illustration.objects.filter(sheet=sheet).count() >= MAX_ILLUSTRATIONS:
            raise JobAborted(f'La fiche contient déjà {MAX_ILLUSTRATIONS} illustrations.')
        illustration = Illustration.objects.create(sheet=sheet, image=name, caption=params['caption'], prompt=params['prompt'],
            source='AI', ai_model=model, width=width, height=height, position=next_position(sheet))
        sheet.save(update_fields=['updated_at'])
        return illustration
    try:
        job.illustration = _guarded(write)
    except Exception:
        remove_files([name])
        raise


def expire_stale(jobs):
    """Mark jobs interrupted by a server restart (thread backend) as failed."""
    limit = timezone.now() - timedelta(seconds=max(settings.AI_TIMEOUT_SECONDS, settings.OLLAMA_TIMEOUT_SECONDS) * 2 + 60)
    stale = [j.pk for j in jobs if j.status in (AIJob.Status.QUEUED, AIJob.Status.RUNNING) and j.created_at < limit]
    if stale:
        AIJob.objects.filter(pk__in=stale, status__in=[AIJob.Status.QUEUED, AIJob.Status.RUNNING]).update(
            status=AIJob.Status.FAILED, error='Génération interrompue (redémarrage du serveur). Relancez-la.',
            finished_at=timezone.now(), source_text='')
    return bool(stale)
