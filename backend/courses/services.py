from bson import ObjectId
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError
from django.db.models import F, Q
from django.utils import timezone
from django_mongodb_backend import transaction
from rest_framework.exceptions import APIException, NotFound, ValidationError
from accounts.models import User
from classrooms.models import Enrollment, LearningGroup
from classrooms.services import get_object
from .models import Chapter, Course, CourseGroup, ProcessingJob, Resource, ResourceSegment, ResourceView, Subject
from .serializers import AdminCourseWriteSerializer, CourseWriteSerializer, course_groups
from .signals import course_content_changed

FIELD_NAMES = {'subject': 'subject_id', 'teacher': 'teacher_id', 'chapter': 'chapter_id', 'course': 'course_id', 'name_key': 'name'}


class ProcessingInProgress(APIException):
    status_code = 409
    default_detail = 'Un traitement est déjà en cours pour cette ressource.'
    default_code = 'processing_in_progress'


def model_errors(instance):
    try: instance.full_clean(validate_unique=False, validate_constraints=False)
    except ModelValidationError as exc:
        errors = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
        raise ValidationError({FIELD_NAMES.get(k, k): v for k, v in errors.items()})


def current_group_ids(student, at=None):
    now = at or timezone.now()
    ids = list(Enrollment.objects.filter(student=student, starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('group_id', flat=True))
    return list(LearningGroup.objects.filter(pk__in=ids, archived=False).values_list('id', flat=True))


def visible_courses(user, *, at=None):
    """Single source of truth for who may read which course."""
    if not user.is_authenticated or not user.is_active: return Course.objects.none()
    if user.role == 'ADMIN': return Course.objects.all()
    if user.role == 'TEACHER': return Course.objects.filter(teacher=user)
    course_ids = list(CourseGroup.objects.filter(group_id__in=current_group_ids(user, at)).values_list('course_id', flat=True))
    return Course.objects.filter(pk__in=course_ids, status=Course.Status.PUBLISHED)


def get_visible_course(user, course_id):
    if not ObjectId.is_valid(str(course_id)): raise NotFound('Cours introuvable.')
    course = visible_courses(user).filter(pk=ObjectId(str(course_id))).first()
    if not course: raise NotFound('Cours introuvable.')
    return course


def course_outline(course_id):
    return [{'chapter_id': str(c.pk), 'title': c.title, 'position': c.position} for c in Chapter.objects.filter(course_id=ObjectId(str(course_id)))]


def course_segments(course_id):
    course_id = ObjectId(str(course_id))
    chapters = list(Chapter.objects.filter(course_id=course_id))
    resources = list(Resource.objects.filter(course_id=course_id, processing_status=Resource.ProcessingStatus.READY))
    for chapter in chapters:
        for resource in [r for r in resources if r.chapter_id == chapter.pk]:
            for segment in ResourceSegment.objects.filter(resource=resource).order_by('order'):
                yield {'resource_id': str(resource.pk), 'resource_title': resource.title, 'kind': resource.kind,
                    'chapter_id': str(chapter.pk), 'chapter_title': chapter.title, 'order': segment.order, 'text': segment.text,
                    'page': segment.page, 'start_seconds': segment.start_seconds, 'end_seconds': segment.end_seconds}


def course_content_version(course_id):
    version = Course.objects.filter(pk=ObjectId(str(course_id))).values_list('content_version', flat=True).first() if ObjectId.is_valid(str(course_id)) else None
    if version is None: raise NotFound('Cours introuvable.')
    return str(version)


def resource_url(course_id, resource_id, *, page=None, start_seconds=None):
    url = f'/espace/cours/{course_id}/ressources/{resource_id}'
    if page: return f'{url}?page={int(page)}'
    if start_seconds is not None: return f'{url}?t={int(start_seconds)}'
    return url


def content_changed(course_id, reason, resource_id=None):
    Course.objects.filter(pk=course_id).update(content_version=F('content_version') + 1, updated_at=timezone.now())
    payload = {'course_id': str(course_id), 'resource_id': str(resource_id) if resource_id else None, 'reason': reason}
    transaction.on_commit(lambda: course_content_changed.send(sender=Course, **payload), robust=True)


def manager_courses(user):
    return Course.objects.all() if user.role == 'ADMIN' else Course.objects.filter(teacher=user)


def managed_course(user, uid):
    try: course = get_object(Course, uid)
    except NotFound: raise NotFound('Cours introuvable.')
    if user.role != 'ADMIN' and course.teacher_id != user.pk: raise NotFound('Cours introuvable.')
    return course


def editable(course):
    if course.status == Course.Status.ARCHIVED:
        raise ValidationError({'status': ['Ce cours est archivé. Restaurez-le pour le modifier.']})


def chapter_for(course, uid):
    try: chapter = get_object(Chapter, uid)
    except NotFound: chapter = None
    if not chapter or chapter.course_id != course.pk: raise NotFound('Chapitre introuvable dans ce cours.')
    return chapter


def resource_for(course, uid):
    try: resource = get_object(Resource, uid)
    except NotFound: resource = None
    if not resource or resource.course_id != course.pk: raise NotFound('Ressource introuvable dans ce cours.')
    return resource


def segment_for(resource, uid):
    try: segment = get_object(ResourceSegment, uid)
    except NotFound: segment = None
    if not segment or segment.resource_id != resource.pk: raise NotFound('Extrait introuvable dans cette ressource.')
    return segment


def body_chapter(course, uid):
    """Chapter referenced in a request body: a wrong id is a field error, not a 404."""
    try: return chapter_for(course, uid)
    except NotFound: raise ValidationError({'chapter_id': ['Sélectionnez un chapitre de ce cours.']})


def next_position(queryset):
    last = queryset.order_by('-position').first()
    return last.position + 1 if last else 1


def compact_positions(queryset):
    # Ascending order keeps every intermediate state valid for the unique position index.
    for position, item in enumerate(queryset.order_by('position', 'id'), 1):
        if item.position != position:
            item.position = position; item.save(update_fields=['position', 'updated_at'])


def reorder(items, ids, field, message):
    """Mirror of the quiz reorder: park every item on a free position first, so no step breaks the unique index."""
    if len(ids) != len(set(ids)) or set(ids) != {str(i.pk) for i in items}:
        raise ValidationError({field: [message]})
    if ids == [str(i.pk) for i in sorted(items, key=lambda i: (i.position, str(i.pk)))]: return False
    by_id = {str(i.pk): i for i in items}
    occupied = {i.position for i in items}; temporary = len(items) + 1
    for item in items:
        while temporary in occupied: temporary += 1
        item.position = temporary; item.save(update_fields=['position', 'updated_at']); occupied.add(temporary); temporary += 1
    for position, uid in enumerate(ids, 1):
        item = by_id[uid]; item.position = position; item.save(update_fields=['position', 'updated_at'])
    return True


def subject_for_course(uid):
    try: return get_object(Subject, uid)
    except NotFound: raise ValidationError({'subject_id': ['Sélectionnez une matière existante.']})


def validated_groups(ids, teacher):
    groups, errors = [], []
    for uid in ids:
        try: group = get_object(LearningGroup, uid)
        except NotFound:
            errors.append('Sélectionnez des groupes existants.'); continue
        if group.archived: errors.append(f'Le groupe « {group.name} » est archivé.')
        elif group.teacher_id != teacher.pk: errors.append(f'Le groupe « {group.name} » doit être affecté à l’enseignant du cours.')
        groups.append(group)
    if errors: raise ValidationError({'group_ids': list(dict.fromkeys(errors))})
    return groups


def course_values(request, data, instance=None):
    """Validate a create or partial update; returns the course (unsaved changes applied) and the groups or None."""
    cls = AdminCourseWriteSerializer if request.user.role == 'ADMIN' else CourseWriteSerializer
    serializer = cls(data=data, partial=bool(instance))
    serializer.is_valid(raise_exception=True)
    attrs = dict(serializer.validated_data)
    previous_teacher_id = instance.teacher_id if instance else None
    course = instance or Course()
    if 'teacher_id' in attrs:
        try: course.teacher = get_object(User, attrs.pop('teacher_id'))
        except NotFound: raise ValidationError({'teacher_id': ['Sélectionnez un enseignant actif existant.']})
    elif not instance:
        course.teacher = request.user
    if 'subject_id' in attrs: course.subject = subject_for_course(attrs.pop('subject_id'))
    for field in ('title', 'description'):
        if field in attrs: setattr(course, field, attrs[field])
    model_errors(course)
    ids = attrs.get('group_ids')
    if ids is None and instance and course.teacher_id != previous_teacher_id:
        ids = [str(g) for g in CourseGroup.objects.filter(course=instance).values_list('group_id', flat=True)]
    if ids is None: return course, (None if instance else [])
    groups = validated_groups(ids, course.teacher)
    if course.status == Course.Status.PUBLISHED and not groups:
        raise ValidationError({'group_ids': ['Un cours publié doit rester partagé avec au moins un groupe.']})
    return course, groups


def replace_groups(course, groups):
    current = set(CourseGroup.objects.filter(course=course).values_list('group_id', flat=True))
    wanted = {g.pk for g in groups}
    if current == wanted: return False
    CourseGroup.objects.filter(course=course, group_id__in=list(current - wanted)).delete()
    for group in groups:
        if group.pk not in current: CourseGroup.objects.create(course=course, group=group)
    return True


def publication_blockers(course):
    reasons = []
    labels = {'title': 'Titre', 'description': 'Description', 'teacher_id': 'Enseignant', 'subject_id': 'Matière'}
    try: model_errors(course)
    except ValidationError as exc:
        for field, messages in exc.detail.items():
            reasons.extend(f'{labels.get(field, field)} : {message}' for message in messages)
    if course.subject.archived: reasons.append(f'Matière : la matière « {course.subject.name} » est archivée.')
    if not any(not g.archived and g.teacher_id == course.teacher_id for g in course_groups(course)):
        reasons.append('Partagez le cours avec au moins un groupe actif de l’enseignant.')
    if not Chapter.objects.filter(course=course).exists(): reasons.append('Ajoutez au moins un chapitre avant de publier.')
    if not Resource.objects.filter(course=course).exists(): reasons.append('Ajoutez au moins une ressource avant de publier.')
    return reasons


def status_filter(request, queryset, parameter, choices):
    value = request.query_params.get(parameter)
    if not value: return queryset
    if value not in choices: raise ValidationError({parameter: ['Sélectionnez une valeur autorisée.']})
    return queryset.filter(**{parameter: value})


def filtered_courses(request, queryset):
    q = request.query_params.get('q', '').strip()[:150]
    if q: queryset = queryset.filter(title__icontains=q)
    queryset = status_filter(request, queryset, 'status', Course.Status.values)
    if request.query_params.get('subject'):
        queryset = queryset.filter(subject=get_object(Subject, request.query_params['subject']))
    if request.query_params.get('group'):
        group = get_object(LearningGroup, request.query_params['group'])
        queryset = queryset.filter(pk__in=list(CourseGroup.objects.filter(group=group).values_list('course_id', flat=True)))
    if request.user.role == 'ADMIN' and request.query_params.get('teacher'):
        queryset = queryset.filter(teacher=get_object(User, request.query_params['teacher']))
    return queryset


def page_number(request):
    try: return max(1, int(request.query_params.get('page', 1)))
    except ValueError: raise ValidationError({'page': ['Page invalide.']})


def paged_list(request, items, serialize):
    page = page_number(request)
    return {'count': len(items), 'page': page, 'page_size': 20, 'results': [serialize(i) for i in items[(page - 1) * 20:page * 20]]}


def student_progress(student, course):
    total = Resource.objects.filter(course=course).count()
    viewed = ResourceView.objects.filter(student=student, course=course).count()
    return {'viewed': viewed, 'total': total, 'percent': round(100 * viewed / total) if total else 0}


def record_view(student, course, resource):
    now = timezone.now()
    views = ResourceView.objects.filter(student=student, resource=resource)
    if not views.update(view_count=F('view_count') + 1, last_viewed_at=now):
        try: ResourceView.objects.create(student=student, resource=resource, course=course, first_viewed_at=now, last_viewed_at=now)
        except IntegrityError: views.update(view_count=F('view_count') + 1, last_viewed_at=now)
    return views.get()


def delete_resources(resources):
    """Explicit single-collection deletes; stored files are removed only once the transaction has committed."""
    ids = [r.pk for r in resources]
    ResourceView.objects.filter(resource_id__in=ids).delete()
    ResourceSegment.objects.filter(resource_id__in=ids).delete()
    ProcessingJob.objects.filter(resource_id__in=ids).delete()
    Resource.objects.filter(pk__in=ids).delete()
    names = [r.file.name for r in resources if r.file.name]
    if names:
        storage = resources[0].file.storage
        transaction.on_commit(lambda: [storage.delete(name) for name in names], robust=True)
