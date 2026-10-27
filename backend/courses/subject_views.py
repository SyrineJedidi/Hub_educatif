from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from accounts.views import SecureView
from classrooms.services import get_object, mutation, paginated
from .models import Course, Subject, normalized_text
from .permissions import CourseManager
from .serializers import SubjectUpdateSerializer, SubjectWriteSerializer, subject_data
from .services import model_errors


def subject_values(request, subject=None):
    serializer = (SubjectUpdateSerializer if subject else SubjectWriteSerializer)(data=request.data, partial=bool(subject))
    serializer.is_valid(raise_exception=True)
    subject = subject or Subject(created_by=request.user)
    for field, value in serializer.validated_data.items():
        setattr(subject, field, value.upper() if field == 'code' else value)
    subject.name_key = normalized_text(subject.name)[:80]
    model_errors(subject)
    others = Subject.objects.exclude(pk=subject.pk) if subject.pk else Subject.objects.all()
    if others.filter(name_key=subject.name_key).exists(): raise ValidationError({'name': ['Une matière porte déjà ce nom.']})
    if others.filter(code=subject.code).exists(): raise ValidationError({'code': ['Ce code est déjà utilisé.']})
    return subject


def editable_subject(request, uid):
    subject = get_object(Subject, uid)
    if request.user.role != 'ADMIN' and subject.created_by_id != request.user.pk:
        raise PermissionDenied('Seuls l’auteur de cette matière et l’administrateur peuvent la modifier.')
    return subject


class SubjectView(SecureView):
    permission_classes = [CourseManager]


class SubjectsView(SubjectView):
    def get(self, request):
        subjects = Subject.objects.all()
        q = request.query_params.get('q', '').strip()[:100]
        if q: subjects = subjects.filter(Q(name_key__icontains=normalized_text(q)) | Q(code__icontains=q))
        archived = request.query_params.get('archived')
        if archived in ('true', 'false'): subjects = subjects.filter(archived=archived == 'true')
        return Response(paginated(request, subjects.order_by('name_key', 'id'), lambda s: subject_data(s, request.user)))
    @mutation
    def post(self, request):
        subject = subject_values(request); subject.save()
        return Response(subject_data(subject, request.user), status=201)


class SubjectDetailView(SubjectView):
    def get(self, request, uid):
        return Response(subject_data(get_object(Subject, uid), request.user))
    @mutation
    def patch(self, request, uid):
        subject = subject_values(request, editable_subject(request, uid)); subject.save()
        return Response(subject_data(subject, request.user))
    @mutation
    def delete(self, request, uid):
        subject = editable_subject(request, uid)
        if Course.objects.filter(subject=subject).exists():
            raise ValidationError({'detail': 'Cette matière est utilisée par des cours : archivez-la plutôt.'})
        subject.delete()
        return Response(status=204)
