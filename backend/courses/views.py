from django.core.files.storage import default_storage
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from accounts.services import limit
from accounts.views import SecureView, validated
from classrooms.services import mutation, paginated
from .models import Chapter, Course, CourseGroup, ProcessingJob, Resource, ResourceSegment, normalized_text
from .permissions import CourseManager
from .processing import job_kind, process_now, should_process_inline
from .serializers import (ChapterReorderSerializer, ChapterWriteSerializer, EmptyActionSerializer, ResourceReorderSerializer,
    ResourceUpdateSerializer, ResourceUploadSerializer, SegmentUpdateSerializer, chapter_data, manager_chapters,
    manager_course_data, manager_resource_data, segment_data)
from .services import (ProcessingInProgress, body_chapter, chapter_for, compact_positions, content_changed, course_values,
    delete_resources, editable, filtered_courses, managed_course, manager_courses, model_errors, next_position,
    publication_blockers, reorder, replace_groups, resource_for, segment_for)
from .statistics import course_statistics, statistics_csv
from .uploads import create_resource, inspect_upload, reject_oversized_body, store

MAX_SEGMENTS = 5000


class ManagerView(SecureView):
    permission_classes = [CourseManager]


def course_detail(course):
    # Counters are bumped with F() expressions: reload before answering.
    course = Course.objects.get(pk=course.pk)
    return {**manager_course_data(course), 'chapters': manager_chapters(course),
        'publication_blockers': publication_blockers(course) if course.status == Course.Status.DRAFT else []}


def ordered_resources(course, queryset):
    positions = {c.pk: c.position for c in Chapter.objects.filter(course=course)}
    return sorted(queryset, key=lambda r: (positions.get(r.chapter_id, 0), r.position, str(r.pk)))


class CoursesView(ManagerView):
    def get(self, request):
        qs = filtered_courses(request, manager_courses(request.user)).order_by('-updated_at', 'id')
        return Response(paginated(request, qs, manager_course_data))
    @mutation
    def post(self, request):
        course, groups = course_values(request, request.data)
        course.save()
        for group in groups: CourseGroup.objects.create(course=course, group=group)
        return Response(course_detail(course), status=201)


class CourseDetailView(ManagerView):
    def get(self, request, uid):
        return Response(course_detail(managed_course(request.user, uid)))
    @mutation
    def patch(self, request, uid):
        course = managed_course(request.user, uid); editable(course)
        course, groups = course_values(request, request.data, course)
        course.save(update_fields=['title', 'description', 'subject', 'teacher', 'updated_at'])
        if groups is not None and replace_groups(course, groups): content_changed(course.pk, 'groups_changed')
        return Response(course_detail(course))
    @mutation
    def delete(self, request, uid):
        course = managed_course(request.user, uid); editable(course)
        if course.status != Course.Status.DRAFT or course.published_at:
            raise ValidationError({'detail': 'Ce cours a déjà été publié : archivez-le plutôt que de le supprimer.'})
        # Explicit single-collection deletes: the MongoDB backend does not support joined deletes.
        delete_resources(list(Resource.objects.filter(course=course)))
        Chapter.objects.filter(course=course).delete()
        CourseGroup.objects.filter(course=course).delete()
        course.delete()
        return Response(status=204)


class CourseActionView(ManagerView):
    transition = None
    transitions = {
        'publish': ([Course.Status.DRAFT], Course.Status.PUBLISHED, 'Seul un cours en brouillon peut être publié.'),
        'unpublish': ([Course.Status.PUBLISHED], Course.Status.DRAFT, 'Seul un cours publié peut être retiré de la publication.'),
        'archive': ([Course.Status.DRAFT, Course.Status.PUBLISHED], Course.Status.ARCHIVED, 'Ce cours est déjà archivé.'),
        'restore': ([Course.Status.ARCHIVED], Course.Status.DRAFT, 'Seul un cours archivé peut être restauré.'),
    }
    @mutation
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        course = managed_course(request.user, uid)
        sources, target, message = self.transitions[self.transition]
        if course.status not in sources: raise ValidationError({'status': [message]})
        if target == Course.Status.PUBLISHED:
            reasons = publication_blockers(course)
            if reasons: raise ValidationError({'publication': reasons})
            course.published_at = course.published_at or timezone.now()
        course.status = target
        course.save(update_fields=['status', 'published_at', 'updated_at'])
        content_changed(course.pk, 'status_changed')
        return Response(course_detail(course))


