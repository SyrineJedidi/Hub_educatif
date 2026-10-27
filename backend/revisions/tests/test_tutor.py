from unittest import mock
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from ..ai.clients import AIServiceError
from ..ai.tutor import clean_questions
from ..models import AIJob, RevisionSheet, SheetProgress
from . import test_revisions as sheets

QUESTIONS = [
    {'question': 'Où se trouve la chlorophylle ?', 'choices': ['Dans le noyau', 'Dans les chloroplastes', 'Dans les racines', 'Dans la sève'], 'answer': 1,
     'explanation': 'La chlorophylle est dans les chloroplastes.'},
    {'question': 'Que stocke le glucose ?', 'choices': ['De l’eau', 'De la lumière', 'De l’énergie', 'Du dioxygène'], 'answer': 2,
     'explanation': 'Le glucose stocke l’énergie.'},
    {'question': 'Que capte la chlorophylle ?', 'choices': ['La lumière', 'Le sol', 'Le vent', 'La chaleur'], 'answer': 0,
     'explanation': 'Elle capte la lumière.'},
    # Rejected: three choices, duplicated choices, answer out of range, repeated question.
    {'question': 'Mal formée', 'choices': ['a', 'b', 'c'], 'answer': 0, 'explanation': ''},
    {'question': 'Doublons', 'choices': ['a', 'a', 'b', 'c'], 'answer': 0, 'explanation': ''},
    {'question': 'Hors bornes', 'choices': ['a', 'b', 'c', 'd'], 'answer': 7, 'explanation': ''},
    {'question': 'Où se trouve la chlorophylle ?', 'choices': ['w', 'x', 'y', 'z'], 'answer': 0, 'explanation': ''},
]


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MEDIA_ROOT=sheets.MEDIA,
                   GEMINI_API_KEY='test-key', AI_JOB_BACKEND='sync')
