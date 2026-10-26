import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from django.db import connections, IntegrityError
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User, AdminGuard
from classrooms.models import LearningGroup, Enrollment
from .models import Quiz, Question, Attempt, Answer


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AttemptTests(TransactionTestCase):
    def setUp(self):
        password = secrets.token_urlsafe(24)
        self.teacher = User.objects.create_user('teacher@attempt.test', password, role='TEACHER')
        self.student = User.objects.create_user('student@attempt.test', password)
        self.other = User.objects.create_user('other@attempt.test', password)
        self.admin = User.objects.create_superuser('admin@attempt.test', password)
        self.group = LearningGroup.objects.create(name='Python', code='ATT', teacher=self.teacher, level='L1', academic_year='2026')
        self.enrollment = Enrollment.objects.create(student=self.student, group=self.group, starts_at=timezone.now()-timedelta(days=1))
        self.quiz = Quiz.objects.create(title='Python', teacher=self.teacher, learning_group=self.group, status='PUBLISHED', duration_minutes=10, max_attempts=2)
        self.q1 = Question.objects.create(quiz=self.quiz, statement='Deux plus deux ?', choice_a='4', choice_b='2', choice_c='1', choice_d='0', correct_answer='A', explanation='Deux et deux font quatre.', points=3, position=1)
        self.q2 = Question.objects.create(quiz=self.quiz, statement='Deux fois trois ?', choice_a='3', choice_b='6', choice_c='1', choice_d='0', correct_answer='B', explanation='Deux fois trois font six.', points=2, position=2)
        self.client = self.as_user(self.student)

    def as_user(self, user):
        client = APIClient(); client.force_login(user); return client

    def start(self, client=None):
        return (client or self.client).post(f'/api/student/quizzes/{self.quiz.pk}/attempts/', {}, format='json')

    def attempt(self):
        response = self.start(); self.assertEqual(response.status_code,201,response.data)
        return response.data['id']

    def save(self, aid, question=None, choice='A', revision=0, client=None):
        return (client or self.client).put(f'/api/student/attempts/{aid}/answers/{(question or self.q1).pk}/', {'selected_choice':choice,'expected_revision':revision}, format='json')

    def submit(self, aid, versions=None):
        return self.client.post(f'/api/student/attempts/{aid}/submit/', {'answer_revisions':versions or {}}, format='json')

    def test_start_snapshot_confidentiality_and_resume(self):
        before=timezone.now(); aid=self.attempt(); attempt=Attempt.objects.get(pk=aid)
        self.assertGreaterEqual(attempt.started_at,before)
        self.assertEqual(attempt.deadline-attempt.started_at,timedelta(minutes=10))
        self.assertEqual(attempt.total_points,5)
        data=self.start().data; self.assertEqual(data['id'],aid)
        self.assertEqual(Attempt.objects.count(),1)
        for key in ('correct_answer','explanation','question_snapshot'):
            self.assertNotIn(key,str(data))
        response=self.client.get(f'/api/student/attempts/{aid}/result/')
        self.assertEqual(response.status_code,409); self.assertNotIn('correct_answer',str(response.data))

    def test_save_reload_score_and_idempotent_submit(self):
        aid=self.attempt(); self.assertEqual(self.save(aid).status_code,200)
        self.assertEqual(self.save(aid,self.q2,'A').status_code,200)
        detail=self.client.get(f'/api/student/attempts/{aid}/').data
        self.assertEqual(len(detail['answers']),2); self.assertIsNone(detail['points_earned'])
        versions={a['question_id']:a['revision'] for a in detail['answers']}
        first=self.submit(aid,versions); self.assertEqual(first.status_code,200,first.data)
        self.assertEqual(first.data['points_earned'],3); self.assertEqual(first.data['percentage'],60)
        self.assertEqual(first.data['questions'][0]['explanation'],self.q1.explanation)
        again=self.submit(aid,versions); self.assertEqual(again.data['ended_at'],first.data['ended_at'])
        self.assertEqual(again.data['points_earned'],3)
        self.assertEqual(self.save(aid,choice='B',revision=1).status_code,409)

    def test_unanswered_questions_are_zero(self):
        aid=self.attempt(); response=self.submit(aid)
        self.assertEqual(response.data['points_earned'],0)
        self.assertTrue(all(q['selected_choice'] is None and q['points_earned']==0 for q in response.data['questions']))

    def test_expiration_commits_even_when_late_answer_is_refused(self):
        aid=self.attempt(); self.save(aid)
        attempt=Attempt.objects.get(pk=aid)
        with patch('quizzes.attempt_services.timezone.now',return_value=attempt.deadline):
            response=self.save(aid,self.q2,'B'); self.assertEqual(response.status_code,409)
        attempt.refresh_from_db(); self.assertEqual(attempt.status,'EXPIRED')
        self.assertEqual(attempt.points_earned,3); self.assertEqual(attempt.ended_at,attempt.deadline)
        self.assertEqual(Answer.objects.filter(attempt=attempt).count(),1)
        result=self.client.get(f'/api/student/attempts/{aid}/result/')
        self.assertEqual(result.data['points_earned'],3)

    def test_expiration_after_browser_closed_on_every_read_path(self):
        aid=self.attempt(); attempt=Attempt.objects.get(pk=aid)
        with patch('quizzes.attempt_services.timezone.now',return_value=attempt.deadline+timedelta(seconds=1)):
            response=self.client.get(f'/api/student/quizzes/{self.quiz.pk}/attempts/')
        self.assertEqual(response.data['attempts'][0]['status'],'EXPIRED')
        attempt.refresh_from_db(); self.assertEqual(attempt.status,'EXPIRED')
        aid2=self.attempt(); second=Attempt.objects.get(pk=aid2)
        with patch('quizzes.attempt_services.timezone.now',return_value=second.deadline):
            self.client.get('/api/student/attempts/')
        second.refresh_from_db(); self.assertEqual(second.status,'EXPIRED')

    def test_no_deadline_for_unlimited_quiz(self):
        self.quiz.duration_minutes=None; self.quiz.save()
        aid=self.attempt(); self.assertIsNone(Attempt.objects.get(pk=aid).deadline)

    def test_start_finalizes_expired_attempt_and_allocates_next(self):
        aid=self.attempt(); old=Attempt.objects.get(pk=aid)
        with patch('quizzes.attempt_services.timezone.now',return_value=old.deadline+timedelta(seconds=1)):
            response=self.start()
        self.assertEqual(response.status_code,201,response.data)
        self.assertNotEqual(response.data['id'],aid)
        old.refresh_from_db(); self.assertEqual(old.status,'EXPIRED')
        self.assertEqual(Attempt.objects.count(),2)

    def test_archive_allows_resume_and_result_but_no_new_start(self):
        aid=self.attempt(); self.quiz.status='ARCHIVED'; self.quiz.save()
        self.assertEqual(self.start().data['id'],aid)
        self.assertEqual(self.save(aid).status_code,200)
        self.assertEqual(self.submit(aid,{str(self.q1.pk):1}).status_code,200)
        self.assertEqual(self.start().status_code,400)
        self.assertEqual(self.client.get(f'/api/student/attempts/{aid}/result/').status_code,200)
        self.assertEqual(self.client.get('/api/student/attempts/').data['count'],1)

    def test_expiration_is_not_rolled_back_when_archived_start_is_refused(self):
        aid=self.attempt(); attempt=Attempt.objects.get(pk=aid)
        self.quiz.status='ARCHIVED'; self.quiz.save()
        with patch('quizzes.attempt_services.timezone.now',return_value=attempt.deadline):
            self.assertEqual(self.start().status_code,400)
        attempt.refresh_from_db(); self.assertEqual(attempt.status,'EXPIRED')

    def test_quota_and_draft_start(self):
        self.quiz.max_attempts=1; self.quiz.save()
        aid=self.attempt(); self.submit(aid)
        self.assertEqual(self.start().status_code,400); self.assertEqual(Attempt.objects.count(),1)
        self.quiz.status='DRAFT'; self.quiz.save()
        self.assertEqual(self.start().status_code,400)

    def test_permissions_roles_and_other_student(self):
        aid=self.attempt()
        for user in (self.teacher,self.admin):
            client=self.as_user(user)
            for path in (f'student/quizzes/{self.quiz.pk}/attempts/', f'student/attempts/{aid}/',f'student/attempts/{aid}/result/','student/attempts/'):
                self.assertEqual(client.get('/api/'+path).status_code,403)
            self.assertEqual(self.save(aid,client=client).status_code,403)
        other=self.as_user(self.other)
        self.assertEqual(self.start(other).status_code,404)
        self.assertEqual(other.get(f'/api/student/attempts/{aid}/').status_code,404)
        self.assertEqual(self.save(aid,client=other).status_code,404)
        self.assertEqual(other.post(f'/api/student/attempts/{aid}/submit/',{'answer_revisions':{}},format='json').status_code,404)
        self.student.is_active=False; self.student.save()
        self.assertEqual(self.client.get(f'/api/student/attempts/{aid}/').status_code,401)

    def test_ended_future_or_archived_group_revoke_attempt_access(self):
        aid=self.attempt()
        for field,value in (('ends_at',timezone.now()-timedelta(seconds=1)),('starts_at',timezone.now()+timedelta(days=1))):
            original=getattr(self.enrollment,field); setattr(self.enrollment,field,value); self.enrollment.save()
            self.assertEqual(self.client.get(f'/api/student/attempts/{aid}/').status_code,404)
            self.assertEqual(self.save(aid).status_code,404)
            setattr(self.enrollment,field,original); self.enrollment.save()
        self.group.archived=True; self.group.save()
        self.assertEqual(self.client.get(f'/api/student/attempts/{aid}/result/').status_code,404)

    def test_question_from_another_quiz_and_invalid_payload(self):
        aid=self.attempt()
        other_quiz=Quiz.objects.create(title='Autre',teacher=self.teacher,learning_group=self.group)
        foreign=Question.objects.create(quiz=other_quiz,statement='Autre',choice_a='1',choice_b='2',choice_c='3',choice_d='4',correct_answer='A',points=1,position=1)
        self.assertEqual(self.save(aid,foreign).status_code,404)
        self.assertEqual(self.save(aid,choice='AB').status_code,400)
        self.assertEqual(self.save(aid,revision=-1).status_code,400)

    def test_snapshot_survives_changes_to_source_data(self):
        aid=self.attempt(); self.save(aid)
        Question.objects.filter(pk=self.q1.pk).update(correct_answer='D',points=10,explanation='Changé',statement='Modifié')
        Quiz.objects.filter(pk=self.quiz.pk).update(title='Modifié')
        result=self.submit(aid,{str(self.q1.pk):1}).data
        self.assertEqual(result['points_earned'],3); self.assertEqual(result['total_points'],5)
        self.assertEqual(result['quiz_title'],'Python'); self.assertEqual(result['questions'][0]['correct_answer'],'A')
        self.assertEqual(result['questions'][0]['explanation'],self.q1.explanation)

    def test_old_save_cannot_overwrite_new_answer_and_retry_is_idempotent(self):
        aid=self.attempt(); self.save(aid)
        self.assertEqual(self.save(aid,choice='B',revision=1).data['revision'],2)
        self.assertEqual(self.save(aid,choice='A',revision=0).status_code,409)
        self.assertEqual(self.save(aid,choice='B',revision=1).data['revision'],2)
        self.assertEqual(Answer.objects.get(attempt_id=aid).selected_choice,'B')

    def test_submission_requires_acknowledged_answer_versions(self):
        aid=self.attempt(); self.save(aid)
        response=self.submit(aid); self.assertEqual(response.status_code,409)
        self.assertEqual(Attempt.objects.get(pk=aid).status,'IN_PROGRESS')
        self.save(aid,choice='B',revision=1)
        self.assertEqual(self.submit(aid,{str(self.q1.pk):1}).status_code,409)
        self.assertEqual(self.submit(aid,{str(self.q1.pk):2}).status_code,200)

    def test_csrf_for_all_new_mutations(self):
        aid=self.attempt(); client=APIClient(enforce_csrf_checks=True); client.force_login(self.student)
        self.assertEqual(self.start(client).status_code,403)
        self.assertEqual(self.save(aid,client=client).status_code,403)
        self.assertEqual(client.post(f'/api/student/attempts/{aid}/submit/',{},format='json').status_code,403)
        token=client.get('/api/csrf/').data['csrfToken']
        self.assertEqual(client.put(f'/api/student/attempts/{aid}/answers/{self.q1.pk}/',{'selected_choice':'A','expected_revision':0},format='json',HTTP_X_CSRFTOKEN=token).status_code,200)

    def test_concurrent_starts_resume_one_attempt_and_respect_quota(self):
        self.quiz.max_attempts=1; self.quiz.save(); AdminGuard.objects.get_or_create(key='accounts')
        clients=[self.as_user(self.student),self.as_user(self.student)]
        def start(client):
            try:return self.start(client).status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(start,clients))
        self.assertTrue(all(status in (200,201,409) for status in statuses),statuses)
        self.assertEqual(Attempt.objects.count(),1)
        self.assertEqual(self.start().status_code,200)
        aid=str(Attempt.objects.get().pk); self.submit(aid)
        self.assertEqual(self.start().status_code,400)

    def test_real_unique_answer_index(self):
        aid=self.attempt(); self.save(aid)
        with self.assertRaises(IntegrityError):
            Answer.objects.create(attempt_id=aid,question=self.q1,selected_choice='D')

    def test_concurrent_reload_is_read_only_before_expiration(self):
        aid=self.attempt(); revision=AdminGuard.objects.get(key='accounts').revision
        clients=[self.as_user(self.student),self.as_user(self.student)]
        def read(client):
            try:return client.get(f'/api/student/attempts/{aid}/').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(read,clients))
        self.assertEqual(statuses,[200,200])
        self.assertEqual(AdminGuard.objects.get(key='accounts').revision,revision)

    def test_concurrent_submission_is_finalized_once(self):
        aid=self.attempt(); self.save(aid)
        clients=[self.as_user(self.student),self.as_user(self.student)]
        def submit(client):
            try:return client.post(f'/api/student/attempts/{aid}/submit/',{'answer_revisions':{str(self.q1.pk):1}},format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(submit,clients))
        self.assertTrue(all(status in (200,409) for status in statuses),statuses)
        attempt=Attempt.objects.get(pk=aid); self.assertEqual(attempt.status,'SUBMITTED'); self.assertEqual(attempt.points_earned,3)
        ended=attempt.ended_at; self.submit(aid)
        attempt.refresh_from_db(); self.assertEqual(attempt.ended_at,ended)

    def test_concurrent_save_and_submit_cannot_change_final_correction(self):
        aid=self.attempt(); self.save(aid)
        clients=[self.as_user(self.student),self.as_user(self.student)]
        def operation(index):
            try:
                if index==0:return self.save(aid,choice='B',revision=1,client=clients[index]).status_code
                return clients[index].post(f'/api/student/attempts/{aid}/submit/',{'answer_revisions':{str(self.q1.pk):1}},format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(operation,(0,1)))
        self.assertTrue(all(status in (200,409) for status in statuses),statuses)
        attempt=Attempt.objects.get(pk=aid); answer=Answer.objects.get(attempt=attempt)
        if attempt.status=='IN_PROGRESS': self.submit(aid,{str(self.q1.pk):answer.revision}); attempt.refresh_from_db()
        self.assertEqual(attempt.points_earned,3 if answer.selected_choice=='A' else 0)
        self.assertEqual(self.save(aid,choice='D',revision=answer.revision).status_code,409)
