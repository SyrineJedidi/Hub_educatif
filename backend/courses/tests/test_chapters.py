from courses.models import Chapter, Course
from .base import CourseTestCase


class ChapterTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.course = self.make_course(); self.base = f'courses/{self.course.pk}/chapters/'

    def create(self, title, **kwargs):
        r = self.post(self.base, {'title': title, **kwargs}); self.assertEqual(r.status_code, 201, r.data); return r.data

    def positions(self):
        return list(Chapter.objects.filter(course=self.course).order_by('position').values_list('title', 'position'))

    def test_create_appends_at_the_end(self):
        before = Course.objects.get(pk=self.course.pk).updated_at
        first = self.create('  Limites  ', description='Notion de limite.')
        self.assertEqual(first, {'id': first['id'], 'course_id': str(self.course.pk), 'title': 'Limites', 'description': 'Notion de limite.', 'position': 1, 'resources': []})
        self.assertEqual((self.create('Dérivées')['position'], self.create('Intégrales', description='')['position']), (2, 3))
        self.assertGreaterEqual(Course.objects.get(pk=self.course.pk).updated_at, before)
        self.assertEqual((self.version(self.course), self.events), (1, []))
        r = self.client.get('/api/' + self.base); self.assertEqual([c['title'] for c in r.data['results']], ['Limites', 'Dérivées', 'Intégrales'])
        self.assertEqual(self.client.get(f'/api/{self.base}{first["id"]}/').status_code, 405)

    def test_field_errors(self):
        chapter = self.create('Limites')
        for field, value in [('title', ''), ('title', '  '), ('title', 12), ('title', None), ('title', 'x' * 121),
                ('description', 'x' * 1001), ('description', None), ('position', 4), ('course_id', str(self.course.pk))]:
            with self.subTest(field=field, value=value):
                r = self.post(self.base, {'title': 'Valide', field: value}); self.assertEqual(r.status_code, 400, r.data); self.assertIn(field, r.data['error']['fields'])
                r = self.patch(f'{self.base}{chapter["id"]}/', {field: value}); self.assertEqual(r.status_code, 400, r.data); self.assertIn(field, r.data['error']['fields'])
        self.assertEqual(self.post(self.base, []).status_code, 400)
        self.assertEqual(self.positions(), [('Limites', 1)])

    def test_rename_bumps_the_version_but_description_does_not(self):
        chapter = self.create('Limites')
        r = self.patch(f'{self.base}{chapter["id"]}/', {'description': 'Approche intuitive.'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['description'], self.version(self.course)), ('Approche intuitive.', 1))
        self.assertEqual(self.patch(f'{self.base}{chapter["id"]}/', {'title': 'Limites'}).status_code, 200); self.assertEqual(self.version(self.course), 1)
        r = self.patch(f'{self.base}{chapter["id"]}/', {'title': 'Limites et continuité'})
        self.assertEqual((r.data['title'], r.data['description'], r.data['position']), ('Limites et continuité', 'Approche intuitive.', 1))
        self.assertEqual((self.version(self.course), self.reasons()), (2, ['chapters_changed']))
        self.assertEqual(self.events[0]['resource_id'], None)

    def test_reorder_takes_exactly_the_course_chapters(self):
        a, b, c = (self.create(t)['id'] for t in ('A', 'B', 'C'))
        r = self.post(self.base + 'reorder/', {'chapter_ids': [c, a, b]}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([(x['title'], x['position']) for x in r.data['results']], [('C', 1), ('A', 2), ('B', 3)])
        self.assertEqual((self.version(self.course), self.reasons()), (2, ['chapters_changed']))
        self.assertEqual(self.post(self.base + 'reorder/', {'chapter_ids': [c, a, b]}).status_code, 200); self.assertEqual(self.version(self.course), 2)
        foreign = self.make_chapter(self.make_course(title='Autre cours')).pk
        message = {'chapter_ids': ['Envoyez exactement les chapitres de ce cours, sans doublon.']}
        for ids in ([c, a], [c, a, b, str(foreign)], [c, a, a], [c, a, str(foreign)], [c, a, 'inconnu'], []):
            with self.subTest(ids=ids):
                r = self.post(self.base + 'reorder/', {'chapter_ids': ids}); self.assertEqual(r.status_code, 400); self.assertEqual(r.data['error']['fields'], message)
        for body in ({'chapter_ids': c}, {}, {'chapter_ids': [c, a, b], 'extra': 1}, []):
            self.assertEqual(self.post(self.base + 'reorder/', body).status_code, 400, body)
        self.assertEqual(self.positions(), [('C', 1), ('A', 2), ('B', 3)]); self.assertEqual(self.version(self.course), 2)

    def test_reorder_survives_gaps_left_by_old_data(self):
        for title, position in (('A', 5), ('B', 7), ('C', 9)): Chapter.objects.create(course=self.course, title=title, position=position)
        ids = {c.title: str(c.pk) for c in Chapter.objects.filter(course=self.course)}
        r = self.post(self.base + 'reorder/', {'chapter_ids': [ids['B'], ids['C'], ids['A']]}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.positions(), [('B', 1), ('C', 2), ('A', 3)])
        empty = self.make_course(title='Vide')
        r = self.post(f'courses/{empty.pk}/chapters/reorder/', {'chapter_ids': []}); self.assertEqual((r.status_code, r.data), (200, {'results': []}))

    def test_delete_only_empty_chapters_and_compact_positions(self):
        a, b, c = (self.create(t)['id'] for t in ('A', 'B', 'C'))
        self.add_resource(self.course, b)
        r = self.client.delete(f'/api/{self.base}{b}/'); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Supprimez ou déplacez d’abord les ressources de ce chapitre.')
        self.events.clear(); before = self.version(self.course)
        self.assertEqual(self.client.delete(f'/api/{self.base}{a}/').status_code, 204)
        self.assertEqual(self.positions(), [('B', 1), ('C', 2)])
        self.assertEqual((self.version(self.course), self.reasons()), (before + 1, ['chapters_changed']))
        self.assertEqual(self.create('D')['position'], 3)

    def test_foreign_or_unknown_chapters_are_not_found(self):
        mine = self.create('A')['id']
        foreign = self.make_chapter(self.make_course(title='Autre cours', teacher=self.other, groups=[self.other_group]))
        for chapter_id in (str(foreign.pk), '0' * 24, 'inconnu'):
            for method, path, data in (('patch', f'{self.base}{chapter_id}/', {'title': 'X'}), ('delete', f'{self.base}{chapter_id}/', None),
                    ('post', f'{self.base}{chapter_id}/resources/reorder/', {'resource_ids': []}), ('get', f'courses/{self.course.pk}/resources/?chapter={chapter_id}', None)):
                with self.subTest(method=method, chapter=chapter_id):
                    r = getattr(self.client, method)('/api/' + path, data, format='json'); self.assertEqual(r.status_code, 404)
                    self.assertEqual((r.data['error']['code'], r.data['error']['message']), ('not_found', 'Chapitre introuvable dans ce cours.'))
        other = self.as_user(self.other)
        self.assertEqual(self.patch(f'{self.base}{mine}/', {'title': 'X'}, other).status_code, 404)
        self.assertEqual(other.get('/api/' + self.base).status_code, 404)
        self.assertEqual(Chapter.objects.get(pk=foreign.pk).title, 'Chapitre 1')
