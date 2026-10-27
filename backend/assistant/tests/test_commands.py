import json
import os
import shutil
import tempfile
from io import StringIO
from unittest.mock import patch
from django.core.management import CommandError, call_command
from accounts.models import RateBucket, User
from classrooms.models import LearningGroup
from assistant.models import Conversation, KnowledgeChunk, Message, ScopeIndex, TeacherNote
from .base import AssistantTestCase, recorded_sleeps, without_courses

DEMO_TITLES = ['Le dioxyde de carbone et l’effet de serre', 'Les fonctions affines', 'Probabilités : bases']
ROW_KEYS = {'question', 'expected_source', 'expected_out_of_scope', 'retrieved_sources', 'top_score', 'retrieval_ms', 'hit_at_1', 'hit_at_5', 'status',
    'error_code', 'latency_ms', 'prompt_tokens', 'output_tokens', 'citations', 'unsourced', 'model_called', 'predicted_out_of_scope'}


class SeedCommandTests(AssistantTestCase):
    def seed(self, *args, **options):
        out = StringIO(); call_command('seed_assistant_demo', *args, stdout=out, **options); return out.getvalue()

    def test_demo_notes_are_created_once_then_kept_in_step(self):
        output = self.seed(group=' seca ')
        self.assertIn('Groupe SECA : 3 note(s) créée(s), 0 mise(s) à jour, 0 inchangée(s).', output)
        self.assertIn(f'evaluate_assistant --source-type group --scope {self.group.pk} --json', output)
        demo = TeacherNote.objects.filter(group=self.group).exclude(pk=self.note.pk)
        self.assertEqual(sorted(demo.values_list('title', flat=True)), DEMO_TITLES)
        self.assertEqual({(n.teacher_id, n.version) for n in demo}, {(self.teacher.pk, 1)})
        self.assertIn('0 note(s) créée(s), 0 mise(s) à jour, 3 inchangée(s).', self.seed(group='SECA'))
        TeacherNote.objects.filter(group=self.group, title='Les fonctions affines').update(body='Ancien texte.')
        self.group.teacher = self.other_teacher; self.group.save()
        self.assertIn('0 note(s) créée(s), 3 mise(s) à jour, 0 inchangée(s).', self.seed(group='SECA'))
        self.assertEqual({(n.teacher_id, n.version) for n in demo.all()}, {(self.other_teacher.pk, 2)})
        self.assertNotEqual(TeacherNote.objects.get(group=self.group, title='Les fonctions affines').body, 'Ancien texte.')

    def test_refusals(self):
        LearningGroup.objects.create(name='Ancien', code='OLD', teacher=self.teacher, level='Seconde', academic_year='2025', archived=True)
        for options, message in (({'group': 'NOPE'}, 'Aucun groupe avec le code NOPE.'), ({'group': 'old'}, 'Le groupe OLD est archivé.'),
                ({'group': 'SECA', 'dataset': '/nulle/part.json'}, 'Jeu de données illisible')):
            with self.subTest(options=options), self.assertRaisesMessage(CommandError, message): self.seed(**options)
        self.assertEqual(TeacherNote.objects.count(), 2)


class EvaluationCommandTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.demo = LearningGroup.objects.create(name='Démonstration', code='DEMO', teacher=self.teacher, level='Seconde', academic_year='2026')
        call_command('seed_assistant_demo', group='DEMO', stdout=StringIO())
        self.folder = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.folder, True)

    def evaluate(self, *args, **options):
        out = StringIO(); call_command('evaluate_assistant', *args, stdout=out, **options); return out.getvalue()

    def report(self, **options):
        return json.loads(self.evaluate(scope=options.pop('scope', 'DEMO'), json=True, **options))

    def dataset(self, questions):
        path = os.path.join(self.folder, 'questions.json')
        with open(path, 'w', encoding='utf-8') as handle: json.dump({'questions': questions}, handle, ensure_ascii=False)
        return path

    def test_json_report_on_the_demo_dataset(self):
        report = self.report()
        summary = report['summary']
        index = ScopeIndex.objects.get(source_type='group', scope_id=str(self.demo.pk))
        self.assertEqual({k: summary[k] for k in ('scope', 'mode', 'min_score', 'retrieval_only', 'chunks', 'questions', 'answerable', 'out_of_scope_expected',
                'hit_rate_at_1', 'hit_rate_at_5', 'refusal_accuracy', 'false_refusals', 'refused_before_model', 'statuses', 'failures', 'model_calls', 'unsourced_answers')}, {
            'scope': {'source_type': 'group', 'scope_id': str(self.demo.pk), 'title': 'Démonstration'}, 'mode': 'EXPLICATION', 'min_score': 1.0,
            'retrieval_only': False, 'chunks': index.chunks_count, 'questions': 20, 'answerable': 15, 'out_of_scope_expected': 5, 'hit_rate_at_1': 1.0,
            'hit_rate_at_5': 1.0, 'refusal_accuracy': 1.0, 'false_refusals': 0, 'refused_before_model': 5, 'statuses': {'COMPLETE': 15, 'OUT_OF_SCOPE': 5},
            'failures': 0, 'model_calls': 15, 'unsourced_answers': 0})
        self.assertEqual(summary['llm'], {'provider': 'fake', 'configured': True, 'model': 'fake-gemini', 'fallback_model': ''})
        self.assertEqual(index.chunks_count, KnowledgeChunk.objects.filter(scope_id=str(self.demo.pk)).count())
        self.assertGreater(summary['tokens']['prompt'], 0); self.assertGreater(summary['tokens']['output'], 0)
        self.assertIsNotNone(summary['latency_ms']['p50']); self.assertIsNotNone(summary['retrieval_ms']['p95'])
        rows = report['results']
        self.assertEqual({frozenset(row) for row in rows}, {frozenset(ROW_KEYS)})
        for row in rows:
            with self.subTest(question=row['question']):
                if row['expected_out_of_scope']:
                    self.assertEqual((row['retrieved_sources'], row['predicted_out_of_scope'], row['model_called'], row['status'], row['top_score']), ([], True, False, 'OUT_OF_SCOPE', None))
                else:
                    self.assertEqual((row['retrieved_sources'][0], row['hit_at_1'], row['status'], row['model_called']), (row['expected_source'], True, 'COMPLETE', True))
                    self.assertGreaterEqual(row['citations'], 1)
        # The evaluation reads the content; it writes no conversation and uses no quota.
        self.assertEqual((Conversation.objects.count(), Message.objects.count(), RateBucket.objects.count()), (0, 0, 0))

    def test_retrieval_only_and_threshold_calibration(self):
        summary = self.report(retrieval_only=True)['summary']
        self.assertEqual((summary['model_calls'], summary['statuses'], summary['hit_rate_at_5'], summary['tokens']), (0, {'NOT_CALLED': 15, 'OUT_OF_SCOPE': 5}, 1.0, {'prompt': 0, 'output': 0}))
        strict = self.report(retrieval_only=True, min_score=1000.0)['summary']
        self.assertEqual((strict['min_score'], strict['refused_before_model'], strict['false_refusals'], strict['hit_rate_at_5'], strict['refusal_accuracy']), (1000.0, 20, 15, 0.0, 1.0))
        self.assertEqual(self.report(scope=str(self.demo.pk), mode='INDICE', retrieval_only=True)['summary']['mode'], 'INDICE')

    def test_model_failures_are_reported(self):
        path = self.dataset([{'question': 'Comment calculer le coefficient directeur ? #erreur', 'expected_source': 'Les fonctions affines'},
            {'question': 'Qu’est-ce qu’un événement contraire ? #bloque', 'expected_source': 'Probabilités : bases'},
            {'question': 'Que dit le cours sur le dioxyde de carbone ? #horscours', 'out_of_scope': True}])
        rows = self.report(dataset=path)['results']
        self.assertEqual([(r['status'], r['error_code'], r['model_called']) for r in rows], [('FAILED', 'unavailable', True), ('BLOCKED', 'blocked', True), ('OUT_OF_SCOPE', '', True)])
        summary = self.report(dataset=path)['summary']
        self.assertEqual((summary['failures'], summary['refusal_accuracy'], summary['refused_before_model']), (2, 1.0, 0))

    def test_pause_only_between_model_calls(self):
        path = self.dataset([{'question': 'Comment calculer le coefficient directeur ?', 'expected_source': 'Les fonctions affines'},
            {'question': 'Quelle est la capitale de l’Australie ?', 'out_of_scope': True},
            {'question': 'Qu’est-ce qu’un événement contraire ?', 'expected_source': 'Probabilités : bases'}])
        with recorded_sleeps() as pauses:
            self.report(dataset=path, pause=0.5)
        self.assertEqual(pauses, [0.5])

    def test_text_report(self):
        text = self.evaluate(scope='DEMO')
        self.assertTrue(text.startswith('Évaluation de l’assistant — Démonstration (fake fake-gemini, seuil 1.0)'))
        for line in ('Bonne source en premier (hit@1) : 100 %', 'Sources retrouvées (hit@5) : 100 %', 'Refus hors cours corrects : 100 %', 'Refus à tort : 0',
                'Appels au modèle : 15 ; échecs : 0'):
            self.assertIn(line, text)
        self.assertEqual((text.count('\n- [COMPLETE] '), text.count('\n- [OUT_OF_SCOPE] ')), (15, 5))
        self.assertEqual(self.evaluate(scope='DEMO', retrieval_only=True).count('\n- [NON APPELÉ] '), 15)

    def test_refusals(self):
        absent = without_courses(); absent.start(); self.addCleanup(absent.stop)
        broken = os.path.join(self.folder, 'broken.json')
        with open(broken, 'w', encoding='utf-8') as handle: handle.write('{"notes": []}')
        cases = [({'scope': 'DEMO', 'source_type': 'course'}, 'Type de contenu indisponible : course.'), ({'scope': 'NOPE'}, 'Aucun groupe avec le code NOPE.'),
            ({'scope': '0' * 24}, 'Contenu introuvable.'), ({'scope': 'DEMO', 'dataset': broken}, 'Jeu de données illisible'),
            ({'scope': 'DEMO', 'dataset': '/nulle/part.json'}, 'Jeu de données illisible')]
        for options, message in cases:
            with self.subTest(options=options), self.assertRaisesMessage(CommandError, message): self.evaluate(**options)
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaisesMessage(CommandError, 'Un compte administrateur actif est nécessaire pour lire le contenu évalué.'): self.evaluate(scope='DEMO')
