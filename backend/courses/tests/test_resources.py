from courses.models import Chapter, ProcessingJob, Resource, ResourceSegment, ResourceView
from .base import MP3, CourseTestCase, pdf_bytes


class ResourceManagementTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.course = self.make_course(); self.first = self.make_chapter(self.course, 'Dérivées'); self.second = self.make_chapter(self.course, 'Intégrales')
        self.base = f'courses/{self.course.pk}/resources/'

    def resource(self, chapter, title, content=None, name='support.pdf'):
        return self.add_resource(self.course, chapter, content if content is not None else pdf_bytes([f'{title} : un document de cours assez long pour être indexé.']), name, title)

    def layout(self):
        return [(r.chapter.title, r.title, r.position) for r in sorted(Resource.objects.filter(course=self.course), key=lambda r: (r.chapter.position, r.position))]

    def test_list_detail_and_manager_shape(self):
        b = self.resource(self.second, 'B'); a = self.resource(self.first, 'A'); audio = self.resource(self.first, 'Audio', MP3, 'cours.mp3')
        r = self.client.get('/api/' + self.base); self.assertEqual([x['title'] for x in r.data['results']], ['A', 'Audio', 'B'])
        self.assertEqual([x['title'] for x in self.client.get(f'/api/{self.base}?chapter={self.second.pk}').data['results']], ['B'])
        r = self.client.get(f'/api/{self.base}{a["id"]}/'); self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {'id', 'course_id', 'chapter_id', 'kind', 'kind_label', 'title', 'description', 'position', 'original_name', 'mime_type',
            'size', 'page_count', 'duration_seconds', 'language', 'processing_status', 'processing_label', 'processing_error', 'text_version',
            'segments_count', 'file_url', 'download_url', 'job', 'created_at', 'updated_at'})
        self.assertEqual((r.data['course_id'], r.data['chapter_id'], r.data['kind_label'], r.data['processing_label']), (str(self.course.pk), str(self.first.pk), 'Document PDF', 'Prêt'))
        self.assertEqual((r.data['file_url'], r.data['download_url']), (f'/api/courses/resources/{a["id"]}/file/', f'/api/courses/resources/{a["id"]}/file/?download=1'))
        self.assertEqual(set(r.data['job']), {'status', 'status_label', 'attempts', 'provider', 'model_name', 'audio_seconds', 'processing_ms', 'segments_count', 'error', 'created_at', 'finished_at'})
        self.assertEqual((r.data['job']['status_label'], r.data['job']['provider'], r.data['job']['model_name']), ('Terminé', 'pypdf', 'pypdf 6.21.2'))
        self.assertEqual((audio['kind_label'], audio['processing_label'], audio['job']['status_label'], audio['job']['attempts']), ('Enregistrement audio', 'En attente', 'En attente', 0))
        self.assertNotIn('sha256', str(r.data)); self.assertNotIn('uploaded_by', r.data)
        other_course = self.make_course(title='Autre cours'); other = self.add_resource(other_course, self.make_chapter(other_course))
        for rid in (other['id'], '0' * 24, 'inconnu'):
            r = self.client.get(f'/api/{self.base}{rid}/'); self.assertEqual((r.status_code, r.data['error']['message']), (404, 'Ressource introuvable dans ce cours.'))
        self.assertEqual(self.client.get(f'/api/courses/{other_course.pk}/resources/').data['results'][0]['id'], other['id'])
        self.assertNotIn(b['id'], [x['id'] for x in self.client.get(f'/api/courses/{other_course.pk}/resources/').data['results']])

    def test_rename_and_description_changes(self):
        a = self.resource(self.first, 'A'); self.events.clear(); before = self.version(self.course)
        r = self.patch(f'{self.base}{a["id"]}/', {'description': 'Fiche de synthèse.'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['description'], self.version(self.course), self.events), ('Fiche de synthèse.', before, []))
        r = self.patch(f'{self.base}{a["id"]}/', {'title': '  Fiche A  '}); self.assertEqual(r.data['title'], 'Fiche A')
        self.assertEqual((self.version(self.course), self.reasons(), self.events[0]['resource_id']), (before + 1, ['resource_updated'], a['id']))
        self.assertEqual(self.patch(f'{self.base}{a["id"]}/', {'title': 'Fiche A', 'chapter_id': str(self.first.pk)}).status_code, 200)
        self.assertEqual(self.version(self.course), before + 1)

    def test_field_errors(self):
        a = self.resource(self.first, 'A')
        foreign = self.make_chapter(self.make_course(title='Autre cours'))
        for field, value in [('title', ''), ('title', ' '), ('title', 'x' * 121), ('title', None), ('description', 'x' * 1001),
                ('chapter_id', 'bad'), ('chapter_id', '0' * 24), ('chapter_id', str(foreign.pk)), ('chapter_id', None),
                ('kind', 'AUDIO'), ('position', 3), ('file', 'x'), ('processing_status', 'READY')]:
            with self.subTest(field=field, value=value):
                r = self.patch(f'{self.base}{a["id"]}/', {field: value}); self.assertEqual(r.status_code, 400, r.data); self.assertIn(field, r.data['error']['fields'])
        self.assertEqual(self.patch(f'{self.base}{a["id"]}/', {'chapter_id': '0' * 24}).data['error']['fields'], {'chapter_id': ['Sélectionnez un chapitre de ce cours.']})
        self.assertEqual(self.layout(), [('Dérivées', 'A', 1)])

    def test_move_appends_to_the_target_and_compacts_the_source(self):
        a = self.resource(self.first, 'A'); b = self.resource(self.first, 'B'); c = self.resource(self.first, 'C'); d = self.resource(self.second, 'D')
        self.events.clear(); before = self.version(self.course)
        r = self.patch(f'{self.base}{a["id"]}/', {'chapter_id': str(self.second.pk), 'title': 'A déplacée'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['chapter_id'], r.data['position'], r.data['title']), (str(self.second.pk), 2, 'A déplacée'))
        self.assertEqual(self.layout(), [('Dérivées', 'B', 1), ('Dérivées', 'C', 2), ('Intégrales', 'D', 1), ('Intégrales', 'A déplacée', 2)])
        self.assertEqual(set(ResourceSegment.objects.filter(resource_id=Resource.objects.get(pk=a['id']).pk).values_list('chapter_id', flat=True)), {self.second.pk})
        self.assertEqual(set(ResourceSegment.objects.filter(resource_id=Resource.objects.get(pk=b['id']).pk).values_list('chapter_id', flat=True)), {self.first.pk})
        self.assertEqual((self.version(self.course), self.reasons()), (before + 1, ['resource_updated']))

    def test_reorder_within_a_chapter(self):
        a, b, c = (self.resource(self.first, t)['id'] for t in 'ABC'); other = self.resource(self.second, 'D')['id']
        path = f'courses/{self.course.pk}/chapters/{self.first.pk}/resources/reorder/'; self.events.clear(); before = self.version(self.course)
        r = self.post(path, {'resource_ids': [c, a, b]}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([(x['title'], x['position']) for x in r.data['results']], [('C', 1), ('A', 2), ('B', 3)])
        self.assertEqual((self.version(self.course), self.reasons(), self.events[0]['resource_id']), (before + 1, ['resource_updated'], None))
        self.assertEqual(self.post(path, {'resource_ids': [c, a, b]}).status_code, 200); self.assertEqual(self.version(self.course), before + 1)
        message = {'resource_ids': ['Envoyez exactement les ressources de ce chapitre, sans doublon.']}
        for ids in ([c, a], [c, a, b, other], [c, c, a], [c, a, other]):
            self.assertEqual(self.post(path, {'resource_ids': ids}).data['error']['fields'], message, ids)
        self.assertEqual(self.post(path, {'chapter_ids': [c, a, b]}).status_code, 400)
        self.assertEqual(self.layout(), [('Dérivées', 'C', 1), ('Dérivées', 'A', 2), ('Dérivées', 'B', 3), ('Intégrales', 'D', 1)])

    def test_delete_removes_history_segments_jobs_and_file(self):
        a = self.resource(self.first, 'A'); b = self.resource(self.first, 'B'); c = self.resource(self.first, 'C')
        pk = Resource.objects.get(pk=b['id']).pk; name = Resource.objects.get(pk=pk).file.name.split('/')[-1]
        ResourceView.objects.create(student=self.student, resource_id=pk, course=self.course)
        ResourceView.objects.create(student=self.student, resource_id=Resource.objects.get(pk=a['id']).pk, course=self.course)
        self.assertIn(name, self.stored_files()); self.events.clear(); before = self.version(self.course)
        self.assertEqual(self.client.delete(f'/api/{self.base}{b["id"]}/').status_code, 204)
        self.assertFalse(Resource.objects.filter(pk=pk).exists())
        for model in (ResourceView, ResourceSegment, ProcessingJob): self.assertFalse(model.objects.filter(resource_id=pk).exists(), model.__name__)
        self.assertNotIn(name, self.stored_files()); self.assertEqual(len(self.stored_files()), 2)
        self.assertEqual(ResourceView.objects.count(), 1)
        self.assertEqual(self.layout(), [('Dérivées', 'A', 1), ('Dérivées', 'C', 2)])
        self.assertEqual(self.events[0]['reason'], 'resource_deleted'); self.assertEqual(self.events[0]['resource_id'], b['id'])
        self.assertEqual(self.version(self.course), before + 1)
        self.assertEqual(self.client.delete(f'/api/{self.base}{b["id"]}/').status_code, 404)
        self.assertEqual(self.resource(self.first, 'E')['position'], 3)
        self.assertTrue(Chapter.objects.filter(pk=self.first.pk).exists())
