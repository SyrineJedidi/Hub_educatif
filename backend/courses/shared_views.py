from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from accounts.services import limit
from accounts.views import SecureView
from ai.transcription import provider_status
from classrooms.services import get_object
from .models import Resource
from .permissions import CourseManager, CourseReader
from .search import search
from .services import manager_courses, visible_courses
from .uploads import file_response


class ResourceFileView(SecureView):
    permission_classes = [CourseReader]
    http_method_names = ['get', 'head', 'options']
    def get(self, request, resource_id):
        try: resource = get_object(Resource, resource_id)
        except NotFound: resource = None
        if not resource or not visible_courses(request.user).filter(pk=resource.course_id).exists():
            raise NotFound('Ressource introuvable.')
        return file_response(request, resource)


class SearchView(SecureView):
    permission_classes = [CourseReader]
    def get(self, request):
        limit(request, 'course-search', maximum=60, seconds=60, identity=str(request.user.pk))
        return Response(search(request))


class ProcessingStatusView(SecureView):
    permission_classes = [CourseManager]
    def get(self, request):
        resources = Resource.objects.all()
        if request.user.role != 'ADMIN': resources = resources.filter(course_id__in=list(manager_courses(request.user).values_list('id', flat=True)))
        counts = {key: resources.filter(processing_status=status).count() for key, status in
            [('pending', Resource.ProcessingStatus.PENDING), ('running', Resource.ProcessingStatus.PROCESSING), ('failed', Resource.ProcessingStatus.FAILED)]}
        return Response({**provider_status(), 'process_inline': settings.COURSES_PROCESS_INLINE, **counts})
