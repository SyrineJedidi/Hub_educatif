from datetime import timedelta
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from classrooms.models import Enrollment
from . import tests as fixtures
from .models import Quiz, Attempt


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProgressTests(TransactionTestCase):
    setUp = fixtures.QuizTests.setUp
    as_user = fixtures.QuizTests.as_user

    def quiz_for(self, title, **attrs):
        return Quiz.objects.create(title=title, description='Présentation', teacher=self.teacher,
            learning_group=self.group, status='PUBLISHED', **attrs)

    def attempt(self, quiz, number=1, points=1, status='SUBMITTED', **attrs):
        now=timezone.now()
        return Attempt.objects.create(quiz=quiz, student=self.student, learning_group=self.group,
            number=number, quiz_title=quiz.title, status=status, points_earned=points,
            total_points=10, ended_at=now if status!='IN_PROGRESS' else None, **attrs)

    def dashboard(self):
        response=self.as_user(self.student).get('/api/student/quiz-progress/')
        self.assertEqual(response.status_code,200,response.data); return response.data

    def test_priority_order_distinct_and_archived_excluded(self):
        now=timezone.now(); early=self.quiz_for('Proche',closes_at=now+timedelta(hours=1))
        late=self.quiz_for('Sans date'); future=self.quiz_for('Bientôt',opens_at=now+timedelta(hours=1))
        running=self.quiz_for('À finir'); self.attempt(running,points=None,status='IN_PROGRESS',deadline=now+timedelta(minutes=3))
        archived=self.quiz_for('Archivé'); archived.status='ARCHIVED';archived.save()
        self.attempt(archived,points=None,status='IN_PROGRESS')
        self.quiz_for('Fermé',closes_at=now-timedelta(seconds=1))
        Enrollment.objects.create(student=self.student,group=self.group,starts_at=now-timedelta(days=2))
        result=self.dashboard()
        self.assertEqual(result['counts'],{'to_start':2,'to_finish':1,'upcoming':1})
        self.assertEqual([row['quiz_id'] for row in result['priorities']['to_start']],[str(early.pk),str(late.pk)])
        self.assertEqual(result['remaining_quizzes'],3)
        self.assertEqual(result['priorities']['upcoming'][0]['quiz_id'],str(future.pk))

    def test_best_per_quiz_average_and_optional_retake_not_remaining(self):
        first=self.quiz_for('Premier'); second=self.quiz_for('Second')
        self.attempt(first,1,2);self.attempt(first,2,8);self.attempt(first,3,None,'IN_PROGRESS')
        self.attempt(second,1,4,'EXPIRED')
        result=self.dashboard()
        self.assertEqual(result['completed_quizzes'],2);self.assertEqual(result['remaining_quizzes'],0)
        self.assertEqual(result['average_best_percentage'],60)
        self.assertEqual(len(result['timeline']),3)
        self.assertEqual(result['counts']['to_finish'],0)

    def test_expiration_is_finalized_and_permissions_apply(self):
        quiz=self.quiz_for('Expiré'); attempt=self.attempt(quiz,points=None,status='IN_PROGRESS',deadline=timezone.now()-timedelta(seconds=1))
        result=self.dashboard();attempt.refresh_from_db()
        self.assertEqual(attempt.status,'EXPIRED');self.assertEqual(result['average_best_percentage'],0)
        self.assertEqual(self.as_user(self.teacher).get('/api/student/quiz-progress/').status_code,403)
        outsider=self.as_user(self.outsider).get('/api/student/quiz-progress/').data
        self.assertEqual(outsider['completed_quizzes'],0)

    def test_empty_results_and_uncorrected_are_not_in_score_statistics(self):
        empty=self.dashboard();self.assertIsNone(empty['average_best_percentage']);self.assertEqual(empty['timeline'],[])
        self.attempt(self.quiz_for('Non corrigé'),points=None)
        result=self.dashboard();self.assertEqual(result['completed_quizzes'],1)
        self.assertIsNone(result['average_best_percentage']);self.assertEqual(result['timeline'],[])
