import secrets
from datetime import timedelta
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User, AdminGuard
from classrooms.models import LearningGroup, Enrollment
from .models import Quiz, Question, Attempt, Answer


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StudentResultsTests(TransactionTestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(20)
        self.teacher = User.objects.create_user('teacher@results.test', self.password, role='TEACHER', first_name='Alice', last_name='Enseignante')
        self.other_teacher = User.objects.create_user('other@results.test', self.password, role='TEACHER', first_name='Marc', last_name='Autre')
        self.admin = User.objects.create_superuser('admin@results.test', self.password)
        self.student = User.objects.create_user('student@results.test', self.password, first_name='Élodie', last_name='Martin')
        self.second = User.objects.create_user('second@results.test', self.password, first_name='Bilal', last_name='Zidane')
        self.group = LearningGroup.objects.create(name='Python', code='RES1', teacher=self.teacher, level='L1', academic_year='2026')
        self.other_group = LearningGroup.objects.create(name='Autre groupe', code='RES2', teacher=self.other_teacher, level='L1', academic_year='2026')
        for student, group in ((self.student,self.group),(self.second,self.group),(self.second,self.other_group)):
            Enrollment.objects.create(student=student,group=group,starts_at=timezone.now()-timedelta(days=3))
        self.quiz = Quiz.objects.create(title='Quiz Python', description='Présentation', teacher=self.teacher, learning_group=self.group, status='PUBLISHED')
        self.other_quiz = Quiz.objects.create(title='Autre quiz', description='Présentation', teacher=self.other_teacher, learning_group=self.other_group, status='ARCHIVED')
        self.questions = []
        for position, points in ((1,3),(2,2)):
            self.questions.append(Question.objects.create(quiz=self.quiz,statement=f'Question initiale {position}',choice_a='Python',choice_b='Java',choice_c='Rust',choice_d='Go',correct_answer='A',explanation='Explication initiale',points=points,position=position))
        fields=('statement','choice_a','choice_b','choice_c','choice_d','correct_answer','explanation','points','position')
        self.snapshot=[{'id':str(q.pk),**{field:getattr(q,field) for field in fields}} for q in self.questions]
        now=timezone.now()
        self.closed=Attempt.objects.create(student=self.student,quiz=self.quiz,learning_group=self.group,number=1,quiz_title=self.quiz.title,question_snapshot=self.snapshot,started_at=now-timedelta(days=1),ended_at=now-timedelta(hours=1),status='SUBMITTED',points_earned=3,total_points=5)
        self.live=Attempt.objects.create(student=self.student,quiz=self.quiz,learning_group=self.group,number=2,quiz_title=self.quiz.title,question_snapshot=self.snapshot,status='IN_PROGRESS',total_points=5)
        self.overdue=Attempt.objects.create(student=self.second,quiz=self.quiz,learning_group=self.group,number=1,quiz_title=self.quiz.title,question_snapshot=self.snapshot,started_at=now-timedelta(hours=1),deadline=now-timedelta(seconds=1),total_points=5)
        other_question=Question.objects.create(quiz=self.other_quiz,statement='Autre question',choice_a='A',choice_b='B',choice_c='C',choice_d='D',correct_answer='B',explanation='Autre explication',points=2,position=1)
        other_snapshot=[{'id':str(other_question.pk),**{field:getattr(other_question,field) for field in fields}}]
        self.expired=Attempt.objects.create(student=self.second,quiz=self.other_quiz,learning_group=self.other_group,number=1,quiz_title=self.other_quiz.title,question_snapshot=other_snapshot,status='EXPIRED',ended_at=now-timedelta(minutes=1),points_earned=2,total_points=2)
        for attempt in (self.closed,self.live,self.overdue):
            Answer.objects.create(attempt=attempt,question=self.questions[0],selected_choice='A')
        Answer.objects.create(attempt=self.expired,question=other_question,selected_choice='B')
        self.client=self.as_user(self.teacher)

    def as_user(self,user):
        client=APIClient(); client.force_login(user); return client

    def detail(self,attempt,client=None):
        return (client or self.client).get(f'/api/quizzes/results/{attempt.pk}/')

    def snapshot_data(self):
        return (list(Attempt.objects.order_by('id').values()),list(Answer.objects.order_by('id').values()),list(AdminGuard.objects.values()))

    def test_teacher_list_and_direct_detail_are_scoped_to_owned_quizzes(self):
        response=self.client.get('/api/quizzes/results/')
        self.assertEqual(response.status_code,200,response.data); self.assertEqual(response.data['count'],3)
        self.assertEqual({row['quiz_id'] for row in response.data['results']},{str(self.quiz.pk)})
        self.assertEqual(self.detail(self.expired).status_code,404)
        self.assertEqual(self.client.get(f'/api/quizzes/{self.other_quiz.pk}/results/').status_code,404)
        other=self.as_user(self.other_teacher)
        self.assertEqual(other.get('/api/quizzes/results/').data['count'],1)
        self.assertEqual(self.detail(self.closed,other).status_code,404)

    def test_admin_reads_every_quiz_and_filters_quiz_group_teacher(self):
        client=self.as_user(self.admin)
        self.assertEqual(client.get('/api/quizzes/results/').data['count'],4)
        for suffix in (f'quiz={self.other_quiz.pk}',f'group={self.other_group.pk}',f'teacher={self.other_teacher.pk}'):
            response=client.get('/api/quizzes/results/?'+suffix)
            self.assertEqual(response.status_code,200,response.data); self.assertEqual(response.data['count'],1)
            self.assertEqual(response.data['results'][0]['id'],str(self.expired.pk))
        self.assertEqual(self.detail(self.expired,client).status_code,200)

    def test_student_cannot_use_reporting_even_for_own_attempt(self):
        client=self.as_user(self.student)
        for path in ('quizzes/results/',f'quizzes/{self.quiz.pk}/results/',f'quizzes/results/{self.closed.pk}/'):
            self.assertEqual(client.get('/api/'+path).status_code,403,path)
        self.assertEqual(client.get(f'/api/student/attempts/{self.closed.pk}/result/').status_code,200)
        self.assertEqual(client.get(f'/api/student/attempts/{self.overdue.pk}/').status_code,404)
        self.assertEqual(client.get(f'/api/student/attempts/{self.overdue.pk}/result/').status_code,404)

    def test_scores_names_and_progress_rows(self):
        response=self.client.get(f'/api/quizzes/{self.quiz.pk}/results/')
        self.assertEqual(response.data['quiz']['id'],str(self.quiz.pk))
        rows={row['id']:row for row in response.data['results']}
        closed=rows[str(self.closed.pk)]
        self.assertEqual(closed['student'],{'id':str(self.student.pk),'first_name':'Élodie','last_name':'Martin'})
        self.assertEqual(closed['learning_group']['name'],'Python')
        self.assertEqual((closed['points_earned'],closed['total_points'],closed['percentage']),(3,5,60))
        live=rows[str(self.live.pk)]
        self.assertEqual(live['status'],'IN_PROGRESS'); self.assertIsNone(live['points_earned']); self.assertIsNone(live['percentage'])
        for key in ('question_snapshot','password','correct_answer','email'):
            self.assertNotIn(key,str(response.data))

    def test_search_full_name_and_effective_status_filter(self):
        response=self.client.get('/api/quizzes/results/?q=martin Élodie')
        self.assertEqual(response.data['count'],2)
        self.assertEqual(self.client.get('/api/quizzes/results/?q=Zidane&status=EXPIRED').data['count'],1)
        self.assertEqual(self.client.get('/api/quizzes/results/?status=IN_PROGRESS').data['count'],1)
        self.assertEqual(self.client.get('/api/quizzes/results/?status=SUBMITTED').data['count'],1)
        self.assertEqual(self.client.get('/api/quizzes/results/?status=INVALID').status_code,400)
        self.assertEqual(self.client.get('/api/quizzes/results/?page=invalid').status_code,400)

    def test_detail_uses_historical_snapshot_and_recorded_choices(self):
        Question.objects.filter(pk=self.questions[0].pk).update(statement='Modifié',correct_answer='D',points=10,explanation='Modifiée')
        response=self.detail(self.closed)
        self.assertEqual(response.status_code,200,response.data)
        question=response.data['questions'][0]
        self.assertEqual(question['statement'],'Question initiale 1')
        self.assertEqual(question['selected_choice'],'A'); self.assertEqual(question['correct_answer'],'A')
        self.assertEqual(question['explanation'],'Explication initiale'); self.assertEqual(question['points_earned'],3)
        self.assertIsNone(response.data['questions'][1]['selected_choice']); self.assertEqual(response.data['questions'][1]['points_earned'],0)

    def test_live_detail_has_reference_correction_but_no_final_score(self):
        response=self.detail(self.live)
        self.assertEqual(response.status_code,200,response.data)
        self.assertIsNone(response.data['points_earned']); self.assertIsNone(response.data['percentage'])
        self.assertEqual(response.data['questions'][0]['correct_answer'],'A')
        self.assertTrue(all(q['points_earned'] is None and q['is_correct'] is None for q in response.data['questions']))

    def test_overdue_result_is_projected_without_writing_scores(self):
        before=self.snapshot_data()
        response=self.detail(self.overdue)
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['status'],'EXPIRED')
        self.assertEqual((response.data['points_earned'],response.data['percentage']),(3,60))
        self.assertEqual(before,self.snapshot_data())
        self.overdue.refresh_from_db(); self.assertEqual(self.overdue.status,'IN_PROGRESS'); self.assertIsNone(self.overdue.points_earned)

    def test_all_consultations_are_read_only_and_write_methods_refused(self):
        before=self.snapshot_data()
        for client in (self.client,self.as_user(self.admin)):
            self.assertEqual(client.get('/api/quizzes/results/').status_code,200)
            self.assertEqual(client.get(f'/api/quizzes/{self.quiz.pk}/results/').status_code,200)
            for attempt in (self.closed,self.live,self.overdue): self.assertEqual(self.detail(attempt,client).status_code,200)
            self.assertEqual(client.post('/api/quizzes/results/',{},format='json').status_code,405)
            self.assertEqual(client.patch(f'/api/quizzes/results/{self.closed.pk}/',{'points_earned':0},format='json').status_code,405)
            self.assertEqual(client.delete(f'/api/quizzes/results/{self.closed.pk}/').status_code,405)
        self.assertEqual(before,self.snapshot_data())

    def test_pagination_and_empty_results(self):
        for index in range(22):
            student=User.objects.create_user(f'page{index}@results.test',self.password,first_name='Élève',last_name=str(index))
            Attempt.objects.create(student=student,quiz=self.quiz,learning_group=self.group,number=1,quiz_title=self.quiz.title,question_snapshot=self.snapshot,status='SUBMITTED',ended_at=timezone.now(),points_earned=0,total_points=5)
        response=self.client.get('/api/quizzes/results/')
        self.assertEqual(response.data['count'],25); self.assertEqual(len(response.data['results']),20)
        self.assertEqual(len(self.client.get('/api/quizzes/results/?page=2').data['results']),5)
        self.assertEqual(self.client.get('/api/quizzes/results/?q=Introuvable').data['count'],0)

    def test_filters_cannot_bypass_teacher_scope_and_inactive_is_denied(self):
        self.assertEqual(self.client.get(f'/api/quizzes/results/?quiz={self.other_quiz.pk}').status_code,404)
        self.assertEqual(self.client.get(f'/api/quizzes/results/?teacher={self.other_teacher.pk}').status_code,403)
        self.assertEqual(self.client.get(f'/api/quizzes/results/?group={self.other_group.pk}').data['count'],0)
        self.teacher.is_active=False; self.teacher.save()
        self.assertEqual(self.client.get('/api/quizzes/results/').status_code,401)
        self.assertEqual(APIClient().get('/api/quizzes/results/').status_code,401)
