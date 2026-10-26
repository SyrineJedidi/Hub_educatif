from datetime import timedelta
from bson import ObjectId
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from classrooms.models import Enrollment, LearningGroup
from quizzes.models import Attempt, Quiz
from assistant import retrieval
from assistant.content import CoursesProvider, NotesProvider, note_blocks, provider_for, providers
from assistant.indexing import INDEX_FORMAT, ensure_index
from assistant.models import KnowledgeChunk, ScopeIndex, TeacherNote, ValidatedAnswer
from .base import AssistantTestCase, CoursesStub, segment


class NotesProviderTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.provider = NotesProvider()

    def keys(self, user):
        return [s.key for s in self.provider.scopes_for(user)]

    def visible(self, user, group=None):
        try: self.provider.get_scope(user, str((group or self.group).pk)); return True
        except NotFound as exc:
            self.assertEqual(str(exc.detail), 'Ressource introuvable.'); return False

    def test_scope_is_the_group_with_its_teacher(self):
        scope = self.provider.get_scope(self.student, str(self.group.pk))
        self.assertEqual((scope.source_type, scope.scope_id, scope.key, scope.title, scope.teacher_id, scope.group_ids),
            ('group', str(self.group.pk), self.scope_key, 'Seconde A', str(self.teacher.pk), [str(self.group.pk)]))
        self.assertEqual(self.keys(self.student), [self.scope_key])
        self.assertEqual(self.keys(self.teacher), [self.scope_key])
        # The administrator manages every scope but never chats.
        self.assertEqual(self.keys(self.admin), [])
        self.assertFalse(self.visible(self.admin))

    def test_student_needs_a_current_enrollment(self):
        now = timezone.now()
        cases = [('ended', now - timedelta(days=9), now - timedelta(seconds=1), False), ('ends now', now - timedelta(days=9), now, False),
            ('future', now + timedelta(minutes=5), None, False), ('open', now - timedelta(seconds=1), None, True),
            ('until tomorrow', now - timedelta(days=9), now + timedelta(days=1), True)]
        for label, starts_at, ends_at, expected in cases:
            with self.subTest(label):
                Enrollment.objects.filter(student=self.student).update(starts_at=starts_at, ends_at=ends_at)
                self.assertEqual(self.visible(self.student), expected)
                self.assertEqual(self.keys(self.student), [self.scope_key] if expected else [])

    def test_a_past_enrollment_does_not_open_the_group_again(self):
        now = timezone.now()
        self.enrollment.ends_at = now - timedelta(days=2); self.enrollment.save()
        Enrollment.objects.create(student=self.student, group=self.group, starts_at=now + timedelta(days=3))
        self.assertFalse(self.visible(self.student))
        Enrollment.objects.create(student=self.student, group=self.group, starts_at=now - timedelta(hours=1))
        self.assertTrue(self.visible(self.student))

    def test_archived_group_is_hidden_from_everyone_who_chats(self):
        LearningGroup.objects.filter(pk=self.group.pk).update(archived=True)
        self.assertFalse(self.visible(self.student)); self.assertFalse(self.visible(self.teacher))
        self.assertEqual(self.keys(self.student), []); self.assertEqual(self.keys(self.teacher), [])
        self.assertNotIn(self.scope_key, [s.key for s in self.provider.managed_scopes(self.teacher)])

    def test_students_are_offered_a_group_only_once_it_has_a_note(self):
        empty = LearningGroup.objects.create(name='Atelier', code='ATELIER', teacher=self.teacher, level='Seconde', academic_year='2026')
        Enrollment.objects.create(student=self.student, group=empty, starts_at=timezone.now() - timedelta(days=1))
        self.assertFalse(self.visible(self.student, empty))
        self.assertEqual(self.keys(self.student), [self.scope_key])
        # Teachers may try the assistant on every group they teach.
        self.assertTrue(self.visible(self.teacher, empty))
        self.assertEqual(self.keys(self.teacher), [f'group:{empty.pk}', self.scope_key])
        TeacherNote.objects.create(group=empty, teacher=self.teacher, title='Consignes', body='Apportez une calculatrice.')
        self.assertTrue(self.visible(self.student, empty))

    def test_other_people_never_see_the_group(self):
        for user in (self.other_student, self.other_teacher):
            with self.subTest(user=user.email): self.assertFalse(self.visible(user)); self.assertNotIn(self.scope_key, self.keys(user))
        for value in ('not-an-id', str(ObjectId()), '', None):
            with self.subTest(value=value), self.assertRaises(NotFound): self.provider.get_scope(self.student, value)

    def test_managed_scopes(self):
        archived = LearningGroup.objects.create(name='Ancien', code='OLD', teacher=self.teacher, level='Seconde', academic_year='2025', archived=True)
        self.assertEqual([s.key for s in self.provider.managed_scopes(self.teacher)], [self.scope_key])
        self.assertEqual([s.key for s in self.provider.managed_scopes(self.admin)], [self.scope_key, self.other_scope_key])
        self.assertEqual(self.provider.managed_scopes(self.student), [])
        self.assertEqual(self.provider.get_managed_scope(self.admin, str(self.other_group.pk)).key, self.other_scope_key)
        self.assertEqual(self.provider.get_managed_scope(self.teacher, str(archived.pk)).title, 'Ancien')
        for user, group in ((self.other_teacher, self.group), (self.student, self.group), (self.teacher, self.other_group)):
            with self.subTest(user=user.email), self.assertRaises(NotFound): self.provider.get_managed_scope(user, str(group.pk))

    def test_segments_are_note_paragraphs_then_validated_answers(self):
        TeacherNote.objects.create(group=self.group, teacher=self.teacher, title='Sans titre de partie',
            body='Premier paragraphe.\r\n\r\n   \n\nDeuxième paragraphe\nsur deux lignes.')
        ValidatedAnswer.objects.create(source_type='group', scope_id=str(self.group.pk), question='Comment noter une norme ?', answer='Avec deux barres.', teacher=self.teacher)
        ValidatedAnswer.objects.create(source_type='group', scope_id=str(self.other_group.pk), question='Autre groupe', answer='Jamais ici.', teacher=self.other_teacher)
        segments = list(self.provider.segments(str(self.group.pk)))
        self.assertEqual([(s.source_kind, s.source_title, s.chapter_title, s.text) for s in segments], [
            ('NOTE', 'Les vecteurs', 'Définition', 'Un vecteur est défini par une direction, un sens et une norme. La norme d’un vecteur est sa longueur.'),
            ('NOTE', 'Les vecteurs', 'Addition', 'La somme de deux vecteurs se construit avec la relation de Chasles : on place les vecteurs bout à bout.'),
            ('NOTE', 'Les vecteurs', 'Colinéarité', 'Deux vecteurs sont colinéaires lorsqu’ils ont la même direction. Leur déterminant est alors égal à zéro.'),
            ('NOTE', 'Sans titre de partie', '', 'Premier paragraphe.'),
            ('NOTE', 'Sans titre de partie', '', 'Deuxième paragraphe\nsur deux lignes.'),
            ('VALIDATED', 'Réponse validée par l’enseignant', 'Comment noter une norme ?', 'Comment noter une norme ?\n\nAvec deux barres.')])
        self.assertEqual({(s.source_id, s.page, s.start_seconds, s.url) for s in segments[:3]}, {(str(self.note.pk), None, None, '')})

    def test_markdown_headings_name_the_following_paragraphs(self):
        note = TeacherNote(title='Plan', body='# Partie 1\n## Section A\nTexte A.\n\nSuite de A.\n\n### Section B\n\nTexte B.\n#pas-un-titre\n\n## Vide')
        self.assertEqual(list(note_blocks(note)), [('Section A', 'Texte A.'), ('Section A', 'Suite de A.'), ('Section B', 'Texte B.\n#pas-un-titre')])

    def test_version_changes_with_every_content_change(self):
        scope_id = str(self.group.pk)
        versions = [self.provider.version(scope_id)]
        def changed():
            versions.append(self.provider.version(scope_id)); return versions[-1] != versions[-2]
        self.assertEqual(self.provider.version(scope_id), versions[0])
        TeacherNote.objects.filter(pk=self.other_note.pk).update(version=5)
        self.assertFalse(changed())
        TeacherNote.objects.filter(pk=self.note.pk).update(version=2)
        self.assertTrue(changed())
        added = TeacherNote.objects.create(group=self.group, teacher=self.teacher, title='Repères', body='Un repère est formé d’une origine et de deux axes.')
        self.assertTrue(changed())
        ValidatedAnswer.objects.create(source_type='group', scope_id=scope_id, question='Q', answer='R', teacher=self.teacher)
        self.assertTrue(changed())
        added.delete()
        self.assertTrue(changed())
        # Only the other group's edit kept the version; no later state repeats an earlier one.
        self.assertEqual(len(set(versions)), len(versions) - 1)


class CoursesProviderTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.courses = CoursesStub()
        self.addCleanup(self.courses.installed().close)
        self.pdf, self.audio = str(ObjectId()), str(ObjectId())
        self.course_id = self.courses.add('Physique : les forces', self.teacher, [self.group], segments=[
            segment('Une force se représente par un vecteur : point d’application, direction, sens et intensité.', self.pdf, 'Cours PDF', 'Les forces', page=3),
            segment('Le poids est la force exercée par la Terre sur un objet.', self.pdf, 'Cours PDF', 'Les forces', page=4),
            segment('Dans cette vidéo, nous mesurons une force avec un dynamomètre.', self.audio, 'Vidéo', 'Mesures', start_seconds=83.4)])
        self.draft = self.courses.add('Brouillon', self.teacher, [self.group], status='DRAFT')
        self.archived = self.courses.add('Ancien cours', self.teacher, [self.group], status='ARCHIVED')
        self.foreign = self.courses.add('Chimie', self.other_teacher, [self.other_group])
        self.provider = providers()['course']

    def test_registered_only_while_the_courses_module_is_installed(self):
        self.assertIsInstance(self.provider, CoursesProvider)
        self.assertEqual(sorted(providers()), ['course', 'group'])
        self.assertIsInstance(provider_for('course'), CoursesProvider)

    def test_student_sees_published_courses_of_current_groups(self):
        self.assertEqual([(s.key, s.title, s.teacher_id, s.group_ids) for s in self.provider.scopes_for(self.student)],
            [(f'course:{self.course_id}', 'Physique : les forces', str(self.teacher.pk), [str(self.group.pk)])])
        self.assertEqual(self.provider.get_scope(self.student, self.course_id).title, 'Physique : les forces')
        for hidden in (self.draft, self.archived, self.foreign, str(ObjectId()), 'not-an-id'):
            with self.subTest(course=hidden), self.assertRaises(NotFound) as caught: self.provider.get_scope(self.student, hidden)
            self.assertEqual(str(caught.exception.detail), 'Ressource introuvable.')
        Enrollment.objects.filter(student=self.student).update(ends_at=timezone.now())
        self.assertEqual(self.provider.scopes_for(self.student), [])
        with self.assertRaises(NotFound): self.provider.get_scope(self.student, self.course_id)

    def test_teacher_chats_on_own_courses_including_drafts(self):
        self.assertEqual([s.title for s in self.provider.scopes_for(self.teacher)], ['Brouillon', 'Physique : les forces'])
        self.assertEqual(self.provider.get_scope(self.teacher, self.draft).title, 'Brouillon')
        for hidden in (self.archived, self.foreign):
            with self.subTest(course=hidden), self.assertRaises(NotFound): self.provider.get_scope(self.teacher, hidden)
        self.assertEqual(self.provider.scopes_for(self.admin), [])
        with self.assertRaises(NotFound): self.provider.get_scope(self.admin, self.course_id)

    def test_managed_scopes(self):
        self.assertEqual([s.title for s in self.provider.managed_scopes(self.teacher)], ['Brouillon', 'Physique : les forces'])
        self.assertEqual([s.title for s in self.provider.managed_scopes(self.admin)], ['Brouillon', 'Chimie', 'Physique : les forces'])
        self.assertEqual(self.provider.managed_scopes(self.student), [])
        self.assertEqual(self.provider.get_managed_scope(self.admin, self.foreign).title, 'Chimie')
        for user, course in ((self.other_teacher, self.course_id), (self.student, self.course_id)):
            with self.subTest(user=user.email), self.assertRaises(NotFound): self.provider.get_managed_scope(user, course)

    def test_segments_link_to_the_resource_page_or_time(self):
        ValidatedAnswer.objects.create(source_type='course', scope_id=self.course_id, question='Qu’est-ce que le poids ?', answer='La force de la Terre.', teacher=self.teacher)
        ValidatedAnswer.objects.create(source_type='group', scope_id=self.course_id, question='Mauvais type', answer='Jamais ici.', teacher=self.teacher)
        self.assertEqual([(s.source_kind, s.source_id, s.source_title, s.chapter_title, s.page, s.start_seconds, s.url) for s in self.provider.segments(self.course_id)], [
            ('RESOURCE', self.pdf, 'Cours PDF', 'Les forces', 3, None, f'/espace/cours/{self.course_id}/ressources/{self.pdf}?page=3'),
            ('RESOURCE', self.pdf, 'Cours PDF', 'Les forces', 4, None, f'/espace/cours/{self.course_id}/ressources/{self.pdf}?page=4'),
            ('RESOURCE', self.audio, 'Vidéo', 'Mesures', None, 83.4, f'/espace/cours/{self.course_id}/ressources/{self.audio}?t=83'),
            ('VALIDATED', next(str(v.pk) for v in ValidatedAnswer.objects.filter(source_type='course')), 'Réponse validée par l’enseignant',
                'Qu’est-ce que le poids ?', None, None, '')])

    def test_version_follows_the_course_and_its_validated_answers(self):
        first = self.provider.version(self.course_id)
        self.assertTrue(first.startswith('1:'))
        self.courses.versions[self.course_id] = 2
        second = self.provider.version(self.course_id)
        self.assertTrue(second.startswith('2:')); self.assertEqual(first.split(':')[1], second.split(':')[1])
        ValidatedAnswer.objects.create(source_type='course', scope_id=self.course_id, question='Q', answer='R', teacher=self.teacher)
        self.assertNotEqual(self.provider.version(self.course_id), second)

    def test_content_signal_marks_the_index_stale_and_forgets_the_corpus(self):
        index = ensure_index(self.provider, self.course_id)
        self.assertEqual(KnowledgeChunk.objects.filter(source_type='course', scope_id=self.course_id).count(), 3)
        hits = retrieval.retrieve('course', self.course_id, index.content_version, 'Comment mesurer une force avec un dynamomètre ?')
        self.assertEqual(hits[0].chunk.url, f'/espace/cours/{self.course_id}/ressources/{self.audio}?t=83')
        self.assertIn(('course', self.course_id, index.content_version), retrieval._cache)
        self.courses.changed(self.course_id)
        self.assertEqual(ScopeIndex.objects.get(pk=index.pk).content_version, '')
        self.assertNotIn(('course', self.course_id, index.content_version), retrieval._cache)
        rebuilt = ensure_index(self.provider, self.course_id)
        self.assertTrue(rebuilt.content_version.startswith(f'{INDEX_FORMAT}:2:'))
        # Another course's change and a signal without course id leave this index alone.
        self.courses.changed(self.foreign); self.courses.signal.send(sender=None, course_id=None, resource_id=None, reason='x')
        self.assertEqual(ScopeIndex.objects.get(pk=index.pk).content_version, rebuilt.content_version)

    def test_students_ask_about_a_course_through_the_api(self):
        response = self.student_client.get('/api/assistant/scopes/')
        self.assertEqual([s['key'] for s in response.data['results']], [self.scope_key, f'course:{self.course_id}'])
        conversation = self.start(scope_key=f'course:{self.course_id}')
        answer = self.answered(conversation, 'Comment mesurer une force avec un dynamomètre ?')['answer']
        self.assertEqual(answer['status'], 'COMPLETE')
        self.assertEqual({k: answer['citations'][0][k] for k in ('number', 'source_kind', 'source_id', 'source_title', 'chapter_title', 'page', 'start_seconds', 'url')},
            {'number': 1, 'source_kind': 'RESOURCE', 'source_id': self.audio, 'source_title': 'Vidéo', 'chapter_title': 'Mesures', 'page': None,
             'start_seconds': 83.4, 'url': f'/espace/cours/{self.course_id}/ressources/{self.audio}?t=83'})
        # The course teacher reviews the shared feedback and follows the course.
        self.student_client.put(f'/api/assistant/messages/{answer["id"]}/feedback/', {'rating': 'DOWN', 'reasons': ['INCOMPLETE'], 'shared_with_teacher': True}, format='json')
        reviews = self.teacher_client.get(f'/api/assistant/reviews/?scope=course:{self.course_id}').data['results']
        self.assertEqual([(r['scope_key'], r['scope_title']) for r in reviews], [(f'course:{self.course_id}', 'Physique : les forces')])
        self.assertEqual(self.as_user(self.other_teacher).get('/api/assistant/reviews/').data['count'], 0)
        self.assertEqual(self.teacher_client.get(f'/api/assistant/insights/course/{self.course_id}/').data['questions'], 1)
        self.assertIn(f'course:{self.course_id}', [s['key'] for s in self.teacher_client.get('/api/assistant/settings/').data['results']])
        # A quiz running in a group linked to the course suspends it too.
        quiz = Quiz.objects.create(title='Contrôle', description='Forces.', teacher=self.teacher, learning_group=self.group, duration_minutes=10, status='PUBLISHED')
        now = timezone.now()
        attempt = Attempt.objects.create(student=self.student, quiz=quiz, learning_group=self.group, number=1, quiz_title='Contrôle', total_points=1,
            started_at=now, deadline=now + timedelta(minutes=10))
        self.refused(self.ask(conversation, 'Qu’est-ce que le poids ?'), 409, 'quiz_in_progress')
        Attempt.objects.filter(pk=attempt.pk).update(status='SUBMITTED')
        # Unpublishing the course leaves the conversation readable but closed.
        self.courses.courses[self.course_id].status = 'DRAFT'
        self.refused(self.ask(conversation, 'Qu’est-ce que le poids ?'), 403, 'scope_unavailable')
        self.assertEqual(self.student_client.get(f'/api/assistant/conversations/{conversation}/messages/').status_code, 200)
        self.assertFalse(self.student_client.get(f'/api/assistant/conversations/{conversation}/').data['can_send'])


class RegistryTests(AssistantTestCase):
    def test_without_the_courses_module_only_notes_are_available(self):
        self.assertEqual(sorted(providers()), ['group'])
        for value in ('course', 'video', ''):
            with self.subTest(value=value), self.assertRaises(ValidationError) as caught: provider_for(value)
            self.assertEqual(caught.exception.detail, {'scope_key': ['Sélectionnez un type de contenu disponible.']})
        with self.assertRaises(ValidationError) as caught: provider_for('course', 'source_type')
        self.assertIn('source_type', caught.exception.detail)
        response = self.student_client.post('/api/assistant/conversations/', {'scope_key': f'course:{ObjectId()}'}, format='json')
        self.assertEqual(response.status_code, 400); self.assertIn('scope_key', response.data['error']['fields'])
