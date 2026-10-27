from datetime import timedelta
from django.utils import timezone
from courses.models import Course, CourseGroup, Subject
from .base import MP3, CourseTestCase


class CourseTests(CourseTestCase):
    def test_teacher_creates_a_draft_they_own(self):
        r = self.post('courses/', self.course_data()); self.assertEqual(r.status_code, 201, r.data)
        course = Course.objects.get(pk=r.data['id'])
        self.assertEqual((course.teacher_id, course.status, course.content_version, course.published_at), (self.teacher.pk, 'DRAFT', 1, None))
        self.assertEqual((r.data['status'], r.data['status_label'], r.data['can_delete'], r.data['content_version']), ('DRAFT', 'Brouillon', True, 1))
        self.assertEqual(r.data['subject'], {'id': str(self.subject.pk), 'name': 'Mathématiques', 'code': 'MATH'})
        self.assertEqual(r.data['teacher'], {'id': str(self.teacher.pk), 'first_name': 'Amel', 'last_name': 'Ben Salah'})
        self.assertEqual(r.data['groups'], [{'id': str(self.group.pk), 'name': 'Analyse', 'code': 'AN1', 'archived': False}])
        self.assertEqual((r.data['chapters'], r.data['chapters_count'], r.data['resources_count'], r.data['processing_count']), ([], 0, 0, 0))
        self.assertEqual(r.data['publication_blockers'], ['Ajoutez au moins un chapitre avant de publier.', 'Ajoutez au moins une ressource avant de publier.'])
        self.assertNotIn('email', str(r.data))
        data = self.course_data(); del data['group_ids']
        r = self.post('courses/', data)
        self.assertEqual(r.status_code, 201, r.data); self.assertEqual(r.data['groups'], [])
        self.assertIn('Partagez le cours avec au moins un groupe actif de l’enseignant.', r.data['publication_blockers'])

    def test_field_errors_on_creation_and_update(self):
        course = self.make_course()
        ids = [f'{i:024x}' for i in range(1, 22)]
        invalid = [('title', ''), ('title', '   '), ('title', 12), ('title', None), ('title', 'x' * 121),
            ('description', ''), ('description', ' \n '), ('description', None), ('description', 'x' * 2001), ('description', []),
            ('subject_id', ''), ('subject_id', 'invalide'), ('subject_id', '0' * 24), ('subject_id', None), ('subject_id', 12),
            ('group_ids', 'abc'), ('group_ids', None), ('group_ids', ['bad']), ('group_ids', ['0' * 24]), ('group_ids', [12]), ('group_ids', ids),
            ('group_ids', [str(self.other_group.pk)]), ('teacher_id', str(self.teacher.pk)), ('status', 'PUBLISHED'), ('content_version', 9)]
        for field, value in invalid:
            for method in ('create', 'patch'):
                with self.subTest(field=field, value=value, method=method):
                    r = self.post('courses/', self.course_data(**{field: value})) if method == 'create' else self.patch(f'courses/{course.pk}/', {field: value})
                    self.assertEqual(r.status_code, 400, r.data); self.assertIn(field, r.data['error']['fields'])
        self.assertEqual(Course.objects.count(), 1)
        course.refresh_from_db(); self.assertEqual((course.title, course.status, course.content_version), ('Analyse réelle', 'DRAFT', 1))
        self.assertEqual(list(CourseGroup.objects.filter(course=course).values_list('group_id', flat=True)), [self.group.pk])
        self.assertEqual(set(self.post('courses/', {}).data['error']['fields']), {'title', 'description', 'subject_id'})
        self.assertEqual(set(self.post('courses/', {}, self.as_user(self.admin)).data['error']['fields']), {'title', 'description', 'subject_id', 'teacher_id'})
        self.assertEqual(self.post('courses/', []).data['error']['fields'], {'non_field_errors': ['Envoyez un objet JSON.']})
        self.assertEqual(self.patch(f'courses/{course.pk}/', 'texte').status_code, 400)

    def test_groups_must_be_active_and_taught_by_the_course_teacher(self):
        self.second_group.archived = True; self.second_group.save()
        cases = [([str(self.other_group.pk)], 'Le groupe « Physique » doit être affecté à l’enseignant du cours.'),
            ([str(self.second_group.pk)], 'Le groupe « Algèbre » est archivé.'), (['0' * 24], 'Sélectionnez des groupes existants.')]
        for ids, message in cases:
            r = self.post('courses/', self.course_data(group_ids=[str(self.group.pk), *ids]))
            self.assertEqual(r.status_code, 400); self.assertEqual(r.data['error']['fields'], {'group_ids': [message]})
        r = self.post('courses/', self.course_data(group_ids=[str(self.other_group.pk), '0' * 24, str(self.second_group.pk), '0' * 24]))
        self.assertEqual(len(r.data['error']['fields']['group_ids']), 3)
        r = self.post('courses/', self.course_data(group_ids=[str(self.group.pk)] * 25)); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CourseGroup.objects.filter(course_id=Course.objects.get(pk=r.data['id']).pk).count(), 1)
        self.assertEqual(Course.objects.count(), 1)

    def test_admin_creates_for_an_active_teacher(self):
        admin = self.as_user(self.admin)
        r = self.post('courses/', self.course_data(), admin); self.assertEqual(r.status_code, 400); self.assertIn('teacher_id', r.data['error']['fields'])
        r = self.post('courses/', self.course_data(teacher_id=str(self.teacher.pk)), admin); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Course.objects.get(pk=r.data['id']).teacher_id, self.teacher.pk)
        r = self.post('courses/', self.course_data(teacher_id=str(self.other.pk)), admin); self.assertEqual(r.status_code, 400)
        self.assertIn('group_ids', r.data['error']['fields'])
        r = self.post('courses/', self.course_data(teacher_id=str(self.other.pk), group_ids=[str(self.other_group.pk)]), admin); self.assertEqual(r.status_code, 201, r.data)
        for user in (self.student, self.admin):
            r = self.post('courses/', self.course_data(teacher_id=str(user.pk), group_ids=[]), admin)
            self.assertEqual(r.data['error']['fields'], {'teacher_id': ['Sélectionnez un enseignant actif.']})
        r = self.post('courses/', self.course_data(teacher_id='0' * 24), admin)
        self.assertEqual(r.data['error']['fields'], {'teacher_id': ['Sélectionnez un enseignant actif existant.']})
        self.other.is_active = False; self.other.save()
        r = self.post('courses/', self.course_data(teacher_id=str(self.other.pk), group_ids=[str(self.other_group.pk)]), admin)
        self.assertEqual(r.status_code, 400); self.assertIn('teacher_id', r.data['error']['fields'])
        self.assertEqual(Course.objects.count(), 2)

    def test_partial_update_keeps_other_fields(self):
        course = self.make_course(groups=[self.group, self.second_group])
        r = self.patch(f'courses/{course.pk}/', {'title': '  Analyse, partie 2  '}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['title'], r.data['description'], len(r.data['groups'])), ('Analyse, partie 2', 'Dérivées et intégrales.', 2))
        other = Subject.objects.create(name='Statistiques', code='STAT', created_by=self.other)
        r = self.patch(f'courses/{course.pk}/', {'subject_id': str(other.pk), 'description': 'Lois usuelles.'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['subject']['code'], r.data['description']), ('STAT', 'Lois usuelles.'))
        self.assertEqual((self.version(course), self.events), (1, []))

    def test_group_replacement_bumps_the_version_only_when_the_set_changes(self):
        course = self.make_course()
        r = self.patch(f'courses/{course.pk}/', {'group_ids': [str(self.second_group.pk), str(self.group.pk)]}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([g['name'] for g in r.data['groups']], ['Algèbre', 'Analyse']); self.assertEqual(r.data['content_version'], 2)
        self.assertEqual(self.events, [{'signal': self.events[0]['signal'], 'sender': Course, 'course_id': str(course.pk), 'resource_id': None, 'reason': 'groups_changed'}])
        self.assertEqual(self.patch(f'courses/{course.pk}/', {'group_ids': [str(self.group.pk), str(self.second_group.pk)]}).data['content_version'], 2)
        r = self.patch(f'courses/{course.pk}/', {'group_ids': [str(self.second_group.pk)]})
        self.assertEqual(([g['id'] for g in r.data['groups']], r.data['content_version']), ([str(self.second_group.pk)], 3))
        r = self.patch(f'courses/{course.pk}/', {'group_ids': []}); self.assertEqual((r.status_code, r.data['groups'], r.data['content_version']), (200, [], 4))
        self.assertEqual(self.reasons(), ['groups_changed'] * 3)
        self.assertFalse(CourseGroup.objects.filter(course=course).exists())

    def test_published_course_keeps_at_least_one_group(self):
        course, _, _ = self.published_course()
        r = self.patch(f'courses/{course.pk}/', {'group_ids': []}); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['fields'], {'group_ids': ['Un cours publié doit rester partagé avec au moins un groupe.']})
        r = self.patch(f'courses/{course.pk}/', {'group_ids': [str(self.second_group.pk)], 'title': 'Analyse réelle, semestre 2'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['status'], r.data['title'], r.data['publication_blockers']), ('PUBLISHED', 'Analyse réelle, semestre 2', []))

    def test_admin_reassigns_the_teacher_with_their_groups(self):
        course = self.make_course(); admin = self.as_user(self.admin)
        r = self.patch(f'courses/{course.pk}/', {'teacher_id': str(self.other.pk)}, admin); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['fields'], {'group_ids': ['Le groupe « Analyse » doit être affecté à l’enseignant du cours.']})
        r = self.patch(f'courses/{course.pk}/', {'teacher_id': str(self.other.pk), 'group_ids': [str(self.other_group.pk)]}, admin); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['teacher']['id'], [g['id'] for g in r.data['groups']]), (str(self.other.pk), [str(self.other_group.pk)]))
        self.assertEqual(self.reasons(), ['groups_changed'])
        self.assertEqual(self.client.get(f'/api/courses/{course.pk}/').status_code, 404)
        self.assertEqual(self.as_user(self.other).get(f'/api/courses/{course.pk}/').status_code, 200)
        empty = self.make_course(groups=[])
        r = self.patch(f'courses/{empty.pk}/', {'teacher_id': str(self.other.pk)}, admin); self.assertEqual(r.status_code, 200, r.data)
        r = self.patch(f'courses/{empty.pk}/', {'teacher_id': str(self.teacher.pk)}, self.as_user(self.other))
        self.assertEqual(r.data['error']['fields'], {'teacher_id': ['Ce champ ne peut pas être modifié.']})

    def test_list_scope_filters_ordering_and_pagination(self):
        archived = self.make_course(title='Topologie', status='ARCHIVED', groups=[self.second_group])
        published = self.make_course(title='Probabilités', status='PUBLISHED')
        foreign = self.make_course(title='Mécanique', teacher=self.other, groups=[self.other_group])
        draft = self.make_course(title='Analyse complexe', groups=[])
        base = timezone.now()
        for offset, course in enumerate((draft, published, archived, foreign)):
            Course.objects.filter(pk=course.pk).update(updated_at=base - timedelta(minutes=offset))
        ids = lambda r: [item['id'] for item in r.data['results']]
        r = self.client.get('/api/courses/'); self.assertEqual(ids(r), [str(draft.pk), str(published.pk), str(archived.pk)])
        self.assertEqual(ids(self.as_user(self.other).get('/api/courses/')), [str(foreign.pk)])
        admin = self.as_user(self.admin); self.assertEqual(admin.get('/api/courses/').data['count'], 4)
        self.assertEqual(ids(self.client.get('/api/courses/', {'q': '  ANALYSE '})), [str(draft.pk)])
        self.assertEqual(ids(self.client.get('/api/courses/?status=ARCHIVED')), [str(archived.pk)])
        self.assertEqual(ids(self.client.get(f'/api/courses/?group={self.second_group.pk}')), [str(archived.pk)])
        self.assertEqual(self.client.get(f'/api/courses/?group={self.other_group.pk}').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/courses/?subject={self.subject.pk}').data['count'], 3)
        self.assertEqual(ids(admin.get(f'/api/courses/?teacher={self.other.pk}')), [str(foreign.pk)])
        self.assertEqual(self.client.get(f'/api/courses/?teacher={self.other.pk}').data['count'], 3)
        r = self.client.get('/api/courses/?status=PUBLIE'); self.assertEqual(r.status_code, 400); self.assertIn('status', r.data['error']['fields'])
        for parameter in ('subject', 'group'): self.assertEqual(self.client.get(f'/api/courses/?{parameter}=bad').status_code, 404)
        self.assertEqual(admin.get('/api/courses/?teacher=' + '0' * 24).status_code, 404)
        self.assertEqual(self.client.get('/api/courses/?page=zero').status_code, 400)
        for i in range(20): self.make_course(title=f'Séance {i}', groups=[])
        r = self.client.get('/api/courses/'); self.assertEqual((r.data['count'], len(r.data['results'])), (23, 20))
        self.assertEqual(len(self.client.get('/api/courses/?page=2').data['results']), 3)
        self.assertNotIn('chapters', r.data['results'][0]); self.assertNotIn('publication_blockers', r.data['results'][0])

    def test_counters_in_list_and_detail(self):
        course = self.make_course(); chapter = self.make_chapter(course); self.make_chapter(course, 'Chapitre 2')
        self.add_resource(course, chapter); self.add_resource(course, chapter, MP3, 'cours.mp3', 'Cours enregistré')
        item = self.client.get('/api/courses/').data['results'][0]
        self.assertEqual((item['chapters_count'], item['resources_count'], item['processing_count']), (2, 2, 1))
        detail = self.client.get(f'/api/courses/{course.pk}/').data
        self.assertEqual([len(c['resources']) for c in detail['chapters']], [2, 0]); self.assertEqual(detail['publication_blockers'], [])
        self.work()
        self.assertEqual(self.client.get(f'/api/courses/{course.pk}/').data['processing_count'], 0)