class ChaptersView(ManagerView):
    def get(self, request, uid):
        return Response({'results': manager_chapters(managed_course(request.user, uid))})
    @mutation
    def post(self, request, uid):
        course = managed_course(request.user, uid); editable(course)
        data = validated(ChapterWriteSerializer, request)
        chapter = Chapter(course=course, position=next_position(Chapter.objects.filter(course=course)), **data)
        model_errors(chapter); chapter.save(); course.save(update_fields=['updated_at'])
        return Response(chapter_data(chapter, []), status=201)


class ChapterDetailView(ManagerView):
    @mutation
    def patch(self, request, uid, chapter_id):
        course = managed_course(request.user, uid); editable(course)
        chapter = chapter_for(course, chapter_id)
        serializer = ChapterWriteSerializer(data=request.data, partial=True); serializer.is_valid(raise_exception=True)
        renamed = serializer.validated_data.get('title', chapter.title) != chapter.title
        for field, value in serializer.validated_data.items(): setattr(chapter, field, value)
        model_errors(chapter); chapter.save(update_fields=['title', 'description', 'updated_at']); course.save(update_fields=['updated_at'])
        if renamed: content_changed(course.pk, 'chapters_changed')
        return Response(chapter_data(chapter, [manager_resource_data(r) for r in Resource.objects.filter(chapter=chapter)]))
    @mutation
    def delete(self, request, uid, chapter_id):
        course = managed_course(request.user, uid); editable(course)
        chapter = chapter_for(course, chapter_id)
        if Resource.objects.filter(chapter=chapter).exists():
            raise ValidationError({'detail': 'Supprimez ou déplacez d’abord les ressources de ce chapitre.'})
        chapter.delete(); compact_positions(Chapter.objects.filter(course=course))
        content_changed(course.pk, 'chapters_changed')
        return Response(status=204)


class ChapterReorderView(ManagerView):
    @mutation
    def post(self, request, uid):
        course = managed_course(request.user, uid); editable(course)
        ids = validated(ChapterReorderSerializer, request)['chapter_ids']
        if reorder(list(Chapter.objects.filter(course=course)), ids, 'chapter_ids', 'Envoyez exactement les chapitres de ce cours, sans doublon.'):
            content_changed(course.pk, 'chapters_changed')
        return Response({'results': manager_chapters(course)})


class ResourcesView(ManagerView):
    def get(self, request, uid):
        course = managed_course(request.user, uid)
        resources = Resource.objects.filter(course=course)
        if request.query_params.get('chapter'): resources = resources.filter(chapter=chapter_for(course, request.query_params['chapter']))
        return Response({'results': [manager_resource_data(r) for r in ordered_resources(course, resources)]})
    def post(self, request, uid):
        # Cheap rejections first: the multipart body is only parsed by validated().
        limit(request, 'course-upload', maximum=30, seconds=3600, identity=str(request.user.pk))
        reject_oversized_body(request)
        editable(managed_course(request.user, uid))
        data = validated(ResourceUploadSerializer, request)
        upload = inspect_upload(data['file'])
        # Stored before the transaction, so a retried transaction never writes the file twice.
        name = store(upload)
        try:
            resource, job = create_resource(self, request, uid, data, upload, name)
        except Exception:
            default_storage.delete(name)
            raise
        if should_process_inline(resource): process_now(job)
        return Response(manager_resource_data(Resource.objects.get(pk=resource.pk)), status=201)


