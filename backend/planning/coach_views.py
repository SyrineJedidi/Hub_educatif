from django.utils import timezone
from rest_framework.response import Response
from accounts.views import SecureView
from classrooms.services import paginated
from .permissions import PlanningCoach
from .services import coach_students, coached_student, coach_row, coach_detail


class CoachView(SecureView):
    # Coaching is read-only: teachers and the administrator never write student planning data.
    permission_classes = [PlanningCoach]
    http_method_names = ['get', 'head', 'options']


class CoachStudentsView(CoachView):
    def get(self, request):
        now = timezone.now()
        return Response(paginated(request, coach_students(request), lambda student: coach_row(request.user, student, now)))


class CoachStudentDetailView(CoachView):
    def get(self, request, uid):
        return Response(coach_detail(request.user, coached_student(request.user, uid)))
