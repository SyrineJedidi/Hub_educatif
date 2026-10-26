"""AI generations: start a job, follow it, rate it, and monitor the engines."""
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from accounts.services import limit
from accounts.views import validated
from classrooms.services import paginated, get_object
from django.conf import settings
from ..ai.jobs import dispatch, expire_stale
from ..ai.metrics import dashboard
from ..models import AIJob, RevisionSheet, Illustration, MAX_ILLUSTRATIONS
from ..serializers import GenerateSummarySerializer, IllustrationGenerateSerializer, RatingSerializer, job_data
from ..services import editable_sheet, not_archived, extract_text
from .base import SheetView


def check_generation(sheet):
    not_archived(sheet)
    if sheet.status == 'PUBLISHED':
        raise ValidationError({'status': ['Repassez la fiche en brouillon pour générer un nouveau contenu : il devra être relu avant d’être partagé.']})




def job_response(request, job, status=202):
    dispatch(job)
    job.refresh_from_db()
    return Response(job_data(job, request.user), status=status)




class GenerateSummaryView(SheetView):
    parser_classes = [JSONParser, MultiPartParser]

    def post(self, request, uid):
        sheet = editable_sheet(request.user, uid)
        check_generation(sheet)
        data = validated(GenerateSummarySerializer, request)
        text = extract_text(data['file']) if data.get('file') else data['source_text'].strip()
        if AIJob.objects.filter(sheet=sheet, kind='SUMMARY', status__in=['QUEUED', 'RUNNING']).exists():
            raise ValidationError({'status': ['Une génération de résumé est déjà en cours pour cette fiche.']})
        limit(request, 'ai-summary', maximum=20, seconds=3600, identity=str(request.user.pk))
        # The slow AI call is processed in the background; the client follows the job.
        job = AIJob.objects.create(kind='SUMMARY', sheet=sheet, sheet_title=sheet.title, user=request.user, source_text=text,
            source_name=data['file'].name[:255] if data.get('file') else 'Texte collé',
            params={'length': data['length'], 'course': sheet.course_label, 'source_characters': len(text)})
        return job_response(request, job)




class GenerateIllustrationView(SheetView):
    def post(self, request, uid):
        sheet = editable_sheet(request.user, uid); not_archived(sheet)
        data = validated(IllustrationGenerateSerializer, request)
        pending = AIJob.objects.filter(sheet=sheet, kind='ILLUSTRATION', status__in=['QUEUED', 'RUNNING']).count()
        if Illustration.objects.filter(sheet=sheet).count() + pending >= MAX_ILLUSTRATIONS:
            raise ValidationError({'image': [f'Une fiche contient au plus {MAX_ILLUSTRATIONS} illustrations.']})
        limit(request, 'ai-illustration', maximum=12, seconds=3600, identity=str(request.user.pk))
        job = AIJob.objects.create(kind='ILLUSTRATION', sheet=sheet, sheet_title=sheet.title, user=request.user, params=dict(data))
        return job_response(request, job)




class SheetJobsView(SheetView):
    def get(self, request, uid):
        sheet = editable_sheet(request.user, uid)
        jobs = list(AIJob.objects.filter(sheet=sheet)[:20])
        if expire_stale(jobs): jobs = list(AIJob.objects.filter(sheet=sheet)[:20])
        return Response({'results': [job_data(j, request.user) for j in jobs]})




def visible_job(user, uid):
    job = get_object(AIJob, uid)
    if user.role != 'ADMIN' and job.user_id != user.pk: raise NotFound('Génération introuvable.')
    return job




class JobDetailView(SheetView):
    def get(self, request, uid):
        job = visible_job(request.user, uid)
        if expire_stale([job]): job.refresh_from_db()
        return Response(job_data(job, request.user))




class JobRatingView(SheetView):
    def post(self, request, uid):
        job = visible_job(request.user, uid)
        if job.user_id != request.user.pk: raise NotFound('Génération introuvable.')
        if job.status != 'SUCCEEDED': raise ValidationError({'rating': ['Seule une génération réussie peut être évaluée.']})
        job.rating = validated(RatingSerializer, request)['rating']
        job.save(update_fields=['rating'])
        return Response(job_data(job, request.user))




class AIStatusView(SheetView):
    def get(self, request):
        # What the interface can offer; never exposes keys.
        summary = bool(settings.GEMINI_API_KEY or settings.OLLAMA_MODEL)
        return Response({
            'summary': summary, 'illustration': bool(settings.HF_TOKEN),
            'summary_engine': f'Gemini · {settings.GEMINI_MODEL}' if settings.GEMINI_API_KEY else (f'Ollama · {settings.OLLAMA_MODEL}' if settings.OLLAMA_MODEL else None),
            'fallback_engine': f'Ollama · {settings.OLLAMA_MODEL}' if settings.GEMINI_API_KEY and settings.OLLAMA_MODEL else None,
            'illustration_engine': f'Hugging Face · {(settings.HF_IMAGE_SPACE or settings.HF_IMAGE_MODEL).split("/")[-1]}' if settings.HF_TOKEN else None,
            'asynchronous': settings.AI_JOB_BACKEND != 'sync',
            'job_backend': {'celery': 'Celery + Redis', 'thread': 'File de tâches intégrée', 'sync': 'Synchrone'}.get(settings.AI_JOB_BACKEND, settings.AI_JOB_BACKEND),
        })




class MetricsView(SheetView):
    def get(self, request):
        if request.user.role == 'STUDENT': raise NotFound('Ressource introuvable.')
        try: days = min(365, max(1, int(request.query_params.get('days', 30))))
        except ValueError: raise ValidationError({'days': ['Période invalide.']})
        jobs, sheets = AIJob.objects.all(), RevisionSheet.objects.all()
        if request.user.role != 'ADMIN':
            jobs, sheets = jobs.filter(user=request.user), sheets.filter(owner=request.user)
        recent = list(jobs.select_related('user', 'illustration').order_by('-created_at', 'id')[:15])
        if expire_stale(recent): recent = list(jobs.order_by('-created_at', 'id')[:15])
        data = dashboard(jobs, sheets, days)
        data['recent'] = [job_data(j, request.user) for j in recent]
        data['configuration'] = {
            'job_backend': settings.AI_JOB_BACKEND,
            'gemini_model': settings.GEMINI_MODEL if settings.GEMINI_API_KEY else None,
            'ollama_model': settings.OLLAMA_MODEL or None,
            'image_model': (settings.HF_IMAGE_SPACE or settings.HF_IMAGE_MODEL) if settings.HF_TOKEN else None,
        }
        return Response(data)




class JobsView(SheetView):
    """Journal of AI generations: the administrator sees everything, the others their own."""
    def get(self, request):
        jobs = (AIJob.objects.all() if request.user.role == 'ADMIN' else AIJob.objects.filter(user=request.user)).select_related('user', 'illustration')
        params = request.query_params
        if params.get('kind'):
            if params['kind'] not in ('SUMMARY', 'ILLUSTRATION'): raise ValidationError({'kind': ['Type invalide.']})
            jobs = jobs.filter(kind=params['kind'])
        if params.get('status'):
            if params['status'] not in AIJob.Status.values: raise ValidationError({'status': ['Statut invalide.']})
            jobs = jobs.filter(status=params['status'])
        expire_stale(list(jobs.filter(status__in=['QUEUED', 'RUNNING'])))
        return Response(paginated(request, jobs.order_by('-created_at', 'id'), lambda j: job_data(j, request.user)))