class ResourceDetailView(ManagerView):
    def get(self, request, uid, resource_id):
        return Response(manager_resource_data(resource_for(managed_course(request.user, uid), resource_id)))
    @mutation
    def patch(self, request, uid, resource_id):
        course = managed_course(request.user, uid); editable(course)
        resource = resource_for(course, resource_id)
        serializer = ResourceUpdateSerializer(data=request.data, partial=True); serializer.is_valid(raise_exception=True)
        attrs = dict(serializer.validated_data)
        source = resource.chapter_id
        changed = attrs.get('title', resource.title) != resource.title
        if 'chapter_id' in attrs:
            target = body_chapter(course, attrs.pop('chapter_id'))
            if target.pk != source:
                resource.chapter = target; resource.position = next_position(Resource.objects.filter(chapter=target)); changed = True
        for field, value in attrs.items(): setattr(resource, field, value)
        model_errors(resource)
        resource.save(update_fields=['title', 'description', 'chapter', 'position', 'updated_at'])
        if resource.chapter_id != source:
            ResourceSegment.objects.filter(resource=resource).update(chapter=resource.chapter)
            compact_positions(Resource.objects.filter(chapter_id=source))
        course.save(update_fields=['updated_at'])
        if changed: content_changed(course.pk, 'resource_updated', resource.pk)
        return Response(manager_resource_data(resource))
    @mutation
    def delete(self, request, uid, resource_id):
        course = managed_course(request.user, uid); editable(course)
        resource = resource_for(course, resource_id)
        delete_resources([resource])
        compact_positions(Resource.objects.filter(chapter_id=resource.chapter_id))
        content_changed(course.pk, 'resource_deleted', resource.pk)
        return Response(status=204)


class ResourceReorderView(ManagerView):
    @mutation
    def post(self, request, uid, chapter_id):
        course = managed_course(request.user, uid); editable(course)
        chapter = chapter_for(course, chapter_id)
        ids = validated(ResourceReorderSerializer, request)['resource_ids']
        if reorder(list(Resource.objects.filter(chapter=chapter)), ids, 'resource_ids', 'Envoyez exactement les ressources de ce chapitre, sans doublon.'):
            content_changed(course.pk, 'resource_updated')
        return Response({'results': [manager_resource_data(r) for r in Resource.objects.filter(chapter=chapter)]})


@mutation
def start_reprocess(_self, request, uid, resource_id):
    validated(EmptyActionSerializer, request)
    course = managed_course(request.user, uid); editable(course)
    resource = resource_for(course, resource_id)
    if ProcessingJob.objects.filter(resource=resource, active=True).exists(): raise ProcessingInProgress()
    job = ProcessingJob.objects.create(resource=resource, kind=job_kind(resource))
    was_ready = resource.processing_status == Resource.ProcessingStatus.READY
    resource.processing_status = Resource.ProcessingStatus.PENDING; resource.processing_error = ''
    resource.save(update_fields=['processing_status', 'processing_error', 'updated_at'])
    # Its segments leave course_segments() until the new result is written.
    if was_ready: content_changed(course.pk, 'resource_updated', resource.pk)
    return resource, job


class ReprocessView(ManagerView):
    def post(self, request, uid, resource_id):
        resource, job = start_reprocess(self, request, uid, resource_id)
        if should_process_inline(resource): process_now(job)
        return Response(manager_resource_data(Resource.objects.get(pk=resource.pk)))


class SegmentsView(ManagerView):
    def get(self, request, uid, resource_id):
        resource = resource_for(managed_course(request.user, uid), resource_id)
        segments = ResourceSegment.objects.filter(resource=resource).order_by('order')
        return Response({'count': segments.count(), 'results': [segment_data(s) for s in segments[:MAX_SEGMENTS]]})


class SegmentDetailView(ManagerView):
    @mutation
    def patch(self, request, uid, resource_id, segment_id):
        course = managed_course(request.user, uid); editable(course)
        resource = resource_for(course, resource_id)
        segment = segment_for(resource, segment_id)
        text = validated(SegmentUpdateSerializer, request)['text']
        # A running job would replace the segments and silently drop the correction.
        if ProcessingJob.objects.filter(resource=resource, active=True).exists(): raise ProcessingInProgress()
        if text != segment.text:
            now = timezone.now()
            segment.text, segment.search_text = text, normalized_text(text)
            segment.edited, segment.edited_by, segment.edited_at = True, request.user, now
            segment.save(update_fields=['text', 'search_text', 'edited', 'edited_by', 'edited_at'])
            Resource.objects.filter(pk=resource.pk).update(text_version=F('text_version') + 1, updated_at=now)
            content_changed(course.pk, 'segment_edited', resource.pk)
        return Response(segment_data(segment))


class StatisticsView(ManagerView):
    http_method_names = ['get', 'head', 'options']
    def perform_content_negotiation(self, request, force=False):
        # ?format=csv selects the export below, not a DRF renderer.
        return super().perform_content_negotiation(request, force=True)
    def get(self, request, uid):
        data = course_statistics(managed_course(request.user, uid))
        if request.query_params.get('format') == 'csv': return statistics_csv(data)
        return Response(data)
