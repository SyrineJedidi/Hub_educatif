from functools import wraps
from bson import ObjectId
from django.db import DatabaseError
from django.db.models import F, Q
from django_mongodb_backend import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, APIException
from accounts.models import AdminGuard, User
from .models import LearningGroup, Enrollment

class Conflict(APIException):
    status_code = 409
    default_detail = 'Modification concurrente. Rechargez les données puis réessayez.'
    default_code = 'conflict'

def mutation(function):
    @wraps(function)
    def wrapped(self, request, *args, **kwargs):
        AdminGuard.objects.get_or_create(key='accounts')
        for attempt in range(3):
            try:
                with transaction.atomic():
                    # One shared guard prevents write skew across roles, periods and sessions.
                    AdminGuard.objects.filter(key='accounts').update(revision=F('revision') + 1)
                    actor = User.objects.get(pk=request.user.pk)
                    if not actor.is_active or actor.role != request.user.role:
                        raise PermissionDenied('Vos droits ont changé. Reconnectez-vous.')
                    return function(self, request, *args, **kwargs)
            except DatabaseError:
                if attempt == 2:
                    raise Conflict()
    return wrapped

def get_object(model, uid):
    if not ObjectId.is_valid(str(uid)):
        raise NotFound('Ressource introuvable.')
    try:
        return model.objects.get(pk=ObjectId(str(uid)))
    except model.DoesNotExist:
        raise NotFound('Ressource introuvable.')

def groups_for(user):
    groups = LearningGroup.objects.all()
    if user.role == 'TEACHER':
        return groups.filter(teacher=user)
    if user.role == 'STUDENT':
        ids = list(Enrollment.objects.filter(student=user).values_list('group_id', flat=True))
        return groups.filter(pk__in=ids)
    return groups

def group_access(user, group, write=False):
    if user.role == 'ADMIN' or (user.role == 'TEACHER' and group.teacher_id == user.pk and not write):
        return
    if not write and user.role == 'STUDENT' and Enrollment.objects.filter(group=group, student=user).exists():
        return
    raise PermissionDenied('Accès à ce groupe refusé.')

def interval_query(start, end):
    query = Q(ends_at__isnull=True) | Q(ends_at__gt=start)
    if end:
        query &= Q(starts_at__lt=end)
    return query

def paginated(request, queryset, serialize):
    from rest_framework.exceptions import ValidationError
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except ValueError:
        raise ValidationError({'page': ['Page invalide.']})
    return {'count': queryset.count(), 'page': page, 'page_size': 20,
            'results': [serialize(item) for item in queryset[(page-1)*20:page*20]]}
