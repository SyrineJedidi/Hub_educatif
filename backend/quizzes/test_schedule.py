from datetime import timedelta
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from . import tests as fixtures
from .models import Quiz, Attempt
from .schedule import availability, attempt_deadline


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ScheduleTests(TransactionTestCase):
    setUp = fixtures.QuizTests.setUp
    as_user = fixtures.QuizTests.as_user
    post = fixtures.QuizTests.post
    add = fixtures.QuizTests.add
    question_data = fixtures.QuizTests.question_data

    def test_aware_optional_dates_and_patch_final_state(self):
        path = f'/api/quizzes/{self.quiz.pk}/'
        for value in ['2026-13-01T10:00:00Z', '2026-10-26T10:00:00', '', 'wrong']:
            self.assertEqual(self.client.patch(path, {'opens_at': value}, format='json').status_code, 400)
        response = self.client.patch(path, {'opens_at': '2026-12-01T10:00:00+01:00', 'closes_at': '2026-12-01T10:00:00Z'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.patch(path, {'closes_at': '2026-12-01T08:59:00Z'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(path, {'opens_at': None, 'closes_at': None}, format='json').status_code, 200)

    def test_boundaries_and_minimum_deadline(self):
        now = timezone.now(); self.quiz.status = 'PUBLISHED'
        for duration, closing, expected in [(10, now+timedelta(minutes=3), now+timedelta(minutes=3)),
            (2, now+timedelta(minutes=5), now+timedelta(minutes=2)), (None, now+timedelta(minutes=1), now+timedelta(minutes=1)),
            (2, None, now+timedelta(minutes=2)), (None, None, None)]:
            self.quiz.duration_minutes=duration; self.quiz.closes_at=closing
            self.assertEqual(attempt_deadline(self.quiz, now), expected)
        self.quiz.opens_at=now; self.assertTrue(availability(self.quiz, now)['can_start'])
        self.quiz.closes_at=now; self.assertFalse(availability(self.quiz, now)['can_start'])

    def test_presentation_visible_but_start_refused_before_open_and_after_close(self):
        self.add(); self.quiz.status='PUBLISHED'; self.quiz.opens_at=timezone.now()+timedelta(hours=1); self.quiz.save()
        student=self.as_user(self.student); path=f'/api/student/quizzes/{self.quiz.pk}/'
        self.assertEqual(student.get(path).status_code,200)
        self.assertEqual(student.get(path+'attempts/').data['availability']['state'],'UPCOMING')
        self.assertEqual(student.post(path+'attempts/',{},format='json').data['error']['code'],'quiz_not_open')
        self.quiz.opens_at=None; self.quiz.closes_at=timezone.now()-timedelta(seconds=1); self.quiz.save()
        self.assertEqual(student.post(path+'attempts/',{},format='json').data['error']['code'],'quiz_closed')
        self.assertFalse(Attempt.objects.exists())

    def test_started_deadline_is_fixed_and_dates_locked(self):
        self.add(); now=timezone.now(); self.quiz.status='PUBLISHED'; self.quiz.closes_at=now+timedelta(minutes=3); self.quiz.save()
        student=self.as_user(self.student); path=f'/api/student/quizzes/{self.quiz.pk}/attempts/'
        response=student.post(path,{},format='json'); self.assertEqual(response.status_code,201,response.data)
        attempt=Attempt.objects.get(pk=response.data['id']); deadline=attempt.deadline
        self.assertEqual(deadline.replace(microsecond=0),self.quiz.closes_at.replace(microsecond=0))
        self.assertEqual(self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'closes_at':None},format='json').status_code,400)
        Quiz.objects.filter(pk=self.quiz.pk).update(closes_at=now-timedelta(seconds=1))
        resumed=student.post(path,{},format='json');self.assertEqual(resumed.status_code,200)
        attempt.refresh_from_db(); self.assertEqual(attempt.deadline,deadline)
