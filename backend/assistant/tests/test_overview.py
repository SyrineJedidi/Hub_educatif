from unittest.mock import patch
from django.test import SimpleTestCase
from assistant.content import NotesProvider
from assistant.indexing import ensure_index
from assistant.models import Message, TeacherNote, ValidatedAnswer
from assistant.retrieval import is_overview_question, overview_hits
from .base import OUT_OF_SCOPE, AssistantTestCase


class OverviewQuestionTests(SimpleTestCase):
    def test_questions_about_the_course_itself(self):
        for question in ('C’est quoi ce cours ?', 'Ok, qu’est-ce que ce cours ? C’est quoi ce cours en fait ?', 'De quoi parle ce cours ?',
                'Résume-moi le cours', 'Quel est le programme du cours ?', 'Quels sont les chapitres ?', 'Quel est le plan de ce cours ?',
                'What is this course about?'):
            with self.subTest(question=question):
                self.assertTrue(is_overview_question(question))

    def test_questions_about_a_notion_or_outside_the_course(self):
        for question in ('Qu’est-ce que la norme d’un vecteur ?', 'Explique-moi le chapitre sur les vecteurs', OUT_OF_SCOPE,
                'Qui a gagné la Coupe du monde 2022 ?', 'ok', 'Bonjour', ''):
            with self.subTest(question=question):
                self.assertFalse(is_overview_question(question))


class OverviewAnswerTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.lines = TeacherNote.objects.create(group=self.group, teacher=self.teacher, title='Les droites',
            body='## Équation\nUne droite non verticale a une équation de la forme y = mx + p.\n\n## Parallélisme\nDeux droites parallèles ont le même coefficient directeur.')

    def test_opening_passage_of_each_source_in_course_order(self):
        ValidatedAnswer.objects.create(source_type='group', scope_id=str(self.group.pk), question='Norme ?', answer='La longueur du vecteur.', teacher=self.teacher)
        ensure_index(NotesProvider(), self.group.pk)
        hits = overview_hits('group', str(self.group.pk))
        self.assertEqual(sorted(h.chunk.source_title for h in hits), ['Les droites', 'Les vecteurs'])
        self.assertEqual([h.chunk.order for h in hits], sorted(h.chunk.order for h in hits))
        self.assertTrue(all(h.chunk.source_kind == 'NOTE' and h.score == 0.0 for h in hits))
        self.assertEqual(len(overview_hits('group', str(self.group.pk), limit=1)), 1)

    def test_a_question_about_the_course_is_answered_from_its_sources(self):
        data = self.answered(self.start(), 'C’est quoi ce cours ?')
        answer = data['answer']
        self.assertEqual((answer['status'], answer['unsourced'], data['quota']['used']), ('COMPLETE', False, 1))
        self.assertTrue(answer['content'].startswith('D’après le cours : '))
        self.assertIn(answer['citations'][0]['source_title'], ('Les droites', 'Les vecteurs'))
        stored = Message.objects.get(pk=answer['id'])
        self.assertEqual((stored.chunks_used, stored.top_score, stored.provider), (2, 0.0, 'fake'))

    def test_an_unrelated_question_is_still_refused_without_the_model(self):
        with patch('assistant.services.generate_answer', side_effect=AssertionError('the model must not be called')):
            data = self.answered(self.start(), OUT_OF_SCOPE)
        self.assertEqual((data['answer']['status'], data['quota']['used']), ('OUT_OF_SCOPE', 0))

    def test_an_overview_question_without_any_passage_is_still_refused(self):
        with patch('assistant.services.overview_hits', return_value=[]), \
                patch('assistant.services.generate_answer', side_effect=AssertionError('the model must not be called')):
            data = self.answered(self.start(), 'De quoi parle ce cours ?')
        self.assertEqual((data['answer']['status'], data['quota']['used']), ('OUT_OF_SCOPE', 0))
