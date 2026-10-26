import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User, AdminGuard
from classrooms.models import LearningGroup, Enrollment
from .models import Quiz, Question

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QuizTests(TransactionTestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        self.admin = User.objects.create_superuser('admin@quiz.test', self.password)
        self.teacher = User.objects.create_user('teacher@quiz.test', self.password, role='TEACHER', first_name='Prof', last_name='Un')
        self.other = User.objects.create_user('other@quiz.test', self.password, role='TEACHER')
        self.student = User.objects.create_user('student@quiz.test', self.password)
        self.outsider = User.objects.create_user('outsider@quiz.test', self.password)
        self.group = LearningGroup.objects.create(name='Python', code='PY', teacher=self.teacher, level='L1', academic_year='2026')
        self.other_group = LearningGroup.objects.create(name='Autre', code='OTHER', teacher=self.other, level='L1', academic_year='2026')
        now = timezone.now()
        self.enrollment = Enrollment.objects.create(student=self.student, group=self.group, starts_at=now-timedelta(days=1))
        Enrollment.objects.create(student=self.outsider, group=self.other_group, starts_at=now-timedelta(days=1))
        self.quiz = Quiz.objects.create(title='Les bases de Python', description='Les premières notions de Python.', teacher=self.teacher, learning_group=self.group, level='EASY', duration_minutes=10, max_attempts=2)
        self.client = self.as_user(self.teacher)
    def as_user(self, user):
        c=APIClient();c.force_login(user);return c
    def quiz_data(self, **kwargs):
        data=dict(title='Nouveau quiz', description='Une présentation du quiz.', learning_group_id=str(self.group.pk), level='EASY', duration_minutes=10, max_attempts=2)
        data.update(kwargs);return data
    def question_data(self, **kwargs):
        data=dict(statement='Quel langage ?',choice_a='Python',choice_b='Java',choice_c='Rust',choice_d='Go',correct_answer='A',points=2,explanation='Python est la bonne réponse.')
        data.update(kwargs);return data
    def post(self, path, data=None, client=None):
        return (client or self.client).post('/api/'+path,data if data is not None else {},format='json')
    def add(self, **kwargs):
        r=self.post(f'quizzes/{self.quiz.pk}/questions/', self.question_data(**kwargs));self.assertEqual(r.status_code,201,r.data);return r.data
    def publish(self):
        return self.post(f'quizzes/{self.quiz.pk}/publish/')
    def test_quiz_creation_owner_and_defaults(self):
        r=self.post('quizzes/',self.quiz_data());self.assertEqual(r.status_code,201,r.data)
        saved=Quiz.objects.get(pk=r.data['id']);self.assertEqual(saved.teacher_id,self.teacher.pk);self.assertEqual(saved.status,'DRAFT');self.assertIsNone(saved.published_at)
        self.assertEqual(r.data['question_count'],0);self.assertEqual(r.data['total_points'],0)
        r=self.post('quizzes/',self.quiz_data(title='Sans limite',duration_minutes=None,max_attempts=1))
        self.assertEqual(r.status_code,201,r.data);self.assertIsNone(r.data['duration_minutes']);self.assertEqual(r.data['max_attempts'],1)
    def test_quiz_validation_and_server_owner(self):
        for change in [dict(title='  '),dict(title='x'*151),dict(description='x'*2001),dict(level='EXTREME'),dict(duration_minutes=0),dict(duration_minutes=-1),dict(max_attempts=0),dict(max_attempts=11),dict(max_attempts=1.5),dict(teacher_id=str(self.other.pk)),dict(status='PUBLISHED')]:
            r=self.post('quizzes/',self.quiz_data(**change));self.assertEqual(r.status_code,400,(change,r.data))
        self.assertEqual(self.post('quizzes/',self.quiz_data(learning_group_id=str(self.other_group.pk))).status_code,400)
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'learning_group_id':str(self.other_group.pk)},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.quiz.refresh_from_db();self.assertEqual(self.quiz.learning_group_id,self.group.pk)
        self.group.archived=True;self.group.save()
        self.assertEqual(self.post('quizzes/',self.quiz_data()).status_code,400)
        response=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'title':'Titre modifié'},format='json')
        self.assertEqual(response.status_code,400,response.data)
    def test_teacher_isolation_all_management_routes(self):
        question=self.add();c=self.as_user(self.other)
        paths=[f'quizzes/{self.quiz.pk}/',f'quizzes/{self.quiz.pk}/questions/',f'quizzes/{self.quiz.pk}/preview/',f'quizzes/{self.quiz.pk}/questions/{question["id"]}/']
        for path in paths:self.assertEqual(c.get('/api/'+path).status_code,404,path)
        for action in ['publish','archive','duplicate','reorder']:self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/{action}/',client=c).status_code,404,action)
        self.assertEqual(c.get('/api/quizzes/').data['count'],0)
    def test_inactive_accounts(self):
        c=self.as_user(self.teacher);self.teacher.is_active=False;self.teacher.save()
        self.assertEqual(c.get('/api/quizzes/').status_code,401)
        self.assertEqual(self.post('quizzes/',self.quiz_data(),c).status_code,401)
    def test_question_validation_normalized_choices(self):
        for change in [dict(statement=' '),dict(statement='x'*2001),dict(choice_a=' '),dict(choice_b='  pYtHon  '),dict(choice_a='une  réponse',choice_d='UNE\tRÉPONSE'),dict(choice_c='x'*501),dict(correct_answer='AB'),dict(correct_answer='E'),dict(points=0),dict(points=11),dict(position=0),dict(position=-1)]:
            r=self.post(f'quizzes/{self.quiz.pk}/questions/',self.question_data(**change));self.assertEqual(r.status_code,400,(change,r.data))
        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(),0)
    def test_model_validation(self):
        q=Quiz(title=' ',teacher=self.teacher,learning_group=self.group,max_attempts=11)
        with self.assertRaises(ModelValidationError):q.full_clean()
        question=Question(quiz=self.quiz,position=1,**self.question_data(choice_b=' PYTHON '))
        with self.assertRaises(ModelValidationError):question.full_clean()
    def test_question_defaults_counts_and_patch(self):
        first=self.add();second=self.add(points=4)
        self.assertEqual((first['position'],second['position']),(1,2))
        response=self.client.get(f'/api/quizzes/{self.quiz.pk}/').data
        self.assertEqual((response['question_count'],response['total_points'],response['next_position']),(2,6,3))
        r=self.client.patch(f'/api/quizzes/{self.quiz.pk}/questions/{first["id"]}/',dict(explanation='Une explication'),format='json');self.assertEqual(r.status_code,200,r.data)
        r=self.client.patch(f'/api/quizzes/{self.quiz.pk}/',dict(description='Mise à jour'),format='json');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['max_attempts'],2)
    def test_publication_empty_incomplete_and_preview(self):
        r=self.publish();self.assertEqual(r.status_code,400);self.assertIn('au moins une',str(r.data))
        Question.objects.create(quiz=self.quiz,position=1,**self.question_data(explanation='  '))
        preview=self.client.get(f'/api/quizzes/{self.quiz.pk}/preview/');self.assertEqual(preview.status_code,200)
        self.assertTrue(preview.data['publication_blockers']);self.assertIn('correct_answer',preview.data['questions'][0])
        self.assertEqual(self.publish().status_code,400)
    def test_publication_checks_affectation_and_group(self):
        self.add();self.group.teacher=self.other;self.group.save()
        self.assertEqual(self.publish().status_code,400)
        self.group.teacher=self.teacher;self.group.archived=True;self.group.save()
        self.assertEqual(self.publish().status_code,400)
    def test_published_quiz_and_questions_locked(self):
        q=self.add();r=self.publish();self.assertEqual(r.status_code,200,r.data);self.assertIsNotNone(r.data['published_at'])
        self.assertEqual(self.client.patch(f'/api/quizzes/{self.quiz.pk}/',dict(title='Changé'),format='json').status_code,400)
        self.assertEqual(self.client.delete(f'/api/quizzes/{self.quiz.pk}/').status_code,400)
        self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/questions/',self.question_data()).status_code,400)
        self.assertEqual(self.client.patch(f'/api/quizzes/{self.quiz.pk}/questions/{q["id"]}/',dict(points=3),format='json').status_code,400)
        self.assertEqual(self.client.delete(f'/api/quizzes/{self.quiz.pk}/questions/{q["id"]}/').status_code,400)
        self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/reorder/',dict(question_ids=[q['id']])).status_code,400)
        self.assertEqual(self.publish().status_code,400)
    def test_archive_retains_data_and_lock(self):
        self.add();self.publish();before=Quiz.objects.get(pk=self.quiz.pk).published_at
        r=self.post(f'quizzes/{self.quiz.pk}/archive/');self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(),1)
        self.assertEqual(Quiz.objects.get(pk=self.quiz.pk).published_at,before)
        self.assertEqual(self.client.delete(f'/api/quizzes/{self.quiz.pk}/').status_code,400)
        self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/archive/').status_code,400)
    def test_duplicate_is_independent_and_resets_publication(self):
        first=self.add(points=3,position=4);self.add(points=6,position=9);self.publish()
        for archived in [False,True]:
            if archived:self.post(f'quizzes/{self.quiz.pk}/archive/')
            r=self.post(f'quizzes/{self.quiz.pk}/duplicate/');self.assertEqual(r.status_code,201,r.data)
            duplicate=Quiz.objects.get(pk=r.data['id']);self.assertEqual(duplicate.status,'DRAFT');self.assertIsNone(duplicate.published_at)
            self.assertEqual(list(Question.objects.filter(quiz=duplicate).values_list('position','points')),[(4,3),(9,6)])
            copy=Question.objects.filter(quiz=duplicate).first();copy.statement='Autre énoncé';copy.save()
            self.assertNotEqual(Question.objects.get(pk=first['id']).statement,copy.statement)
        self.assertEqual(self.post(f'quizzes/{duplicate.pk}/duplicate/').status_code,400)
    def test_duplicate_requires_active_compatible_destination(self):
        self.add();self.publish();self.group.archived=True;self.group.save()
        self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/duplicate/').status_code,400)
        destination=LearningGroup.objects.create(name='Nouveau',code='NEW',teacher=self.teacher,level='L2',academic_year='2026')
        r=self.post(f'quizzes/{self.quiz.pk}/duplicate/',dict(learning_group_id=str(destination.pk)));self.assertEqual(r.status_code,201,r.data)
    def test_delete_draft_removes_only_its_questions(self):
        self.add();other=Quiz.objects.create(title='Autre',teacher=self.teacher,learning_group=self.group)
        Question.objects.create(quiz=other,position=1,**self.question_data())
        self.assertEqual(self.client.delete(f'/api/quizzes/{self.quiz.pk}/').status_code,204)
        self.assertEqual(Question.objects.count(),1);self.assertTrue(Quiz.objects.filter(pk=other.pk).exists())
    def test_reorder_atomic_and_foreign_question_refused(self):
        a=self.add();b=self.add();c=self.add()
        r=self.post(f'quizzes/{self.quiz.pk}/reorder/',dict(question_ids=[c['id'],a['id'],b['id']]));self.assertEqual(r.status_code,200,r.data)
        self.assertEqual([q['id'] for q in r.data['results']],[c['id'],a['id'],b['id']]);self.assertEqual([q['position'] for q in r.data['results']],[1,2,3])
        r=self.post(f'quizzes/{self.quiz.pk}/reorder/',dict(question_ids=[a['id'],a['id']]));self.assertEqual(r.status_code,400)
        other=Quiz.objects.create(title='Autre',teacher=self.teacher,learning_group=self.group)
        self.assertEqual(self.client.get(f'/api/quizzes/{other.pk}/questions/{a["id"]}/').status_code,404)
    def test_position_unique_index_and_concurrent_auto_positions(self):
        self.add(position=4)
        with self.assertRaises(IntegrityError):Question.objects.create(quiz=self.quiz,position=4,**self.question_data())
        clients=[self.as_user(self.teacher),self.as_user(self.teacher)]
        payload=self.question_data()
        def create(client):
            try:return client.post(f'/api/quizzes/{self.quiz.pk}/questions/',payload,format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create,clients))
        self.assertIn(201,results);self.assertTrue(all(code in (201,409) for code in results),results)
        # A busy shared guard may return 409 after three attempts; no write is silently lost.
        if 409 in results:
            retry=self.post(f'quizzes/{self.quiz.pk}/questions/',payload)
            self.assertEqual(retry.status_code,201,retry.data)
        self.assertEqual(list(Question.objects.filter(quiz=self.quiz).values_list('position',flat=True)),[4,5,6])
    def test_concurrent_explicit_position_does_not_duplicate(self):
        AdminGuard.objects.get_or_create(key='accounts');clients=[self.as_user(self.teacher),self.as_user(self.teacher)]
        def create(client):
            try:return client.post(f'/api/quizzes/{self.quiz.pk}/questions/',self.question_data(position=1),format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create,clients))
        self.assertEqual(results.count(201),1,results);self.assertEqual(Question.objects.filter(quiz=self.quiz,position=1).count(),1)
    def test_student_presentation_never_returns_answers(self):
        self.add();self.publish();c=self.as_user(self.student)
        r=c.get('/api/student/quizzes/');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['count'],1)
        r=c.get(f'/api/student/quizzes/{self.quiz.pk}/');self.assertEqual(r.status_code,200,r.data)
        for field in ['questions','correct_answer','explanation','choice_a','teacher_id','next_position']:self.assertNotIn(field,str(r.data))
        self.assertEqual(r.data['question_count'],1);self.assertEqual(r.data['total_points'],2)
        self.assertEqual(c.get('/api/quizzes/').status_code,403)
        for path in [f'quizzes/{self.quiz.pk}/',f'quizzes/{self.quiz.pk}/questions/',f'quizzes/{self.quiz.pk}/preview/']:
            self.assertEqual(c.get('/api/'+path).status_code,403)
        self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/publish/',client=c).status_code,403)
    def test_student_visibility_periods_archives_and_foreign_ids(self):
        c=self.as_user(self.student)
        self.assertEqual(c.get(f'/api/student/quizzes/{self.quiz.pk}/').status_code,404)
        self.add();self.publish();self.assertEqual(self.as_user(self.outsider).get(f'/api/student/quizzes/{self.quiz.pk}/').status_code,404)
        self.enrollment.ends_at=timezone.now()-timedelta(hours=1);self.enrollment.save()
        self.assertEqual(c.get('/api/student/quizzes/').data['count'],0)
        self.enrollment.ends_at=None;self.enrollment.starts_at=timezone.now()+timedelta(days=1);self.enrollment.save()
        self.assertEqual(c.get('/api/student/quizzes/').data['count'],0)
        self.enrollment.starts_at=timezone.now()-timedelta(days=1);self.enrollment.save();self.group.archived=True;self.group.save()
        self.assertEqual(c.get('/api/student/quizzes/').data['count'],0)
    def test_admin_selects_teacher_and_respects_lifecycle(self):
        c=self.as_user(self.admin)
        self.assertEqual(self.post('quizzes/',self.quiz_data(),c).status_code,400)
        r=self.post('quizzes/',self.quiz_data(teacher_id=str(self.teacher.pk)),c);self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(self.post('quizzes/',self.quiz_data(teacher_id=str(self.other.pk)),c).status_code,400)
        self.teacher.is_active=False;self.teacher.save();self.assertEqual(self.post('quizzes/',self.quiz_data(teacher_id=str(self.teacher.pk)),c).status_code,400)
        self.teacher.is_active=True;self.teacher.save();self.add();self.publish()
        self.assertEqual(c.get(f'/api/quizzes/{self.quiz.pk}/preview/').status_code,200)
        self.assertEqual(c.patch(f'/api/quizzes/{self.quiz.pk}/',dict(title='Interdit'),format='json').status_code,400)
        self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/archive/',client=c).status_code,200)
    def test_list_search_filters_and_pagination(self):
        for i in range(22):Quiz.objects.create(title=f'Quiz {i}',teacher=self.teacher,learning_group=self.group,level='HARD')
        r=self.client.get('/api/quizzes/?q=Quiz&level=HARD&status=DRAFT');self.assertEqual(r.data['count'],22);self.assertEqual(len(r.data['results']),20)
        self.assertEqual(len(self.client.get('/api/quizzes/?q=Quiz&page=2').data['results']),2)
        self.assertEqual(self.client.get('/api/quizzes/?level=INVALID').status_code,400)
        self.assertEqual(self.client.get('/api/quizzes/?page=bad').status_code,400)
        self.assertEqual(self.client.get('/api/quizzes/not-an-id/').status_code,404)
    def test_csrf_all_new_mutations(self):
        c=APIClient(enforce_csrf_checks=True);c.force_login(self.teacher)
        for path in ['quizzes/',f'quizzes/{self.quiz.pk}/questions/',*[f'quizzes/{self.quiz.pk}/{a}/' for a in ['publish','archive','duplicate','reorder']]]:
            self.assertEqual(self.post(path,{},c).status_code,403,path)
        self.assertEqual(c.patch(f'/api/quizzes/{self.quiz.pk}/',{},format='json').status_code,403)
        self.assertEqual(c.delete(f'/api/quizzes/{self.quiz.pk}/').status_code,403)
        token=c.get('/api/csrf/').data['csrfToken']
        r=c.post('/api/quizzes/',self.quiz_data(),format='json',HTTP_X_CSRFTOKEN=token);self.assertEqual(r.status_code,201,r.data)
    def test_no_arbitrary_status_and_malformed_input(self):
        for status in ['PUBLISHED','ARCHIVED','DRAFT']:
            self.assertEqual(self.client.patch(f'/api/quizzes/{self.quiz.pk}/',{'status':status},format='json').status_code,400)
        self.assertEqual(self.post('quizzes/',[]).status_code,400)
        self.add();self.publish()
        self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/duplicate/',[]).status_code,400)

    def test_group_with_quiz_cannot_be_deleted(self):
        fresh=LearningGroup.objects.create(name='Groupe avec quiz',code='QUIZONLY',teacher=self.teacher,level='L1',academic_year='2026')
        Quiz.objects.create(title='Quiz dépendant',teacher=self.teacher,learning_group=fresh)
        response=self.as_user(self.admin).delete(f'/api/groups/{fresh.pk}/')
        self.assertEqual(response.status_code,400,response.data)
        self.assertTrue(LearningGroup.objects.filter(pk=fresh.pk).exists())

    def test_legacy_invalid_question_blocks_publication(self):
        Question.objects.create(quiz=self.quiz,position=1,**self.question_data(choice_b=' Python '))
        response=self.publish()
        self.assertEqual(response.status_code,400,response.data)
        self.assertIn('identique',str(response.data))

    def test_admin_global_filters(self):
        other=Quiz.objects.create(title='Autre enseignant',teacher=self.other,learning_group=self.other_group,level='HARD')
        c=self.as_user(self.admin)
        response=c.get(f'/api/quizzes/?teacher={self.other.pk}&group={self.other_group.pk}&level=HARD')
        self.assertEqual(response.data['count'],1)
        self.assertEqual(response.data['results'][0]['id'],str(other.pk))

    def test_description_preserved_through_question_and_lifecycle(self):
        description='Trois questions pour consolider les premières notions de Python.'
        response=self.post('quizzes/',self.quiz_data(description=description))
        self.assertEqual(response.status_code,201,response.data)
        self.quiz=Quiz.objects.get(pk=response.data['id'])
        self.assertEqual(self.quiz.description,description)
        self.add()
        self.quiz.refresh_from_db();self.assertEqual(self.quiz.description,description)
        self.publish();self.quiz.refresh_from_db();self.assertEqual(self.quiz.description,description)
        self.post(f'quizzes/{self.quiz.pk}/archive/')
        self.quiz.refresh_from_db();self.assertEqual(self.quiz.description,description)

    def test_quiz_field_errors_for_creation_update_and_duplicate(self):
        invalid = [
            ('title', ''), ('title', '   '), ('title', 123), ('title', 'x'*51), ('title', None),
            ('description', []), ('description', ''), ('description', '   '), ('description', 'x'*2001), ('description', None),
            ('level', ''), ('level', 'IMPOSSIBLE'),
            ('duration_minutes', True), ('duration_minutes', 1.5), ('duration_minutes', '1e2'),
            ('duration_minutes', 0), ('duration_minutes', 2147483648),
            ('max_attempts', False), ('max_attempts', 1.5), ('max_attempts', '2.0'),
            ('max_attempts', ''), ('max_attempts', 0), ('max_attempts', 11),
        ]
        original_title = self.quiz.title
        for field, value in invalid:
            for method in ('create', 'patch'):
                with self.subTest(field=field, value=value, method=method):
                    response = self.post('quizzes/', self.quiz_data(**{field:value})) if method == 'create' else self.client.patch(
                        f'/api/quizzes/{self.quiz.pk}/', {field:value}, format='json')
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(field, response.data['error']['fields'])
        self.quiz.refresh_from_db(); self.assertEqual(self.quiz.title, original_title)
        self.add(); self.publish()
        response = self.post(f'quizzes/{self.quiz.pk}/duplicate/', {'max_attempts':'1e1'})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('max_attempts', response.data['error']['fields'])
        self.assertEqual(Quiz.objects.count(), 1)

    def test_question_field_errors_for_creation_and_update(self):
        question = self.add()
        invalid = [
            ('statement', ''), ('statement', ' \n '), ('statement', 12), ('statement', 'x'*2001),
            *[(f'choice_{letter}', value) for letter in 'abcd' for value in ('', '  ', 'x'*501, 12)],
            ('correct_answer', ''), ('correct_answer', 'AB'), ('correct_answer', ['A','B']),
            ('explanation', {}), ('explanation', None), ('explanation', ''), ('explanation', ' \n '),
            ('points', True), ('points', ''), ('points', '2e0'), ('points', 1.5), ('points', 0), ('points', 11),
            ('position', False), ('position', ''), ('position', '1.0'), ('position', 1.5),
            ('position', 0), ('position', 2147483648),
        ]
        for field, value in invalid:
            for method in ('create', 'patch'):
                with self.subTest(field=field, value=value, method=method):
                    response = self.post(f'quizzes/{self.quiz.pk}/questions/', self.question_data(**{field:value})) if method == 'create' else self.client.patch(
                        f'/api/quizzes/{self.quiz.pk}/questions/{question["id"]}/', {field:value}, format='json')
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(field, response.data['error']['fields'])
        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(), 1)
        saved = Question.objects.get(pk=question['id'])
        self.assertEqual(saved.statement, 'Quel langage ?'); self.assertEqual(saved.points, 2)

    def test_required_fields_return_all_field_errors(self):
        response = self.post('quizzes/', {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data['error']['fields']), {'title','description','learning_group_id','level','duration_minutes','max_attempts'})
        response = self.post('quizzes/', {}, self.as_user(self.admin))
        self.assertIn('teacher_id', response.data['error']['fields'])
        response = self.post(f'quizzes/{self.quiz.pk}/questions/', {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data['error']['fields']), {'statement','choice_a','choice_b','choice_c','choice_d','correct_answer','explanation','points'})

    def test_invalid_references_have_associated_field_errors(self):
        for field in ('learning_group_id', 'teacher_id'):
            for value in ('', 'invalide', '000000000000000000000000', None, 123):
                with self.subTest(field=field, value=value):
                    data = self.quiz_data(teacher_id=str(self.teacher.pk))
                    data[field] = value
                    response = self.post('quizzes/', data, self.as_user(self.admin))
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(field, response.data['error']['fields'])

    def test_explicit_unlimited_and_integer_strings_remain_supported(self):
        response = self.post('quizzes/', self.quiz_data(duration_minutes=None, max_attempts='2'))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['duration_minutes'])
        response = self.post(f'quizzes/{self.quiz.pk}/questions/', self.question_data(points='3', position='2'))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['points'], 3)
        response = self.publish()
        self.assertEqual(response.status_code, 200, response.data)

    def test_visibility_for_each_status_and_role(self):
        self.add()
        clients = {role:self.as_user(user) for role,user in (
            ('owner',self.teacher), ('admin',self.admin), ('other_teacher',self.other),
            ('student',self.student), ('outsider',self.outsider))}
        for status in ('DRAFT','PUBLISHED','ARCHIVED'):
            if status == 'PUBLISHED': self.assertEqual(self.publish().status_code, 200)
            if status == 'ARCHIVED': self.assertEqual(self.post(f'quizzes/{self.quiz.pk}/archive/').status_code, 200)
            with self.subTest(status=status):
                for role in ('owner','admin'):
                    response = clients[role].get(f'/api/quizzes/{self.quiz.pk}/')
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data['status'], status)
                    self.assertEqual(clients[role].get('/api/quizzes/').data['count'], 1)
                self.assertEqual(clients['other_teacher'].get(f'/api/quizzes/{self.quiz.pk}/').status_code, 404)
                self.assertEqual(clients['other_teacher'].get('/api/quizzes/').data['count'], 0)
                for role in ('student','outsider'):
                    visible = status == 'PUBLISHED' and role == 'student'
                    response = clients[role].get(f'/api/student/quizzes/{self.quiz.pk}/')
                    self.assertEqual(response.status_code, 200 if visible else 404)
                    self.assertEqual(clients[role].get('/api/student/quizzes/').data['count'], int(visible))
        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(), 1)
