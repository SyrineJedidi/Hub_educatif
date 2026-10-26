from rest_framework.test import APIClient
from courses.models import Course, Subject
from .base import CourseTestCase


class SubjectTests(CourseTestCase):
    def create_subject(self, **kwargs):
        data = dict(name='Physique quantique', code='phy-q', description='Ondes et particules.'); data.update(kwargs)
        return self.post('subjects/', data)

    def test_creation_normalises_code_and_returns_public_shape(self):
        r = self.create_subject(name='  Physique quantique  '); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['name'], r.data['code'], r.data['description'], r.data['archived']), ('Physique quantique', 'PHY-Q', 'Ondes et particules.', False))
        self.assertEqual(r.data['created_by'], {'id': str(self.teacher.pk), 'first_name': 'Amel', 'last_name': 'Ben Salah'})
        self.assertEqual((r.data['courses_count'], r.data['can_edit']), (0, True)); self.assertNotIn('email', str(r.data))
        saved = Subject.objects.get(pk=r.data['id']); self.assertEqual((saved.name_key, saved.created_by_id), ('physique quantique', self.teacher.pk))
        r = self.post('subjects/', {'name': 'Chimie', 'code': 'CHI'}); self.assertEqual(r.status_code, 201, r.data); self.assertEqual(r.data['description'], '')
        r = self.post('subjects/', {'name': 'Biologie', 'code': 'BIO'}, self.as_user(self.admin)); self.assertEqual(r.status_code, 201, r.data)

    def test_duplicate_name_is_accent_case_and_space_insensitive(self):
        for name in ('mathematiques', '  MATHÉMATIQUES ', 'Mathématiques'):
            r = self.create_subject(name=name, code='OTHER')
            self.assertEqual(r.status_code, 400, name); self.assertEqual(r.data['error']['fields'], {'name': ['Une matière porte déjà ce nom.']})
        r = self.create_subject(name='Algèbre linéaire', code='math'); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['fields'], {'code': ['Ce code est déjà utilisé.']})
        other = self.create_subject(name='Algèbre   linéaire', code='ALG').data
        self.assertEqual(self.patch(f'subjects/{other["id"]}/', {'name': 'MATHEMATIQUES'}).status_code, 400)
        self.assertEqual(self.patch(f'subjects/{other["id"]}/', {'code': 'Math'}).status_code, 400)
        r = self.patch(f'subjects/{other["id"]}/', {'name': 'algèbre linéaire', 'code': 'alg'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Subject.objects.get(pk=other['id']).name_key, 'algebre lineaire')

    def test_field_validation(self):
        invalid = [('name', ''), ('name', '   '), ('name', 12), ('name', None), ('name', 'x' * 81),
            ('code', ''), ('code', 'A'), ('code', '-AB'), ('code', 'AB CD'), ('code', 'É1'), ('code', 'A' * 21), ('code', 12),
            ('description', 'x' * 1001), ('description', ['x']), ('archived', True), ('created_by', str(self.other.pk))]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                r = self.create_subject(**{field: value}); self.assertEqual(r.status_code, 400, r.data)
                self.assertIn(field, r.data['error']['fields'])
        r = self.post('subjects/', {}); self.assertEqual(set(r.data['error']['fields']), {'name', 'code'})
        self.assertEqual(self.post('subjects/', [], ).data['error']['fields'], {'non_field_errors': ['Envoyez un objet JSON.']})
        self.assertEqual(Subject.objects.count(), 1)
        for value in ('true', 1, None):
            self.assertEqual(self.patch(f'subjects/{self.subject.pk}/', {'archived': value}).status_code, 400, value)

    def test_list_search_filters_ordering_and_pagination(self):
        for i in range(21): Subject.objects.create(name=f'Option {i:02d}', code=f'OPT{i:02d}', created_by=self.other, archived=i % 2 == 0)
        r = self.client.get('/api/subjects/'); self.assertEqual((r.data['count'], len(r.data['results']), r.data['page_size']), (22, 20, 20))
        self.assertEqual(r.data['results'][0]['name'], 'Mathématiques'); self.assertEqual(r.data['results'][1]['name'], 'Option 00')
        self.assertEqual(len(self.client.get('/api/subjects/?page=2').data['results']), 2)
        self.assertEqual(self.client.get('/api/subjects/?page=x').status_code, 400)
        self.assertEqual(self.client.get('/api/subjects/?q=MATHEMATIQUES').data['count'], 1)
        self.assertEqual(self.client.get('/api/subjects/?q=opt1').data['count'], 10)
        self.assertEqual(self.client.get('/api/subjects/?archived=true').data['count'], 11)
        self.assertEqual(self.client.get('/api/subjects/?archived=false').data['count'], 11)
        self.assertEqual(self.client.get('/api/subjects/?archived=maybe').data['count'], 22)
        other = self.client.get('/api/subjects/', {'q': 'option 03'}).data['results'][0]
        self.assertEqual((other['can_edit'], other['created_by']['last_name']), (False, 'Jlassi'))

    def test_only_creator_or_admin_can_change_a_subject(self):
        uid = self.create_subject().data['id']; c = self.as_user(self.other)
        r = c.get(f'/api/subjects/{uid}/'); self.assertEqual(r.status_code, 200); self.assertFalse(r.data['can_edit'])
        r = self.patch(f'subjects/{uid}/', {'name': 'Piratage'}, c); self.assertEqual((r.status_code, r.data['error']['code']), (403, 'permission_denied'))
        self.assertEqual(c.delete(f'/api/subjects/{uid}/').status_code, 403)
        self.assertEqual(Subject.objects.get(pk=uid).name, 'Physique quantique')
        admin = self.as_user(self.admin)
        r = self.patch(f'subjects/{uid}/', {'description': 'Revue par l’administration.'}, admin); self.assertEqual(r.status_code, 200, r.data); self.assertTrue(r.data['can_edit'])
        r = self.patch(f'subjects/{uid}/', {'archived': True}); self.assertEqual(r.status_code, 200); self.assertTrue(r.data['archived'])
        self.assertEqual(Subject.objects.get(pk=uid).created_by_id, self.teacher.pk)
        self.assertEqual(admin.delete(f'/api/subjects/{uid}/').status_code, 204); self.assertFalse(Subject.objects.filter(pk=uid).exists())

    def test_archived_subject_cannot_be_chosen_but_existing_courses_keep_it(self):
        course = self.post('courses/', self.course_data()).data
        self.assertEqual(self.patch(f'subjects/{self.subject.pk}/', {'archived': True}).status_code, 200)
        r = self.post('courses/', self.course_data()); self.assertEqual(r.status_code, 400); self.assertIn('subject_id', r.data['error']['fields'])
        r = self.patch(f'courses/{course["id"]}/', {'title': 'Analyse réelle, deuxième partie'}); self.assertEqual(r.status_code, 200, r.data)
        r = self.patch(f'courses/{course["id"]}/', {'subject_id': str(self.subject.pk)}); self.assertEqual(r.status_code, 200, r.data)
        fresh = Subject.objects.create(name='Statistiques', code='STAT', created_by=self.teacher)
        self.assertEqual(self.patch(f'courses/{course["id"]}/', {'subject_id': str(fresh.pk)}).status_code, 200)
        r = self.patch(f'courses/{course["id"]}/', {'subject_id': str(self.subject.pk)}); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['fields'], {'subject_id': ['Cette matière est archivée : choisissez-en une autre.']})
        self.assertEqual(Course.objects.get(pk=course['id']).subject_id, fresh.pk)

    def test_delete_only_unused_subjects(self):
        course = self.make_course(status='ARCHIVED')
        r = self.client.delete(f'/api/subjects/{self.subject.pk}/'); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Cette matière est utilisée par des cours : archivez-la plutôt.')
        self.assertEqual(self.client.get(f'/api/subjects/{self.subject.pk}/').data['courses_count'], 1)
        self.assertTrue(Subject.objects.filter(pk=self.subject.pk).exists())
        course.subject = Subject.objects.create(name='Autre', code='AUT', created_by=self.teacher); course.save()
        self.assertEqual(self.client.delete(f'/api/subjects/{self.subject.pk}/').status_code, 204)
        for uid in ('bad', '0' * 24): self.assertEqual(self.client.get(f'/api/subjects/{uid}/').status_code, 404)

    def test_students_and_anonymous_users_are_refused(self):
        uid = str(self.subject.pk)
        for client, status in ((self.as_user(self.student), 403), (APIClient(), 401)):
            self.assertEqual(client.get('/api/subjects/').status_code, status)
            self.assertEqual(client.get(f'/api/subjects/{uid}/').status_code, status)
            self.assertEqual(self.post('subjects/', {'name': 'Chimie', 'code': 'CHI'}, client).status_code, status)
            self.assertEqual(self.patch(f'subjects/{uid}/', {'name': 'Chimie'}, client).status_code, status)
            self.assertEqual(client.delete(f'/api/subjects/{uid}/').status_code, status)
        self.assertEqual(Subject.objects.get(pk=uid).name, 'Mathématiques')
