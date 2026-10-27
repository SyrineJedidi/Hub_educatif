from courses.models import Chapter, Course, CourseGroup, ProcessingJob, Resource, ResourceSegment, ResourceView
from .base import MP3, CourseTestCase, pdf_bytes


class CourseLifecycleTests(CourseTestCase):
    def ready_course(self):
        course = self.make_course(); chapter = self.make_chapter(course)
        resource = self.add_resource(course, chapter)
        return course, chapter, resource

    def action(self, course, name, client=None):
        return self.post(f'courses/{course.pk}/{name}/', client=client)

    def blockers(self, course, client=None):
        r = self.action(course, 'publish', client); self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['error']['code'], 'invalid')
        self.assertEqual(r.data['error']['fields']['publication'], (client or self.client).get(f'/api/courses/{course.pk}/').data['publication_blockers'])
        return r.data['error']['fields']['publication']

    def test_each_publication_blocker_on_its_own(self):
        course, chapter, resource = self.ready_course()
        self.assertEqual(self.client.get(f'/api/courses/{course.pk}/').data['publication_blockers'], [])
        Course.objects.filter(pk=course.pk).update(title='  ')
        self.assertEqual(self.blockers(course), ['Titre : Renseignez un titre non vide.'])
        Course.objects.filter(pk=course.pk).update(title='Analyse réelle', description='\n ')
        self.assertEqual(self.blockers(course), ['Description : Renseignez une description non vide.'])
        Course.objects.filter(pk=course.pk).update(description='Dérivées.')
        self.teacher.is_active = False; self.teacher.save()
        self.assertEqual(self.blockers(course, self.as_user(self.admin)), ['Enseignant : Sélectionnez un enseignant actif.'])
        self.teacher.is_active = True; self.teacher.save()
        self.subject.archived = True; self.subject.save()
        self.assertEqual(self.blockers(course), ['Matière : la matière « Mathématiques » est archivée.'])
        self.subject.archived = False; self.subject.save()
        no_group = ['Partagez le cours avec au moins un groupe actif de l’enseignant.']
        self.group.archived = True; self.group.save(); self.assertEqual(self.blockers(course), no_group)
        self.group.archived = False; self.group.teacher = self.other; self.group.save(); self.assertEqual(self.blockers(course), no_group)
        self.group.teacher = self.teacher; self.group.save(); CourseGroup.objects.filter(course=course).delete()
        self.assertEqual(self.blockers(course), no_group)
        CourseGroup.objects.create(course=course, group=self.group)
        self.assertEqual(self.client.delete(f'/api/courses/{course.pk}/resources/{resource["id"]}/').status_code, 204)
        self.assertEqual(self.blockers(course), ['Ajoutez au moins une ressource avant de publier.'])
        self.assertEqual(self.client.delete(f'/api/courses/{course.pk}/chapters/{chapter.pk}/').status_code, 204)
        self.assertEqual(self.blockers(course), ['Ajoutez au moins un chapitre avant de publier.', 'Ajoutez au moins une ressource avant de publier.'])
        self.assertEqual(Course.objects.get(pk=course.pk).status, 'DRAFT')

    def test_all_blockers_are_returned_together(self):
        course = self.make_course(groups=[]); Course.objects.filter(pk=course.pk).update(title=' ', description=' ')
        self.subject.archived = True; self.subject.save()
        self.assertEqual(self.blockers(course), ['Titre : Renseignez un titre non vide.', 'Description : Renseignez une description non vide.',
            'Matière : la matière « Mathématiques » est archivée.', 'Partagez le cours avec au moins un groupe actif de l’enseignant.',
            'Ajoutez au moins un chapitre avant de publier.', 'Ajoutez au moins une ressource avant de publier.'])
        self.assertEqual(self.events, [])

    def test_status_transitions_and_versions(self):
        course, _, _ = self.ready_course(); start = self.version(course); self.events.clear()
        r = self.action(course, 'publish'); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['status'], r.data['status_label'], r.data['publication_blockers'], r.data['can_delete']), ('PUBLISHED', 'Publié', [], False))
        first = Course.objects.get(pk=course.pk).published_at; self.assertIsNotNone(first)
        r = self.action(course, 'publish'); self.assertEqual(r.data['error']['fields'], {'status': ['Seul un cours en brouillon peut être publié.']})
        r = self.action(course, 'restore'); self.assertEqual(r.data['error']['fields'], {'status': ['Seul un cours archivé peut être restauré.']})
        r = self.action(course, 'unpublish'); self.assertEqual((r.status_code, r.data['status'], r.data['can_delete']), (200, 'DRAFT', False))
        r = self.action(course, 'unpublish'); self.assertEqual(r.data['error']['fields'], {'status': ['Seul un cours publié peut être retiré de la publication.']})
        self.assertEqual(self.action(course, 'publish').status_code, 200)
        self.assertEqual(Course.objects.get(pk=course.pk).published_at, first)
        r = self.action(course, 'archive'); self.assertEqual((r.data['status'], r.data['status_label'], r.data['publication_blockers']), ('ARCHIVED', 'Archivé', []))
        r = self.action(course, 'archive'); self.assertEqual(r.data['error']['fields'], {'status': ['Ce cours est déjà archivé.']})
        self.assertEqual(self.action(course, 'publish').status_code, 400)
        r = self.action(course, 'restore'); self.assertEqual((r.data['status'], r.data['published_at'] is not None), ('DRAFT', True))
        self.assertEqual(self.action(course, 'archive').data['status'], 'ARCHIVED')
        self.assertEqual(self.version(course), start + 6); self.assertEqual(self.reasons(), ['status_changed'] * 6)
        self.assertEqual({e['course_id'] for e in self.events}, {str(course.pk)}); self.assertEqual({e['resource_id'] for e in self.events}, {None})
        self.assertEqual(Course.objects.get(pk=course.pk).published_at, first)

    def test_actions_take_an_empty_body_and_respect_ownership(self):
        course, _, _ = self.ready_course()
        self.assertEqual(self.post(f'courses/{course.pk}/publish/', {'status': 'PUBLISHED'}).data['error']['fields'], {'status': ['Ce champ ne peut pas être modifié.']})
        self.assertEqual(self.post(f'courses/{course.pk}/archive/', []).status_code, 400)
        for name in ('publish', 'unpublish', 'archive', 'restore'):
            self.assertEqual(self.action(course, name, self.as_user(self.other)).status_code, 404, name)
            self.assertEqual(self.action(course, name, self.as_user(self.student)).status_code, 403, name)
        self.assertEqual(Course.objects.get(pk=course.pk).status, 'DRAFT')
        self.assertEqual(self.action(course, 'publish', self.as_user(self.admin)).status_code, 200)
        self.assertEqual(self.client.get(f'/api/courses/{course.pk}/publish/').status_code, 405)

    def test_archived_course_is_read_only(self):
        course, chapter, resource = self.ready_course()
        segment = ResourceSegment.objects.filter(resource_id=resource['id']).first()
        self.assertEqual(self.action(course, 'archive').status_code, 200); before = self.version(course); self.events.clear()
        base, rid = f'courses/{course.pk}/', resource['id']
        writes = [('patch', base, {'title': 'Nouveau titre'}), ('delete', base, None),
            ('post', base + 'chapters/', {'title': 'Nouveau chapitre'}), ('patch', f'{base}chapters/{chapter.pk}/', {'title': 'Renommé'}),
            ('delete', f'{base}chapters/{chapter.pk}/', None), ('post', base + 'chapters/reorder/', {'chapter_ids': [str(chapter.pk)]}),
            ('patch', f'{base}resources/{rid}/', {'title': 'Renommée'}), ('delete', f'{base}resources/{rid}/', None),
            ('post', f'{base}chapters/{chapter.pk}/resources/reorder/', {'resource_ids': [rid]}), ('post', f'{base}resources/{rid}/reprocess/', {}),
            ('patch', f'{base}resources/{rid}/segments/{segment.pk}/', {'text': 'Correction'})]
        for method, path, data in writes:
            with self.subTest(method=method, path=path):
                r = getattr(self.client, method)('/api/' + path, data, format='json'); self.assertEqual(r.status_code, 400, r.data)
                self.assertEqual(r.data['error']['fields'], {'status': ['Ce cours est archivé. Restaurez-le pour le modifier.']})
        r = self.upload(course, chapter, MP3, 'cours.mp3'); self.assertEqual(r.data['error']['fields'], {'status': ['Ce cours est archivé. Restaurez-le pour le modifier.']})
        for path in (base, base + 'chapters/', base + 'resources/', f'{base}resources/{rid}/', f'{base}resources/{rid}/segments/', base + 'statistics/'):
            self.assertEqual(self.client.get('/api/' + path).status_code, 200, path)
        self.assertEqual((self.version(course), self.events), (before, []))
        self.assertEqual((Chapter.objects.get(pk=chapter.pk).title, Resource.objects.get(pk=rid).title), ('Chapitre 1', 'Support'))
        self.assertEqual(ResourceSegment.objects.get(pk=segment.pk).edited, False); self.assertEqual(len(self.stored_files()), 1)
        self.assertEqual(self.action(course, 'restore').status_code, 200)
        self.assertEqual(self.patch(base, {'title': 'Nouveau titre'}).status_code, 200)

    def test_only_a_never_published_draft_can_be_deleted(self):
        course, _, _ = self.published_course()
        r = self.client.delete(f'/api/courses/{course.pk}/'); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Ce cours a déjà été publié : archivez-le plutôt que de le supprimer.')
        self.assertEqual(self.action(course, 'unpublish').status_code, 200)
        self.assertFalse(self.client.get(f'/api/courses/{course.pk}/').data['can_delete'])
        self.assertEqual(self.client.delete(f'/api/courses/{course.pk}/').status_code, 400)
        self.assertEqual(self.action(course, 'archive').status_code, 200)
        r = self.client.delete(f'/api/courses/{course.pk}/'); self.assertIn('status', r.data['error']['fields'])
        self.assertEqual(self.as_user(self.other).delete(f'/api/courses/{course.pk}/').status_code, 404)
        self.assertTrue(Course.objects.filter(pk=course.pk).exists())

    def test_deleting_a_draft_removes_every_child_and_file_but_nothing_else(self):
        keep, keep_chapter, kept = self.ready_course()
        course = self.make_course(groups=[self.group, self.second_group]); chapter = self.make_chapter(course); self.make_chapter(course, 'Annexe')
        pdf = self.add_resource(course, chapter, pdf_bytes(['Un autre document de cours sur les suites numériques.']))
        audio = self.add_resource(course, chapter, MP3, 'cours.mp3', 'Cours enregistré'); self.work()
        removed = [Resource.objects.get(pk=r['id']).pk for r in (pdf, audio)]
        ResourceView.objects.create(student=self.student, resource_id=removed[0], course=course)
        self.assertEqual(len(self.stored_files()), 3); self.events.clear()
        self.assertTrue(self.client.get(f'/api/courses/{course.pk}/').data['can_delete'])
        self.assertEqual(self.client.delete(f'/api/courses/{course.pk}/').status_code, 204)
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())
        for model in (Chapter, CourseGroup, Resource, ResourceSegment, ResourceView):
            self.assertFalse(model.objects.filter(course_id=course.pk).exists(), model.__name__)
        self.assertFalse(ProcessingJob.objects.filter(resource_id__in=removed).exists())
        kept = Resource.objects.get(pk=kept['id'])
        self.assertEqual(list(ProcessingJob.objects.values_list('resource_id', flat=True)), [kept.pk])
        self.assertEqual(self.stored_files(), [kept.file.name.split('/')[-1]])
        self.assertEqual(ResourceSegment.objects.filter(course_id=keep.pk).count(), 2); self.assertEqual(Chapter.objects.get(pk=keep_chapter.pk).course_id, keep.pk)
        self.assertEqual(self.events, []); self.assertEqual(self.client.get(f'/api/courses/{course.pk}/').status_code, 404)
