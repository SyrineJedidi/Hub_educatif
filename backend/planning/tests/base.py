import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from quizzes.models import Quiz, Attempt
from planning.models import StudyGoal, Deadline, Availability, StudyPlan, RevisionTask, LOCAL_TZ

API = '/api/student/planning/'


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL_TZ)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PlanningTestCase(TransactionTestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        self.teacher = User.objects.create_user('teacher@planning.test', self.password, role='TEACHER', first_name='Alice', last_name='Prof')
        self.student = User.objects.create_user('student@planning.test', self.password, first_name='Élodie', last_name='Martin')
        self.other = User.objects.create_user('other@planning.test', self.password, first_name='Bilal', last_name='Zidane')
        self.group = LearningGroup.objects.create(name='Python', code='PLAN1', teacher=self.teacher, level='L1', academic_year='2026')
        self.math = LearningGroup.objects.create(name='Mathématiques', code='PLAN2', teacher=self.teacher, level='L1', academic_year='2026')
        now = timezone.now()
        for group in (self.group, self.math):
            Enrollment.objects.create(student=self.student, group=group, starts_at=now - timedelta(days=30))
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)
        self.client = self.as_user(self.student)

    def as_user(self, user):
        client = APIClient(); client.force_login(user); return client

    def post(self, path, data=None, client=None):
        return (client or self.client).post(API + path, data if data is not None else {}, format='json')

    def patch(self, path, data, client=None):
        return (client or self.client).patch(API + path, data, format='json')

    def delete(self, path, client=None):
        return (client or self.client).delete(API + path)

    def get(self, path, client=None):
        return (client or self.client).get(API + path)

    def goal(self, student=None, **kwargs):
        values = dict(title='Réussir Python', priority='MEDIUM', estimated_hours=5, learning_group=self.group)
        values.update(kwargs)
        return StudyGoal.objects.create(student=student or self.student, **values)

    def deadline(self, student=None, **kwargs):
        values = dict(title='Examen Python', kind='EXAM', due_at=timezone.now() + timedelta(days=10))
        values.update(kwargs)
        return Deadline.objects.create(student=student or self.student, **values)

    def slot(self, weekday, start, end, student=None):
        return Availability.objects.create(student=student or self.student, weekday=weekday,
            start_time=datetime.strptime(start, '%H:%M').time(), end_time=datetime.strptime(end, '%H:%M').time())

    def every_day(self, start='09:00', end='11:00', student=None):
        for weekday in range(7): self.slot(weekday, start, end, student)

    def plan(self, student=None, status='DRAFT', start=None, days=7, **kwargs):
        start = start or self.tomorrow
        return StudyPlan.objects.create(student=student or self.student, title='Planning test', start_date=start,
            end_date=start + timedelta(days=days - 1), status=status, activated_at=timezone.now() if status == 'ACTIVE' else None, **kwargs)

    def task(self, plan, starts_at, minutes=60, **kwargs):
        return RevisionTask.objects.create(plan=plan, student_id=plan.student_id, title=kwargs.pop('title', 'Séance'),
            starts_at=starts_at, ends_at=starts_at + timedelta(minutes=minutes), **kwargs)

    def attempt(self, group, earned, total=10, ended_at=None, student=None):
        quiz = Quiz.objects.create(title=f'Quiz {group.name}', description='Présentation', teacher=self.teacher, learning_group=group, status='PUBLISHED')
        number = Attempt.objects.filter(student=student or self.student, quiz=quiz).count() + 1
        ended_at = ended_at or timezone.now() - timedelta(days=1)
        return Attempt.objects.create(student=student or self.student, quiz=quiz, learning_group=group, number=number, quiz_title=quiz.title,
            question_snapshot=[], started_at=ended_at - timedelta(minutes=10), ended_at=ended_at, status='SUBMITTED',
            points_earned=earned, total_points=total)

    def generate(self, mode='rules', client=None, **kwargs):
        data = dict(start_date=self.tomorrow.isoformat(), end_date=(self.tomorrow + timedelta(days=6)).isoformat(), mode=mode)
        data.update(kwargs)
        return self.post('plans/generate/', data, client)

    @contextmanager
    def frozen(self, moment):
        # Patch the clock, then log in again so the session is valid at the patched time.
        with patch('django.utils.timezone.now', return_value=moment):
            self.client = self.as_user(self.student)
            yield
