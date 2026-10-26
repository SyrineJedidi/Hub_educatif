from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from classrooms.models import Enrollment, LearningGroup
from classrooms.services import get_object, mutation
from .models import Attempt, Answer, Question
from .attempt_serializers import answer_data


def mongo_now():
    now = timezone.now()
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def require_group_access(student, group):
    now = timezone.now()
    allowed = not group.archived and Enrollment.objects.filter(
        student=student, group=group, starts_at__lte=now,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).exists()
    if not allowed: raise NotFound('Ce quiz ou cette tentative ne vous est pas accessible.')


def accessible_attempts(student):
    now = timezone.now()
    groups = Enrollment.objects.filter(student=student, starts_at__lte=now).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('group_id', flat=True)
    active = list(LearningGroup.objects.filter(pk__in=list(groups), archived=False).values_list('id', flat=True))
    return Attempt.objects.filter(student=student, learning_group_id__in=active).order_by('-started_at', 'id')


def own_attempt(student, uid):
    attempt = get_object(Attempt, uid)
    if attempt.student_id != student.pk: raise NotFound('Tentative introuvable.')
    require_group_access(student, attempt.learning_group)
    return attempt


def error_response(code, message, status=409):
    # Returning a response commits lazy expiration; raising would roll it back.
    return Response({'error': {'code': code, 'message': message, 'fields': {}}}, status=status)


def saved_answers(attempt):
    return {str(a.question_id): a for a in Answer.objects.filter(attempt=attempt)}


def score_saved_answers(attempt, answers=None):
    answers = saved_answers(attempt) if answers is None else answers
    return sum(q['points'] for q in attempt.question_snapshot
        if q['id'] in answers and answers[q['id']].selected_choice == q['correct_answer'])


def attempt_percentage(attempt):
    if attempt.points_earned is None or not attempt.total_points: return None
    return round(100 * attempt.points_earned / attempt.total_points, 2)


def finalize(attempt, expired=False):
    if attempt.status != Attempt.Status.IN_PROGRESS: return
    attempt.points_earned = score_saved_answers(attempt)
    attempt.status = Attempt.Status.EXPIRED if expired else Attempt.Status.SUBMITTED
    attempt.ended_at = attempt.deadline if expired else mongo_now()
    attempt.save(update_fields=['points_earned', 'status', 'ended_at'])


def expire_if_due(attempt):
    if attempt.status == Attempt.Status.IN_PROGRESS and attempt.deadline and timezone.now() >= attempt.deadline:
        finalize(attempt, expired=True)


@mutation
def finalize_expired(_self, request, ids):
    for uid in ids:
        attempt = own_attempt(request.user, uid)
        expire_if_due(attempt)


def refresh_expired(request, attempts):
    now = timezone.now()
    due = [str(a.pk) for a in attempts if a.status == 'IN_PROGRESS' and a.deadline and now >= a.deadline]
    if due:
        finalize_expired(None, request, due)
        for attempt in attempts:
            if str(attempt.pk) in due: attempt.refresh_from_db()


def attempt_summary(attempt):
    closed = attempt.status != Attempt.Status.IN_PROGRESS
    return {
        'id': str(attempt.pk), 'quiz_id': str(attempt.quiz_id), 'quiz_title': attempt.quiz_title,
        'number': attempt.number, 'status': attempt.status, 'started_at': attempt.started_at,
        'deadline': attempt.deadline, 'ended_at': attempt.ended_at,
        'total_points': attempt.total_points, 'points_earned': attempt.points_earned if closed else None,
        'server_time': timezone.now(),
    }


def attempt_data(attempt):
    # Explicit allowlist: corrections and explanations stay server-side.
    fields = ('id', 'statement', 'choice_a', 'choice_b', 'choice_c', 'choice_d', 'points', 'position')
    return {**attempt_summary(attempt),
        'questions': [{field: q[field] for field in fields} for q in attempt.question_snapshot],
        'answers': [answer_data(a) for a in Answer.objects.filter(attempt=attempt)],
    }


def result_data(attempt, answers=None):
    answers = saved_answers(attempt) if answers is None else answers
    questions = []
    for snapshot in attempt.question_snapshot:
        answer = answers.get(snapshot['id'])
        selected = answer.selected_choice if answer else None
        correct = selected == snapshot['correct_answer']
        questions.append({**snapshot, 'selected_choice': selected, 'is_correct': correct,
            'points_earned': snapshot['points'] if correct else 0})
    return {**attempt_summary(attempt), 'percentage': attempt_percentage(attempt), 'questions': questions}


def create_attempt(student, quiz, number):
    fields = ('statement', 'choice_a', 'choice_b', 'choice_c', 'choice_d', 'correct_answer', 'explanation', 'points', 'position')
    snapshot = [{'id': str(q.pk), **{field: getattr(q, field) for field in fields}} for q in Question.objects.filter(quiz=quiz)]
    if not snapshot: return None
    now = mongo_now()
    return Attempt.objects.create(student=student, quiz=quiz, learning_group=quiz.learning_group,
        number=number, quiz_title=quiz.title, question_snapshot=snapshot,
        started_at=now, deadline=now + timedelta(minutes=quiz.duration_minutes) if quiz.duration_minutes else None,
        total_points=sum(q['points'] for q in snapshot))
