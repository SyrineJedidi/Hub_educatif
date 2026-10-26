from collections.abc import Mapping
import re
from rest_framework import serializers
from accounts.serializers import StrictSerializer
from .models import Chapter, Course, CourseGroup, ProcessingJob, Resource, ResourceSegment, SEGMENT_MAX_LENGTH

MAX_COURSE_GROUPS = 20


class CourseInputSerializer(StrictSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping): raise serializers.ValidationError({'non_field_errors': ['Envoyez un objet JSON.']})
        return super().to_internal_value(data)


class CourseTextField(serializers.CharField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'blank': 'Ce champ est obligatoire et ne peut pas contenir uniquement des espaces.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez un texte valide.',
        'max_length': 'Limitez ce champ à {max_length} caractères.',
    }

    def to_internal_value(self, data):
        if not isinstance(data, str): self.fail('invalid')
        return super().to_internal_value(data)


class CourseBooleanField(serializers.BooleanField):
    default_error_messages = {'required': 'Ce champ est obligatoire.', 'null': 'Ce champ ne peut pas être vide.', 'invalid': 'Envoyez true ou false.'}

    def to_internal_value(self, data):
        if not isinstance(data, bool): self.fail('invalid')
        return data


class CourseReferenceField(CourseTextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(r'[0-9a-fA-F]{24}', value):
            raise serializers.ValidationError('Sélectionnez une valeur existante dans la liste.')
        return value


class CourseReferenceListField(serializers.ListField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'null': 'Ce champ ne peut pas être vide.',
        'not_a_list': 'Envoyez une liste d’identifiants.',
        'empty': 'Sélectionnez au moins un élément.',
        'max_length': 'Sélectionnez au plus {max_length} éléments.',
    }

    def __init__(self, **kwargs):
        super().__init__(child=CourseReferenceField(), **kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, list): self.fail('not_a_list', input_type=type(data).__name__)
        return list(dict.fromkeys(super().to_internal_value(data)))


class CourseFileField(serializers.FileField):
    default_error_messages = {
        'required': 'Choisissez un fichier.',
        'null': 'Choisissez un fichier.',
        'invalid': 'Envoyez un fichier.',
        'no_name': 'Le nom du fichier est introuvable.',
        'empty': 'Le fichier est vide.',
        'max_length': 'Le nom du fichier est trop long.',
    }


class SubjectWriteSerializer(CourseInputSerializer):
    name = CourseTextField(max_length=80)
    code = CourseTextField(max_length=20)
    description = CourseTextField(max_length=1000, required=False, allow_blank=True)

class SubjectUpdateSerializer(SubjectWriteSerializer):
    archived = CourseBooleanField(required=False)

class CourseWriteSerializer(CourseInputSerializer):
    title = CourseTextField(max_length=120)
    description = CourseTextField(max_length=2000)
    subject_id = CourseReferenceField()
    group_ids = CourseReferenceListField(required=False, max_length=MAX_COURSE_GROUPS)

class AdminCourseWriteSerializer(CourseWriteSerializer):
    teacher_id = CourseReferenceField()

class ChapterWriteSerializer(CourseInputSerializer):
    title = CourseTextField(max_length=120)
    description = CourseTextField(max_length=1000, required=False, allow_blank=True)

class ChapterReorderSerializer(CourseInputSerializer):
    chapter_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)

class ResourceReorderSerializer(CourseInputSerializer):
    resource_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)

class ResourceUploadSerializer(CourseInputSerializer):
    chapter_id = CourseReferenceField()
    title = CourseTextField(max_length=120)
    description = CourseTextField(max_length=1000, required=False, allow_blank=True)
    file = CourseFileField()

class ResourceUpdateSerializer(CourseInputSerializer):
    chapter_id = CourseReferenceField()
    title = CourseTextField(max_length=120)
    description = CourseTextField(max_length=1000, allow_blank=True)

class SegmentUpdateSerializer(CourseInputSerializer):
    text = CourseTextField(max_length=SEGMENT_MAX_LENGTH)

class EmptyActionSerializer(CourseInputSerializer):
    pass


def person_data(user):
    return {'id': str(user.pk), 'first_name': user.first_name, 'last_name': user.last_name}

def subject_short(subject):
    return {'id': str(subject.pk), 'name': subject.name, 'code': subject.code}

def subject_data(subject, user):
    return {**subject_short(subject), 'description': subject.description, 'archived': subject.archived,
        'created_by': person_data(subject.created_by), 'courses_count': Course.objects.filter(subject=subject).count(),
        'can_edit': user.role == 'ADMIN' or subject.created_by_id == user.pk,
        'created_at': subject.created_at, 'updated_at': subject.updated_at}

