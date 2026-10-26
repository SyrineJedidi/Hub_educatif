from copy import copy
from django.db.models import Q
from django.utils import timezone
from rest_framework.fields import ChoiceField
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from accounts.models import User
from accounts.views import SecureView
from classrooms.models import LearningGroup
from classrooms.services import get_object, paginated
from .models import Attempt, Quiz
from .permissions import QuizManager
from .services import managed_quiz
from .attempt_services import (attempt_summary, result_data, saved_answers,
    score_saved_answers, attempt_percentage)


def reported_attempt(attempt, now, answers=None):
    """Project an overdue attempt for reporting, without finalizing or saving it."""
    if attempt.status == Attempt.Status.IN_PROGRESS and attempt.deadline and now >= attempt.deadline:
        visible = copy(attempt)
        visible.status = Attempt.Status.EXPIRED
        visible.ended_at = attempt.deadline
        visible.points_earned = score_saved_answers(attempt, answers)
        return visible
    return attempt


def person_data(user):
    return {'id': str(user.pk), 'first_name': user.first_name, 'last_name': user.last_name}


def summary_data(attempt):
    return {**attempt_summary(attempt),
        'student': person_data(attempt.student),
        'learning_group': {'id': str(attempt.learning_group_id), 'name': attempt.learning_group.name},
        'teacher': person_data(attempt.quiz.teacher),
        'percentage': attempt_percentage(attempt) if attempt.status != 'IN_PROGRESS' else None,
    }


def filtered_results(request, queryset, now):
    search = request.query_params.get('q', '').strip()[:200]
    if search:
        students = User.objects.all()
        for word in search.split():
            students = students.filter(Q(first_name__icontains=word) | Q(last_name__icontains=word))
        queryset = queryset.filter(student_id__in=list(students.values_list('id', flat=True)))
    status = request.query_params.get('status')
    if status:
        status = ChoiceField(choices=Attempt.Status.choices).run_validation(status)
        overdue = Q(status='IN_PROGRESS', deadline__isnull=False, deadline__lte=now)
        if status == 'EXPIRED': queryset = queryset.filter(Q(status='EXPIRED') | overdue)
        elif status == 'IN_PROGRESS':
            queryset = queryset.filter(status='IN_PROGRESS').filter(Q(deadline__isnull=True) | Q(deadline__gt=now))
        else: queryset = queryset.filter(status=status)
    if request.query_params.get('quiz'):
        quiz = managed_quiz(request.user, request.query_params['quiz'])
        queryset = queryset.filter(quiz=quiz)
    if request.query_params.get('group'):
        group = get_object(LearningGroup, request.query_params['group'])
        queryset = queryset.filter(learning_group=group)
    if request.query_params.get('teacher'):
        if request.user.role != 'ADMIN': raise PermissionDenied('Le filtre par enseignant est réservé à l’administrateur.')
        teacher = get_object(User, request.query_params['teacher'])
        ids = list(Quiz.objects.filter(teacher=teacher).values_list('id', flat=True))
        queryset = queryset.filter(quiz_id__in=ids)
    return queryset.order_by('-started_at', 'id')


class ReadOnlyResultsView(SecureView):
    permission_classes = [QuizManager]
    http_method_names = ['get', 'head', 'options']


class ResultsListView(ReadOnlyResultsView):
    def get(self, request, uid=None):
        context = {}
        if uid:
            quiz = managed_quiz(request.user, uid)
            queryset = Attempt.objects.filter(quiz=quiz)
            context = {'quiz': {'id': str(quiz.pk), 'title': quiz.title}}
        elif request.user.role == 'ADMIN': queryset = Attempt.objects.all()
        else:
            ids = list(Quiz.objects.filter(teacher=request.user).values_list('id', flat=True))
            queryset = Attempt.objects.filter(quiz_id__in=ids)
        now = timezone.now()
        queryset = filtered_results(request, queryset, now)
        return Response({**paginated(request, queryset, lambda a: summary_data(reported_attempt(a, now))), **context})


class ResultDetailView(ReadOnlyResultsView):
    def get(self, request, attempt_id):
        attempt = get_object(Attempt, attempt_id)
        managed_quiz(request.user, str(attempt.quiz_id))
        answers = saved_answers(attempt)
        visible = reported_attempt(attempt, timezone.now(), answers)
        summary = summary_data(visible)
        if visible.status != 'IN_PROGRESS':
            return Response({**summary, 'questions': result_data(visible, answers)['questions']})
        questions = []
        for snapshot in attempt.question_snapshot:
            answer = answers.get(snapshot['id'])
            questions.append({**snapshot, 'selected_choice': answer.selected_choice if answer else None,
                'is_correct': None, 'points_earned': None})
        return Response({**summary, 'questions': questions})
