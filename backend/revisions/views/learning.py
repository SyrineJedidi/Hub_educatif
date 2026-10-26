"""Revision with flashcards, reading follow-up and the module overview."""
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from accounts.views import validated
from classrooms.services import mutation
from ..ai.jobs import expire_stale
from ..services.learning import flashcards, tracked, progress_data, record_view, record_review, engagement
from ..models import AIJob, Illustration, SheetProgress
from ..serializers import ReviewSerializer, EmptyActionSerializer, job_data, sheet_list
from ..services import editable_sheets, readable_sheet, publication_blockers, facets
from .base import SheetView


class OverviewView(SheetView):
    """Figures and to-do list of the module home page."""
    def get(self, request):
        sheets = editable_sheets(request.user).select_related('owner', 'learning_group')
        to_review = sheets.filter(ai_generated=True, ai_reviewed=False).exclude(status='ARCHIVED').order_by('-updated_at', 'id')
        drafts = sheets.filter(status='DRAFT', learning_group__isnull=False).order_by('-updated_at', 'id')[:30]
        ready = [s for s in drafts if not publication_blockers(s)][:5]
        jobs = (AIJob.objects.all() if request.user.role == 'ADMIN' else AIJob.objects.filter(user=request.user)).select_related('user', 'illustration')
        running = list(jobs.filter(status__in=['QUEUED', 'RUNNING']))
        if expire_stale(running): running = list(jobs.filter(status__in=['QUEUED', 'RUNNING']))
        serialize = lambda items: sheet_list(list(items), request.user)
        illustrations = Illustration.objects.filter(sheet__in=sheets)
        return Response({
            'stats': facets(sheets)['stats'],
            'illustrations': {'total': illustrations.count(), 'ai': illustrations.filter(source='AI').count()},
            'to_review_count': to_review.count(),
            'to_review': serialize(to_review[:5]),
            'ready_to_publish': serialize(ready),
            'recent': serialize(sheets.order_by('-updated_at', 'id')[:6]),
            'running': [job_data(j, request.user) for j in running],
            'recent_jobs': [job_data(j, request.user) for j in jobs.order_by('-created_at', 'id')[:6]],
        })




class CardsView(SheetView):
    """Flashcards of a sheet, with the progress of the student who revises it."""
    def get(self, request, uid):
        sheet = readable_sheet(request.user, uid)
        cards = flashcards(sheet)
        progress = SheetProgress.objects.filter(sheet=sheet, student=request.user).first() if tracked(request.user, sheet) else None
        return Response({'cards': cards, 'tracked': tracked(request.user, sheet), 'progress': progress_data(progress, cards)})




class ReadView(SheetView):
    """A student opened a sheet shared by their teacher: the teacher sees who read it."""
    @mutation
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        sheet = readable_sheet(request.user, uid)
        if not tracked(request.user, sheet): return Response(status=204)
        return Response(progress_data(record_view(request.user, sheet), flashcards(sheet)))




class ReviewView(SheetView):
    """End of a flashcard session: the cards the student knows are saved."""
    @mutation
    def post(self, request, uid):
        known = validated(ReviewSerializer, request)['known']
        sheet = readable_sheet(request.user, uid)
        if not tracked(request.user, sheet):
            # Teachers and personal sheets: a training session, nothing to record.
            ids = {c['id'] for c in flashcards(sheet)}
            kept = [k for k in dict.fromkeys(known) if k in ids]
            return Response({'saved': False, 'known': kept, 'mastery': round(len(kept) / len(ids), 3) if ids else None})
        return Response({'saved': True, **record_review(request.user, sheet, known)})




class EngagementView(SheetView):
    """Who read and revised each published sheet (teacher: own sheets, administrator: all)."""
    def get(self, request):
        if request.user.role == 'STUDENT': raise NotFound('Ressource introuvable.')
        return Response({'results': engagement(editable_sheets(request.user))})
