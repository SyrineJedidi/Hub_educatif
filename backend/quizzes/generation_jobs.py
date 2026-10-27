"""Question generation in the background.

The request validates the input and records a QuestionGenerationJob (202 Accepted); the call to
Ollama, often 30 s or more, runs elsewhere and the page polls the job. Same backends as the AI jobs
of the revision sheets (AI_JOB_BACKEND): ``celery`` in production, ``thread`` without a broker,
``sync`` for automated tests.
"""
import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from .generation import generate_questions
from .models import QuestionGenerationJob

logger = logging.getLogger(__name__)
_pool = None
Status = QuestionGenerationJob.Status


def dispatch(job):
    backend = settings.AI_JOB_BACKEND
    if backend == 'sync':
        return run_generation_job(job.pk)
    if backend == 'celery':
        try:
            from .tasks import run_question_generation
            run_question_generation.delay(str(job.pk))
            return
        except Exception:  # Broker unreachable: keep the feature working in-process.
            logger.warning('Celery indisponible, génération de questions %s dans un thread.', job.pk, exc_info=True)
    global _pool
    if _pool is None: _pool = ThreadPoolExecutor(max_workers=settings.AI_JOB_WORKERS, thread_name_prefix='quiz-generation')
    _pool.submit(_run_in_thread, job.pk)


def _run_in_thread(job_id):
    try: run_generation_job(job_id)
    finally: close_old_connections()


def proposal_metrics(inputs, proposals):
    """Quality indicators of one generation, kept without the course or the questions themselves."""
    statements = [' '.join(p['statement'].split()).casefold() for p in proposals]
    return {
        'requested': inputs.get('count'), 'returned': len(proposals), 'level': inputs.get('level'),
        'distinct_statements': len(set(statements)),
        'answers': dict(sorted(Counter(p['correct_answer'] for p in proposals).items())),
        'notions': len({p['notion'].casefold() for p in proposals if p.get('notion')}),
        'explanation_chars': round(sum(len(p['explanation']) for p in proposals) / len(proposals)) if proposals else 0,
    }


def failure(status, code, message, fields=None):
    return {'status': Status.FAILED, 'error_status': status, 'error_code': code[:40], 'error_message': message[:500],
            'error_fields': fields or {}}


def run_generation_job(job_id):
    if not QuestionGenerationJob.objects.filter(pk=job_id, status=Status.QUEUED).update(status=Status.RUNNING, started_at=timezone.now()):
        return
    job = QuestionGenerationJob.objects.select_related('quiz').get(pk=job_id)
    started = time.monotonic()
    metrics = {'model': str(settings.OLLAMA_MODEL)[:80], 'course_characters': len(job.inputs.get('course_text', ''))}
    try:
        proposals = generate_questions(job.quiz, job.inputs)
        fields = {'status': Status.SUCCEEDED, 'proposals': proposals}
        metrics.update(proposal_metrics(job.inputs, proposals))
    except ValidationError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {'non_field_errors': exc.detail}
        errors = {key: [str(m) for m in (value if isinstance(value, list) else [value])] for key, value in detail.items()}
        fields = failure(400, 'invalid', next(iter(errors.values()))[0], errors)
    except APIException as exc:
        fields = failure(exc.status_code, str(exc.get_codes()), str(exc.detail))
    except Exception:
        logger.exception('Échec imprévu de la génération de questions %s', job_id)
        fields = failure(503, 'generation_failed', 'La génération a échoué. Réessayez plus tard.')
    metrics['latency_ms'] = int((time.monotonic() - started) * 1000)
    # The course is not kept once the model has read it.
    inputs = {key: value for key, value in job.inputs.items() if key != 'course_text'}
    QuestionGenerationJob.objects.filter(pk=job_id).update(inputs=inputs, metrics=metrics, finished_at=timezone.now(), **fields)


def expire_stale(job):
    """A job abandoned by a stopped worker ends in a clear failure instead of waiting forever."""
    limit = float(settings.OLLAMA_TIMEOUT_SECONDS) + 120
    if job.status in (Status.QUEUED, Status.RUNNING) and job.created_at < timezone.now() - timedelta(seconds=limit):
        QuestionGenerationJob.objects.filter(pk=job.pk, status=job.status).update(
            inputs={}, finished_at=timezone.now(), **failure(504, 'generation_expired', 'La génération n’a pas abouti dans le délai prévu. Relancez-la.'))
        job.refresh_from_db()
    return job


def job_data(job, questions=None):
    data = {'id': str(job.pk), 'status': job.status, 'status_label': job.get_status_display(),
            'created_at': job.created_at, 'started_at': job.started_at, 'finished_at': job.finished_at,
            'latency_ms': job.metrics.get('latency_ms'), 'delivered': job.delivered}
    if job.status == Status.FAILED:
        data['error'] = {'code': job.error_code, 'message': job.error_message, 'status': job.error_status, 'fields': job.error_fields}
    if questions is not None:
        data['questions'] = questions
    return data
