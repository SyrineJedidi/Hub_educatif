from django.db.models import Q
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from accounts.views import SecureView, validated
from accounts.permissions import Administrator
from .models import LearningGroup, Enrollment
from .serializers import GroupSerializer, EnrollmentSerializer, EndEnrollmentSerializer, group_data, enrollment_data
from .services import get_object, groups_for, group_access, mutation, interval_query, paginated

class GroupsView(SecureView):
    def get(self, request):
        groups = groups_for(request.user).order_by('name', 'id')
        q = request.query_params.get('q', '')[:100]
        if q:
            groups = groups.filter(Q(name__icontains=q) | Q(code__icontains=q))
        archived = request.query_params.get('archived')
        if archived in ('true', 'false'):
            groups = groups.filter(archived=archived == 'true')
        return Response(paginated(request, groups, group_data))
    @mutation
    def post(self, request):
        if request.user.role != 'ADMIN':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Action réservée à l’administration.')
        data = validated(GroupSerializer, request)
        return Response(group_data(LearningGroup.objects.create(**data)), status=201)

class GroupDetailView(SecureView):
    def get(self, request, uid):
        group = get_object(LearningGroup, uid)
        group_access(request.user, group)
        return Response(group_data(group))
    @mutation
    def patch(self, request, uid):
        group = get_object(LearningGroup, uid)
        group_access(request.user, group, write=True)
        data = validated(GroupSerializer, request, instance=group)
        for key, value in data.items():
            setattr(group, key, value)
        group.save()
        return Response(group_data(group))
    @mutation
    def delete(self, request, uid):
        from attendance.models import LearningSession
        from quizzes.models import Quiz
        from assistant.models import TeacherNote
        from courses.models import CourseGroup
        group = get_object(LearningGroup, uid)
        group_access(request.user, group, write=True)
        if Enrollment.objects.filter(group=group).exists() or LearningSession.objects.filter(group=group).exists() or Quiz.objects.filter(learning_group=group).exists() or TeacherNote.objects.filter(group=group).exists() or CourseGroup.objects.filter(group=group).exists():
            raise ValidationError('Ce groupe possède un historique. Archivez-le.')
        group.delete()
        return Response(status=204)

class EnrollmentsView(SecureView):
    def get(self, request):
        entries = Enrollment.objects.filter(group_id__in=list(groups_for(request.user).values_list('id', flat=True)))
        if request.user.role == 'STUDENT':
            entries = entries.filter(student=request.user)
        if request.query_params.get('group'):
            group = get_object(LearningGroup, request.query_params['group'])
            group_access(request.user, group)
            entries = entries.filter(group=group)
        return Response(paginated(request, entries.order_by('-starts_at', 'id'), enrollment_data))
    @mutation
    def post(self, request):
        if not Administrator().has_permission(request, self):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Action réservée à l’administration.')
        data = validated(EnrollmentSerializer, request)
        return Response(enrollment_data(Enrollment.objects.create(**data)), status=201)

class EnrollmentDetailView(SecureView):
    permission_classes = [Administrator]
    @mutation
    def patch(self, request, uid):
        enrollment = get_object(Enrollment, uid)
        data = validated(EndEnrollmentSerializer, request)
        if enrollment.ends_at:
            raise ValidationError('Cette inscription est déjà terminée ; créez une nouvelle période.')
        if data['ends_at'] <= enrollment.starts_at:
            raise ValidationError('La sortie doit suivre l’entrée.')
        if Enrollment.objects.filter(group=enrollment.group, student=enrollment.student).exclude(pk=enrollment.pk).filter(interval_query(enrollment.starts_at, data['ends_at'])).exists():
            raise ValidationError('Chevauchement avec une autre période.')
        enrollment.ends_at = data['ends_at']
        enrollment.save()
        return Response(enrollment_data(enrollment))