def group_short(group):
    return {'id': str(group.pk), 'name': group.name, 'code': group.code, 'archived': group.archived}

def job_data(job):
    return {'status': job.status, 'status_label': job.get_status_display(), 'attempts': job.attempts,
        'provider': job.provider, 'model_name': job.model_name, 'audio_seconds': job.audio_seconds,
        'processing_ms': job.processing_ms, 'segments_count': job.segments_count, 'error': job.error,
        'created_at': job.created_at, 'finished_at': job.finished_at}

def file_url(resource):
    return f'/api/courses/resources/{resource.pk}/file/'

def common_resource_data(resource):
    return {'id': str(resource.pk), 'course_id': str(resource.course_id), 'chapter_id': str(resource.chapter_id),
        'kind': resource.kind, 'kind_label': resource.get_kind_display(), 'title': resource.title,
        'description': resource.description, 'position': resource.position, 'original_name': resource.original_name}

def manager_resource_data(resource):
    job = ProcessingJob.objects.filter(resource=resource).order_by('-created_at', '-id').first()
    return {**common_resource_data(resource), 'mime_type': resource.mime_type, 'size': resource.size,
        'page_count': resource.page_count, 'duration_seconds': resource.duration_seconds, 'language': resource.language,
        'processing_status': resource.processing_status, 'processing_label': resource.get_processing_status_display(),
        'processing_error': resource.processing_error, 'text_version': resource.text_version,
        'segments_count': ResourceSegment.objects.filter(resource=resource).count(),
        'file_url': file_url(resource), 'download_url': file_url(resource) + '?download=1',
        'job': job_data(job) if job else None, 'created_at': resource.created_at, 'updated_at': resource.updated_at}

def student_resource_data(resource, viewed):
    return {**common_resource_data(resource), 'size': resource.size, 'page_count': resource.page_count,
        'duration_seconds': resource.duration_seconds, 'language': resource.language,
        'processing_status': resource.processing_status, 'processing_label': resource.get_processing_status_display(),
        'segments_count': ResourceSegment.objects.filter(resource=resource).count(),
        'file_url': file_url(resource), 'download_url': file_url(resource) + '?download=1', 'viewed': viewed}

def chapter_data(chapter, resources):
    return {'id': str(chapter.pk), 'course_id': str(chapter.course_id), 'title': chapter.title,
        'description': chapter.description, 'position': chapter.position, 'resources': resources}

def manager_chapters(course):
    resources = list(Resource.objects.filter(course=course))
    return [chapter_data(chapter, [manager_resource_data(r) for r in resources if r.chapter_id == chapter.pk])
        for chapter in Chapter.objects.filter(course=course)]

def student_chapters(course, viewed_ids):
    resources = list(Resource.objects.filter(course=course))
    return [chapter_data(chapter, [student_resource_data(r, r.pk in viewed_ids) for r in resources if r.chapter_id == chapter.pk])
        for chapter in Chapter.objects.filter(course=course)]

def course_groups(course):
    from classrooms.models import LearningGroup
    ids = list(CourseGroup.objects.filter(course=course).values_list('group_id', flat=True))
    return list(LearningGroup.objects.filter(pk__in=ids).order_by('name', 'id'))

def manager_course_data(course):
    return {'id': str(course.pk), 'title': course.title, 'description': course.description,
        'status': course.status, 'status_label': course.get_status_display(),
        'subject': subject_short(course.subject), 'teacher': person_data(course.teacher),
        'groups': [group_short(g) for g in course_groups(course)],
        'chapters_count': Chapter.objects.filter(course=course).count(),
        'resources_count': Resource.objects.filter(course=course).count(),
        'processing_count': Resource.objects.filter(course=course, processing_status__in=['PENDING', 'PROCESSING']).count(),
        'content_version': course.content_version, 'published_at': course.published_at,
        'created_at': course.created_at, 'updated_at': course.updated_at,
        'can_delete': course.status == Course.Status.DRAFT and course.published_at is None}

def student_course_data(course, progress):
    return {'id': str(course.pk), 'title': course.title, 'description': course.description,
        'subject': subject_short(course.subject), 'teacher': person_data(course.teacher),
        'chapters_count': Chapter.objects.filter(course=course).count(), 'resources_count': progress['total'],
        'progress': progress, 'updated_at': course.updated_at}

def segment_data(segment):
    return {'id': str(segment.pk), 'order': segment.order, 'text': segment.text, 'page': segment.page,
        'start_seconds': segment.start_seconds, 'end_seconds': segment.end_seconds,
        'edited': segment.edited, 'edited_at': segment.edited_at}