class TutorTests(TransactionTestCase):
    """AI help for the student: training quiz written from a sheet, and today's revision plan."""
    # Same accounts, group and helpers as the sheet tests, without running those tests again.
    setUp, as_user, data, create, post = (sheets.RevisionSheetTests.setUp, sheets.RevisionSheetTests.as_user, sheets.RevisionSheetTests.data,
                                          sheets.RevisionSheetTests.create, sheets.RevisionSheetTests.post)
    def published(self):
        sheet = self.create()
        RevisionSheet.objects.filter(pk=sheet['id']).update(status='PUBLISHED', published_at=timezone.now(),
            key_points=['La chlorophylle capte la lumière.', 'Le glucose stocke l’énergie.'],
            glossary=[{'term': 'Chloroplaste', 'definition': 'Organite où se trouve la chlorophylle.'}])
        return RevisionSheet.objects.get(pk=sheet['id'])

    @mock.patch('revisions.ai.tutor.generate_json', return_value=({'questions': QUESTIONS}, 'gemini-test', False, 900))
    def test_student_gets_a_valid_quiz_grounded_in_the_sheet(self, generate):
        sheet, student = self.published(), self.as_user(self.student)
        started = self.post(f'sheets/{sheet.pk}/self-quiz/', {'count': 3}, student)
        self.assertEqual((started.status_code, started.data['kind'], started.data['status']), (202, 'QUIZ', 'SUCCEEDED'))
        prompt = generate.call_args[0][1]
        self.assertIn('Rédige exactement 3 questions', prompt)
        self.assertIn('Chloroplaste : Organite', prompt)
        job = student.get(f'/api/ai/jobs/{started.data["id"]}/').data
        questions = job['result']['questions']
        self.assertEqual(len(questions), 3)
        for q in questions:
            self.assertEqual(len(set(q['choices'])), 4)
            self.assertIn(q['choices'][q['answer']], ('Dans les chloroplastes', 'De l’énergie', 'La lumière'))
        self.assertEqual((job['metrics']['requested'], job['metrics']['valid']), (3, 3))
        self.assertGreater(job['metrics']['grounding'], 0.5)
        # Somebody else cannot read this quiz, even the teacher who owns the sheet.
        self.assertEqual(self.client.get(f'/api/ai/jobs/{started.data["id"]}/').status_code, 404)

    def test_answers_are_spread_over_the_four_positions(self):
        many = [{'question': f'Question {i} ?', 'choices': ['Juste', 'Faux 1', 'Faux 2', 'Faux 3'], 'answer': 0, 'explanation': 'x'} for i in range(40)]
        positions = {q['answer'] for q in clean_questions(many, seed='abc')}
        self.assertEqual(positions, {0, 1, 2, 3})
        self.assertEqual(len(clean_questions(QUESTIONS, seed='abc')), 3)

    def test_quiz_needs_a_readable_sheet_with_content(self):
        sheet = self.published()
        self.assertEqual(self.post(f'sheets/{sheet.pk}/self-quiz/', {}, self.as_user(self.outsider)).status_code, 404)
        empty = self.create(summary='', key_points=[])
        self.assertEqual(self.post(f'sheets/{empty["id"]}/self-quiz/', {}).status_code, 400)
        self.assertEqual(self.post(f'sheets/{sheet.pk}/self-quiz/', {'count': 50}, self.as_user(self.student)).status_code, 400)

    @mock.patch('revisions.ai.tutor.generate_json', side_effect=AIServiceError('Le service IA ne répond pas.'))
    def test_ai_failure_is_reported_on_the_job(self, generate):
        sheet = self.published()
        job = self.post(f'sheets/{sheet.pk}/self-quiz/', {}, self.as_user(self.student)).data
        self.assertEqual((job['status'], job['error']), ('FAILED', 'Le service IA ne répond pas.'))

    def plan_fixture(self):
        cache.clear()
        unread, revised = self.published(), self.published()
        RevisionSheet.objects.filter(pk=revised.pk).update(title='Le cycle de Calvin')
        SheetProgress.objects.create(sheet=revised, student=self.student, views=2, known=[])
        return unread, revised

    @mock.patch('revisions.ai.tutor.generate_json')
    def test_plan_orders_only_items_found_by_the_platform(self, generate):
        unread, revised = self.plan_fixture()
        generate.return_value = ({'advice': 'Commence par les cartes du cycle de Calvin, puis lis la nouvelle fiche.',
                                  'order': [f'cards:{revised.pk}', 'sheet:inventée', f'sheet:{unread.pk}']}, 'gemini-test', False, 800)
        plan = self.as_user(self.student).get('/api/revisions/plan/').data
        self.assertEqual([i['id'] for i in plan['items']], [f'cards:{revised.pk}', f'sheet:{unread.pk}'])
        # The reason shown is the platform's fact, never a sentence of the model.
        self.assertEqual((plan['engine'], plan['items'][0]['reason']), ('gemini', '0 cartes maîtrisées sur 3'))
        self.assertEqual(plan['items'][1]['link'], f'/espace/fiches/{unread.pk}')
        # Cached for the day: the AI is not called again until a refresh is asked.
        self.as_user(self.student).get('/api/revisions/plan/')
        self.assertEqual(generate.call_count, 1)
        self.as_user(self.student).get('/api/revisions/plan/?refresh=1')
        self.assertEqual(generate.call_count, 2)

    @mock.patch('revisions.ai.tutor.generate_json', side_effect=AIServiceError('indisponible'))
    def test_plan_falls_back_to_rules_and_is_for_students(self, generate):
        unread, revised = self.plan_fixture()
        plan = self.as_user(self.student).get('/api/revisions/plan/').data
        self.assertEqual(plan['engine'], 'rules')
        self.assertTrue(plan['advice'].startswith('Commence par'))
        self.assertEqual({i['kind'] for i in plan['items']}, {'sheet', 'cards'})
        self.assertEqual(self.client.get('/api/revisions/plan/').status_code, 400)
        cache.clear()
        empty = self.as_user(self.outsider).get('/api/revisions/plan/').data
        self.assertEqual((empty['items'], empty['engine']), ([], 'rules'))


class GeminiFallbackTests(TransactionTestCase):
    """A saturated Gemini model hands over to the lighter one before the slow local model."""
    @override_settings(GEMINI_API_KEY='test-key', REVISIONS_GEMINI_MODEL='gemini-main', REVISIONS_GEMINI_FALLBACK_MODEL='gemini-lite',
                       REVISIONS_OLLAMA_MODEL='qwen-local')
    def test_lighter_gemini_model_answers_before_ollama(self):
        import json
        from ..ai import clients
        answer = json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps({'advice': 'ok', 'order': []})}]}}]}).encode()
        urls = []
        def post(url, headers, payload, timeout=None):
            urls.append(url)
            if 'gemini-main' in url: raise AIServiceError('Le service IA reçoit trop de demandes.')
            return answer, 'application/json'
        with mock.patch.object(clients, '_post', side_effect=post):
            data, model, fallback, _ = clients.generate_json('système', 'question', {'type': 'OBJECT'})
        self.assertEqual((data['advice'], model, fallback), ('ok', 'gemini-lite', False))
        self.assertEqual([u.split('/models/')[1].split(':')[0] for u in urls], ['gemini-main', 'gemini-lite'])
