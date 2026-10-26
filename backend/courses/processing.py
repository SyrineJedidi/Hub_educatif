import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import timedelta
import pypdf
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django_mongodb_backend import transaction
from ai.transcription import TranscriptionError, get_transcriber
from .models import ProcessingJob, Resource, ResourceSegment, SEGMENT_MAX_LENGTH, normalized_text
from .services import content_changed

logger = logging.getLogger('courses')
MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(seconds=60)
STALE_AFTER = timedelta(minutes=15)
GENERIC_ERROR = 'Le traitement a échoué. Réessayez plus tard.'
SCANNED_PDF = 'Ce PDF semble numérisé : aucun texte exploitable. Il reste consultable mais n’est pas indexé.'
NO_SPEECH = 'Aucune parole détectée dans cet enregistrement.'
DELETED = 'La ressource a été supprimée pendant le traitement.'


@dataclass
class Result:
    segments: list = field(default_factory=list)
    empty_message: str = ''
    provider: str = ''
    model_name: str = ''
    audio_seconds: float | None = None
    language: str = ''


def job_kind(resource):
    return ProcessingJob.Kind.EXTRACT_PDF if resource.kind == Resource.Kind.PDF else ProcessingJob.Kind.TRANSCRIBE_AUDIO


def clean_text(text):
    """Collapse spaces inside lines and keep at most one blank line between paragraphs."""
    text = ''.join(c if c in '\n\r\t' or unicodedata.category(c)[0] != 'C' else ' ' for c in text)
    lines = [' '.join(line.split()) for line in text.splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def extract_pdf(resource):
    segments = []
    with resource.file.storage.open(resource.file.name, 'rb') as handle:
        reader = pypdf.PdfReader(handle)
        if reader.is_encrypted: reader.decrypt('')
        pages = len(reader.pages)
        for number, page in enumerate(reader.pages, 1):
            try: text = clean_text(page.extract_text() or '')
            except Exception:
                logger.warning('Unreadable page %s in resource %s', number, resource.pk, exc_info=True)
                text = ''
            if text: segments.append({'text': text[:SEGMENT_MAX_LENGTH], 'page': number})
    model = f'pypdf {pypdf.__version__}'
    # Scanned documents usually yield a few stray characters per page, not real text.
    if sum(len(s['text']) for s in segments) < 20 * max(pages, 1):
        return Result([], SCANNED_PDF, 'pypdf', model)
    return Result(segments, '', 'pypdf', model)


def transcribe_audio(resource):
    transcript = get_transcriber().transcribe(resource.file.path, language=settings.WHISPER_LANGUAGE or None)
    segments = [{'text': s.text.strip()[:SEGMENT_MAX_LENGTH], 'start_seconds': round(s.start, 3), 'end_seconds': round(s.end, 3)}
        for s in transcript.segments if s.text.strip()]
    return Result(segments, NO_SPEECH, transcript.provider, transcript.model, transcript.duration, transcript.language)


def claim(job_id=None, worker=''):
    """Compare-and-swap PENDING -> RUNNING, so two workers never process the same job."""
    now = timezone.now()
    available = ProcessingJob.objects.filter(status=ProcessingJob.Status.PENDING, active=True, available_at__lte=now)
    ids = [job_id] if job_id else list(available.order_by('created_at', 'id').values_list('id', flat=True)[:20])
    for pk in ids:
        if available.filter(pk=pk).update(status=ProcessingJob.Status.RUNNING, attempts=F('attempts') + 1, started_at=now, worker=worker[:80]):
            job = ProcessingJob.objects.get(pk=pk)
            Resource.objects.filter(pk=job.resource_id).update(processing_status=Resource.ProcessingStatus.PROCESSING, updated_at=now)
            return job
    return None


def retry_or_fail(job, message, retryable, processing_ms=None):
    now = timezone.now()
    message = message[:300]
    claimed = ProcessingJob.objects.filter(pk=job.pk, status=ProcessingJob.Status.RUNNING, attempts=job.attempts)
    with transaction.atomic():
        if retryable and job.attempts < MAX_ATTEMPTS:
            if claimed.update(status=ProcessingJob.Status.PENDING, available_at=now + RETRY_DELAY * job.attempts, error=message, processing_ms=processing_ms, worker=''):
                Resource.objects.filter(pk=job.resource_id).update(processing_status=Resource.ProcessingStatus.PENDING, updated_at=now)
        elif claimed.update(status=ProcessingJob.Status.FAILED, active=False, error=message, processing_ms=processing_ms, finished_at=now):
            Resource.objects.filter(pk=job.resource_id).update(processing_status=Resource.ProcessingStatus.FAILED, processing_error=message, updated_at=now)


def save_result(job, result, processing_ms):
    now = timezone.now()
    with transaction.atomic():
        resource = Resource.objects.filter(pk=job.resource_id).first()
        claimed = ProcessingJob.objects.filter(pk=job.pk, status=ProcessingJob.Status.RUNNING, attempts=job.attempts)
        if resource is None:
            claimed.update(status=ProcessingJob.Status.FAILED, active=False, error=DELETED, processing_ms=processing_ms, finished_at=now)
            return
        # A stale-recovered job may have been claimed again by another worker meanwhile.
        if not claimed.update(status=ProcessingJob.Status.DONE, active=False, error='', provider=result.provider[:30], model_name=result.model_name[:80],
                audio_seconds=result.audio_seconds, processing_ms=processing_ms, segments_count=len(result.segments), finished_at=now):
            return
        ResourceSegment.objects.filter(resource=resource).delete()
        ResourceSegment.objects.bulk_create([ResourceSegment(resource=resource, course_id=resource.course_id, chapter_id=resource.chapter_id,
            order=order, text=s['text'], search_text=normalized_text(s['text']), page=s.get('page'),
            start_seconds=s.get('start_seconds'), end_seconds=s.get('end_seconds')) for order, s in enumerate(result.segments, 1)])
        values = {'processing_status': Resource.ProcessingStatus.READY if result.segments else Resource.ProcessingStatus.NO_TEXT,
            'processing_error': '' if result.segments else result.empty_message, 'text_version': F('text_version') + 1, 'updated_at': now}
        if job.kind == ProcessingJob.Kind.TRANSCRIBE_AUDIO:
            values.update(duration_seconds=result.audio_seconds, language=(result.language or '')[:8])
        Resource.objects.filter(pk=resource.pk).update(**values)
        content_changed(resource.course_id, 'resource_processed', resource.pk)


def run(job):
    """Process a claimed job. Providers are called outside any transaction; only the short write phase is atomic."""
    started = time.monotonic()
    def elapsed(): return int((time.monotonic() - started) * 1000)
    resource = Resource.objects.filter(pk=job.resource_id).first()
    try:
        if resource is None: raise TranscriptionError(DELETED)
        result = extract_pdf(resource) if job.kind == ProcessingJob.Kind.EXTRACT_PDF else transcribe_audio(resource)
        save_result(job, result, elapsed())
    except TranscriptionError as exc:
        retry_or_fail(job, exc.message, exc.retryable, elapsed())
    except Exception:
        logger.exception('Processing job %s failed', job.pk)
        retry_or_fail(job, GENERIC_ERROR, True, elapsed())
    # None when the resource, and therefore the job, was deleted meanwhile.
    return ProcessingJob.objects.filter(pk=job.pk).first()


def recover_stale(now=None):
    """Jobs left RUNNING by a crashed or killed worker go back to the queue."""
    cutoff = (now or timezone.now()) - STALE_AFTER
    recovered = 0
    for job in ProcessingJob.objects.filter(status=ProcessingJob.Status.RUNNING, started_at__lt=cutoff):
        retry_or_fail(job, GENERIC_ERROR, True); recovered += 1
    return recovered


def process_now(job):
    """Inline processing right after the request's transaction has committed."""
    claimed = claim(job_id=job.pk, worker=f'inline-{os.getpid()}')
    return run(claimed) if claimed else None


def should_process_inline(resource):
    return resource.kind == Resource.Kind.PDF or settings.COURSES_PROCESS_INLINE
