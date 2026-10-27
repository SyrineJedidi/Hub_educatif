from rest_framework.response import Response
from accounts.services import limit
from accounts.views import SecureView, validated
from classrooms.services import get_object
from .models import ResourceSegment, ResourceView, Subject, normalized_text
from .permissions import CourseStudent
from .serializers import EmptyActionSerializer, segment_data, student_chapters, student_course_data, student_resource_data
from .services import get_visible_course, paged_list, record_view, resource_for, student_progress, visible_courses
from .views import MAX_SEGMENTS


class StudentView(SecureView):
    permission_classes = [CourseStudent]


class StudentCoursesView(StudentView):
    def get(self, request):
        courses = visible_courses(request.user)
        q = request.query_params.get('q', '').strip()[:150]
        if q: courses = courses.filter(title__icontains=q)
        if request.query_params.get('subject'): courses = courses.filter(subject=get_object(Subject, request.query_params['subject']))
        courses = list(courses)
        subjects = {s.pk: s.name_key for s in Subject.objects.filter(pk__in=[c.subject_id for c in courses])}
        courses.sort(key=lambda c: (subjects.get(c.subject_id, ''), normalized_text(c.title), str(c.pk)))
        return Response(paged_list(request, courses, lambda c: student_course_data(c, student_progress(request.user, c))))


class StudentCourseDetailView(StudentView):
    def get(self, request, uid):
        course = get_visible_course(request.user, uid)
        viewed = set(ResourceView.objects.filter(student=request.user, course=course).values_list('resource_id', flat=True))
        return Response({**student_course_data(course, student_progress(request.user, course)), 'chapters': student_chapters(course, viewed)})


class StudentResourceView(StudentView):
    def get(self, request, uid, resource_id):
        course = get_visible_course(request.user, uid)
        resource = resource_for(course, resource_id)
        viewed = ResourceView.objects.filter(student=request.user, resource=resource).exists()
        return Response({**student_resource_data(resource, viewed), 'chapter': {'id': str(resource.chapter_id), 'title': resource.chapter.title},
            'course': {'id': str(course.pk), 'title': course.title}})


class StudentSegmentsView(StudentView):
    def get(self, request, uid, resource_id):
        resource = resource_for(get_visible_course(request.user, uid), resource_id)
        segments = ResourceSegment.objects.filter(resource=resource).order_by('order')
        return Response({'count': segments.count(), 'results': [segment_data(s) for s in segments[:MAX_SEGMENTS]]})


class ResourceViewTrackingView(StudentView):
    # Self-service write on the student's own counter: no global write guard.
    def post(self, request, uid, resource_id):
        limit(request, 'course-view', maximum=600, seconds=3600, identity=str(request.user.pk))
        validated(EmptyActionSerializer, request)
        course = get_visible_course(request.user, uid)
        view = record_view(request.user, course, resource_for(course, resource_id))
        return Response({'viewed': True, 'view_count': view.view_count, 'progress': student_progress(request.user, course)})
