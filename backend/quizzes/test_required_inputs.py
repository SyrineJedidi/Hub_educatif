import json
import secrets
from io import StringIO
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import LearningGroup
from .models import Quiz, Question


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RequiredInputTests(TransactionTestCase):
    def setUp(self):
        self.teacher = User.objects.create_user('strict@inputs.test', secrets.token_urlsafe(20), role='TEACHER')
        self.group = LearningGroup.objects.create(name='Groupe', code='REQ', teacher=self.teacher, level='L1', academic_year='2026')
        self.client = APIClient(); self.client.force_login(self.teacher)
        self.quiz = Quiz.objects.create(title='Quiz existant', description='Présentation', teacher=self.teacher, learning_group=self.group, duration_minutes=10)

    def quiz_data(self, **changes):
        return dict(title='Été : x[0] <= 10 ?', description="L’élève écrit : print('Été') # ✓", learning_group_id=str(self.group.pk), level='MEDIUM', duration_minutes=5, max_attempts=2, **changes)

    def question_data(self):
        return dict(statement="Quelle instruction affiche l'été ?", choice_a="print('Été')", choice_b='x[0]', choice_c="{'clé': 1}", choice_d='a <= b', correct_answer='A', explanation="print('Été') affiche du texte : accents, apostrophes et code sont autorisés.", points=2)

    def test_required_create_fields_cannot_be_omitted_individually(self):
        for key in self.quiz_data():
            body=self.quiz_data(); body.pop(key)
            response=self.client.post('/api/quizzes/',body,format='json')
            self.assertEqual(response.status_code,400,response.data); self.assertIn(key,response.data['error']['fields'])
        for key in self.question_data():
            body=self.question_data(); body.pop(key)
            response=self.client.post(f'/api/quizzes/{self.quiz.pk}/questions/',body,format='json')
            self.assertEqual(response.status_code,400,response.data); self.assertIn(key,response.data['error']['fields'])

    def test_boundaries_and_code_are_accepted(self):
        body=self.quiz_data(); body.update(title='É'*50,description='D'*2000)
        response=self.client.post('/api/quizzes/',body,format='json'); self.assertEqual(response.status_code,201,response.data)
        body['title']='É'*51
        self.assertEqual(self.client.post('/api/quizzes/',body,format='json').status_code,400)
        body=self.question_data(); body.update(statement='S'*2000,choice_a='A'*500,choice_b='B'*500,choice_c='C'*500,choice_d='D'*500)
        response=self.client.post(f'/api/quizzes/{self.quiz.pk}/questions/',body,format='json'); self.assertEqual(response.status_code,201,response.data)
        response=self.client.post('/api/quizzes/',self.quiz_data(),format='json'); self.assertEqual(response.status_code,201,response.data)
        response=self.client.post(f'/api/quizzes/{self.quiz.pk}/questions/',self.question_data(),format='json'); self.assertEqual(response.status_code,201,response.data)

    def test_missing_duration_differs_from_explicit_null_on_create_and_patch(self):
        body=self.quiz_data(); body.pop('duration_minutes')
        self.assertEqual(self.client.post('/api/quizzes/',body,format='json').status_code,400)
        body['duration_minutes']=None
        self.assertEqual(self.client.post('/api/quizzes/',body,format='json').status_code,201)
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'title':'Nouveau titre'},format='json')
        self.assertEqual(response.status_code,200,response.data); self.assertEqual(response.data['duration_minutes'],10)
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'duration_minutes':None},format='json')
        self.assertEqual(response.status_code,200,response.data); self.assertIsNone(response.data['duration_minutes'])
        for value in ('',0,-1,True,1.5,'1e2'):
            response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'duration_minutes':value},format='json')
            self.assertEqual(response.status_code,400,response.data)

    def test_patch_validates_final_state_and_preserves_omitted_values(self):
        Quiz.objects.filter(pk=self.quiz.pk).update(title='Ancien titre '*8,description='  ')
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'level':'HARD'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertIn('title',response.data['error']['fields']); self.assertIn('description',response.data['error']['fields'])
        self.quiz.refresh_from_db(); self.assertEqual(self.quiz.level,'EASY'); self.assertEqual(self.quiz.description,'  ')
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'title':'Titre corrigé','description':'Description corrigée'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['duration_minutes'],10); self.assertEqual(response.data['max_attempts'],1)
        body=self.question_data(); body['explanation']=' \n '
        question=Question.objects.create(quiz=self.quiz,position=1,**body)
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/questions/{question.pk}/',{'points':4},format='json')
        self.assertEqual(response.status_code,400,response.data); self.assertIn('explanation',response.data['error']['fields'])
        question.refresh_from_db(); self.assertEqual(question.points,2)
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/questions/{question.pk}/',{'explanation':'Correction explicite'},format='json')
        self.assertEqual(response.status_code,200,response.data); self.assertEqual(response.data['position'],1); self.assertEqual(response.data['points'],2)

    def test_audit_is_read_only_and_reports_existing_invalid_records(self):
        Quiz.objects.filter(pk=self.quiz.pk).update(title='X'*75,description='  ')
        body=self.question_data(); body['explanation']=' '
        Question.objects.create(quiz=self.quiz,position=1,**body)
        before=(list(Quiz.objects.values()),list(Question.objects.values()))
        output=StringIO(); call_command('audit_quiz_inputs',as_json=True,stdout=output)
        report=json.loads(output.getvalue())
        self.assertEqual(report['nonconforming_records'],2); self.assertEqual(report['modified_records'],0)
        self.assertEqual(before,(list(Quiz.objects.values()),list(Question.objects.values())))

    def test_duplicate_of_valid_quiz_and_atomic_refusal_of_legacy_question(self):
        self.quiz.title='T'*50; self.quiz.status='PUBLISHED'; self.quiz.save()
        question=Question.objects.create(quiz=self.quiz,position=1,**self.question_data())
        response=self.client.post(f'/api/quizzes/{self.quiz.pk}/duplicate/',{},format='json')
        self.assertEqual(response.status_code,201,response.data); self.assertEqual(len(response.data['title']),50)
        self.assertTrue(response.data['title'].endswith(' (copie)'))
        Question.objects.filter(pk=question.pk).update(explanation='')
        count=Quiz.objects.count()
        response=self.client.post(f'/api/quizzes/{self.quiz.pk}/duplicate/',{},format='json')
        self.assertEqual(response.status_code,400,response.data); self.assertIn('questions',response.data['error']['fields'])
        self.assertEqual(Quiz.objects.count(),count)
        response=self.client.post(f'/api/quizzes/{self.quiz.pk}/archive/',{},format='json')
        self.assertEqual(response.status_code,200,response.data)
        question.refresh_from_db(); self.assertEqual(question.explanation,'')
