from django.utils import timezone
from rest_framework.response import Response
from .attempt_views import StudentAttemptView
from .attempt_services import accessible_attempts, refresh_expired, attempt_summary, attempt_percentage
from .services import student_quizzes
from .schedule import availability


def student_progress(request):
    now = timezone.now()
    quizzes = {quiz.pk: quiz for quiz in student_quizzes(request.user)}
    attempts = list(accessible_attempts(request.user))
    refresh_expired(request, attempts)
    finished = [a for a in attempts if a.status in ('SUBMITTED', 'EXPIRED')]
    completed = {a.quiz_id for a in finished}
    scored = [a for a in finished if a.points_earned is not None and a.total_points > 0]
    best = {}
    for attempt in scored:
        score = attempt_percentage(attempt)
        best[attempt.quiz_id] = max(best.get(attempt.quiz_id, 0), score)
    started = {a.quiz_id for a in attempts}
    ongoing = {a.quiz_id: a for a in attempts if a.status == 'IN_PROGRESS' and a.quiz_id not in completed}
    categories = {'to_finish': [], 'to_start': [], 'upcoming': []}
    for uid, quiz in quizzes.items():
        if uid in completed: continue  # Optional retakes are not outstanding required work.
        window = availability(quiz, now)
        item = {'quiz_id': str(uid), 'quiz_title': quiz.title, 'opens_at': quiz.opens_at, 'closes_at': quiz.closes_at}
        if uid in ongoing:
            attempt = ongoing[uid]
            categories['to_finish'].append({**item, 'attempt_id': str(attempt.pk), 'deadline': attempt.deadline})
        elif uid not in started:
            if window['can_start']: categories['to_start'].append(item)
            elif window['state'] == 'UPCOMING': categories['upcoming'].append(item)
    for key, field in [('to_finish', 'deadline'), ('to_start', 'closes_at'), ('upcoming', 'opens_at')]:
        categories[key].sort(key=lambda row: (row.get(field) is None, row.get(field) or now, row['quiz_id']))
    timeline = [{**attempt_summary(a), 'percentage': attempt_percentage(a)} for a in
                sorted(scored, key=lambda a: (a.ended_at or a.started_at, a.started_at, str(a.pk)))]
    return {'priorities': categories, 'counts': {key: len(value) for key, value in categories.items()},
            'completed_quizzes': len(completed), 'remaining_quizzes': len(categories['to_finish'])+len(categories['to_start']),
            'scored_quizzes': len(best), 'average_best_percentage': round(sum(best.values())/len(best), 2) if best else None,
            'timeline': timeline, 'server_time': now, 'time_zone': 'Africa/Tunis'}


class StudentProgressView(StudentAttemptView):
    def get(self, request):
        response = Response(student_progress(request))
        response['Cache-Control'] = 'private, no-store'
        return response
