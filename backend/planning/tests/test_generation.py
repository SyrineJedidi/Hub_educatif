import sys
import types
from datetime import timedelta
from unittest.mock import patch
from django.db import connection
from django.test import override_settings
from ai.gemini import GeminiError, GeminiResult
from planning import generation
from planning.generation import planner_inputs, quota_hits, RESPONSE_SCHEMA
from planning.models import StudyPlan, RevisionTask
from .base import PlanningTestCase, at

UNAVAILABLE = 'Service IA indisponible : planning calculé par règles.'
QUOTA = 'Quota IA atteint : planning calculé par règles.'
OUT_OF_WINDOWS = 'La proposition de l’IA ne respectait pas vos disponibilités : planning calculé par règles.'


@override_settings(GEMINI_PROVIDER='fake')
class GenerationTests(PlanningTestCase):
    def setUp(self):
        super().setUp()
        self.every_day('09:00', '11:00')
        self.python = self.goal(title='Python', priority='HIGH', estimated_hours=3, description='x' * 400)
        self.stats = self.goal(title='Statistiques', estimated_hours=2, learning_group=self.math)
        self.exam = self.deadline(title='Partiel Python', goal=self.python, due_at=at(self.tomorrow + timedelta(days=5), 10))

    def item(self, day=0, start='09:00', end='10:00', **kwargs):
        return {'title': 'Exercices', 'description': 'Série 1', 'date': (self.tomorrow + timedelta(days=day)).isoformat(), 'start': start, 'end': end, **kwargs}

    def with_proposal(self, tasks, advice='Commencez par Python.'):
        with patch('planning.generation.fake_response', return_value={'advice': advice, 'tasks': tasks}):
            return self.generate('ai')

    def test_fake_provider_keeps_the_ai_plan_and_metrics(self):
        r = self.generate('ai'); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['generator'], r.data['generator_label'], r.data['provider'], r.data['model_name'], r.data['fallback_reason']),
            ('AI', 'IA (Gemini)', 'fake', 'fake', ''))
        self.assertIsInstance(r.data['latency_ms'], int); self.assertIsNone(r.data['prompt_tokens'])
        self.assertTrue(r.data['advice'].startswith('Proposition de démonstration'))
        self.assertEqual(r.data['tasks_count'], 5)
        self.assertEqual(set(RevisionTask.objects.filter(plan_id=r.data['id']).values_list('source', flat=True)), {'AI'})
        self.assertEqual(r.data['tasks'][0]['goal'], {'id': str(self.python.pk), 'title': 'Python'})
        self.assertEqual(r.data['tasks'][0]['deadline'], {'id': str(self.exam.pk), 'title': 'Partiel Python'})
        self.assertEqual((quota_hits('planning-ai', str(self.student.pk)), quota_hits('planning-ai-global', 'global')), (1, 1))
        self.assertEqual(self.get('context/').data['ai']['remaining_today'], 9)

    def test_ai_proposals_are_validated_and_partly_dropped(self):
        foreign = self.goal(student=self.other, title='Autre')
        tasks = [self.item(goal_id=str(self.python.pk), deadline_id=str(self.exam.pk), title='  Exercices   de Python  '),
            self.item(start='09:30', end='10:30'), self.item(start='10:00', end='10:10'), self.item(day=1, start='08:00', end='10:00'),
            self.item(day=1, start='09:00', end='11:00', goal_id=str(foreign.pk), title=''), self.item(day=2, title='T' * 200, goal_id='nope'),
            self.item(day=3, start='9:00'), self.item(day=4, date='2026-02-30'), self.item(day=9), 'pas un objet',
            self.item(day=5, start='10:00', end='11:00', deadline_id=str(self.exam.pk).upper())]
        r = self.with_proposal(tasks); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['generator'], 'AI'); self.assertEqual(r.data['fallback_reason'], '7 propositions hors créneaux ont été ignorées.')
        self.assertEqual(r.data['advice'], 'Commencez par Python.')
        kept = r.data['tasks']
        self.assertEqual([t['title'] for t in kept], ['Exercices de Python', 'Révision', 'T' * 119 + '…', 'Exercices'])
        self.assertEqual(kept[0]['goal']['id'], str(self.python.pk)); self.assertEqual(kept[0]['deadline']['id'], str(self.exam.pk))
        self.assertIsNone(kept[1]['goal']); self.assertIsNone(kept[2]['goal']); self.assertEqual(kept[3]['deadline']['id'], str(self.exam.pk))
        self.assertEqual([t['minutes'] for t in kept], [60, 120, 60, 60])
        r = self.with_proposal([self.item(), self.item(start='09:30', end='10:30')], advice='')
        self.assertEqual(r.data['fallback_reason'], '1 proposition hors créneaux a été ignorée.')
        self.assertEqual(r.data['advice'], '1 séance de révision prévue, 1 h au total.')

    def test_no_valid_proposal_falls_back_to_rules(self):
        for tasks in ([self.item(start='12:00', end='13:00'), self.item(day=-1)], []):
            r = self.with_proposal(tasks); self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual((r.data['generator'], r.data['fallback_reason'], r.data['provider']), ('RULES', OUT_OF_WINDOWS, 'fake'))
            self.assertEqual({t['minutes'] for t in r.data['tasks']}, {60})
            self.assertEqual(set(RevisionTask.objects.filter(plan_id=r.data['id']).values_list('source', flat=True)), {'RULES'})
        with patch('planning.generation.fake_response', return_value=['not', 'a', 'dict']):
            r = self.generate('ai')
        self.assertEqual((r.data['generator'], r.data['fallback_reason']), ('RULES', 'La réponse de l’IA était inexploitable : planning calculé par règles.'))

    def test_provider_errors_fall_back_to_rules(self):
        reasons = {'unavailable': UNAVAILABLE, 'auth': UNAVAILABLE, 'refused': UNAVAILABLE, 'quota': QUOTA,
            'blocked': 'Le service IA a bloqué la demande : planning calculé par règles.',
            'invalid_response': 'La réponse de l’IA était inexploitable : planning calculé par règles.'}
        for code, reason in reasons.items():
            with patch('planning.generation.generate_json', side_effect=GeminiError(code)):
                r = self.generate('ai')
            self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual((r.data['generator'], r.data['fallback_reason'], r.data['model_name']), ('RULES', reason, ''), code)
            self.assertTrue(r.data['tasks'])
        with override_settings(GEMINI_PROVIDER='disabled'):
            r = self.generate('ai')
        self.assertEqual((r.data['generator'], r.data['fallback_reason'], r.data['provider']),
            ('RULES', 'L’IA n’est pas configurée sur ce serveur : planning calculé par règles.', 'disabled'))
        self.assertEqual(StudyPlan.objects.filter(student=self.student).count(), 7)

    def test_quotas_fall_back_without_calling_the_provider(self):
        self.every_day('09:00', '11:00', self.other)
        self.goal(student=self.other, learning_group=None)
        other = self.as_user(self.other)
        with override_settings(PLANNING_AI_DAILY_LIMIT=1, PLANNING_AI_DAILY_BUDGET=2):
            self.assertEqual(self.generate('ai').data['generator'], 'AI')
            with patch('planning.generation.generate_json') as call:
                r = self.generate('ai')
                call.assert_not_called()
            self.assertEqual((r.data['generator'], r.data['fallback_reason']), ('RULES', QUOTA))
            # A throttled student does not spend the shared budget.
            self.assertEqual(quota_hits('planning-ai-global', 'global'), 1)
            self.assertEqual(self.get('context/').data['ai']['remaining_today'], 0)
            self.assertEqual(self.generate('ai', other).data['generator'], 'AI')
            self.assertEqual(self.get('context/', other).data['ai']['remaining_today'], 0)
        with override_settings(PLANNING_AI_DAILY_LIMIT=5, PLANNING_AI_DAILY_BUDGET=2):
            r = self.generate('ai', other)
            self.assertEqual((r.status_code, r.data['generator'], r.data['fallback_reason']), (201, 'RULES', QUOTA))
        self.assertEqual(self.generate('rules').data['generator'], 'RULES')
        self.assertEqual(quota_hits('planning-ai', str(self.student.pk)), 2)

    def test_provider_runs_outside_transactions_and_gets_no_personal_data(self):
        seen = {}
        def provider(system, prompt, schema, fake=None, **kwargs):
            seen.update(atomic=connection.in_atomic_block_mongo, system=system, prompt=prompt, schema=schema)
            return GeminiResult(fake(), 'gemini', 'gemini-3.5-flash-lite', 2400, 900, 300)
        self.attempt(self.math, earned=3)
        with patch('planning.generation.generate_json', side_effect=provider):
            r = self.generate('ai')
        self.assertEqual(r.status_code, 201, r.data); self.assertFalse(seen['atomic'])
        self.assertEqual((r.data['provider'], r.data['model_name'], r.data['latency_ms'], r.data['prompt_tokens'], r.data['output_tokens']),
            ('gemini', 'gemini-3.5-flash-lite', 2400, 900, 300))
        for private in ('student@planning.test', 'Élodie', 'Martin', str(self.student.pk)):
            self.assertNotIn(private, seen['prompt'])
        for expected in (str(self.python.pk), str(self.exam.pk), 'Partiel Python', 'Quiz Mathématiques', '"start": "09:00"'):
            self.assertIn(expected, seen['prompt'])
        self.assertIn('UNIQUEMENT', seen['system']); self.assertIs(seen['schema'], RESPONSE_SCHEMA)
        self.assertEqual(RESPONSE_SCHEMA['properties']['tasks']['items']['required'], ['title', 'description', 'date', 'start', 'end'])

    def test_ai_context_content(self):
        self.attempt(self.math, earned=3)
        inputs = planner_inputs(self.student, self.tomorrow, self.tomorrow + timedelta(days=1), at(self.today, 6))
        context = generation.ai_context(self.student, inputs)
        self.assertEqual(set(context), {'today', 'plan', 'windows', 'goals', 'deadlines', 'quiz_results', 'courses'})
        self.assertEqual(context['windows'][0], {'date': self.tomorrow.isoformat(), 'start': '09:00', 'end': '11:00'})
        python = context['goals'][0]
        self.assertEqual((python['title'], len(python['description']), python['remaining_minutes'], python['group'], python['priority']), ('Python', 300, 180, 'Python', 'HIGH'))
        self.assertEqual(context['deadlines'][0]['due_at'], f'{self.tomorrow + timedelta(days=5)}T10:00+01:00')
        self.assertEqual(context['deadlines'][0]['goal_id'], str(self.python.pk))
        self.assertEqual(context['quiz_results'][0]['percent'], 30.0); self.assertEqual(context['courses'], [])

    def test_context_endpoint_and_optional_courses(self):
        self.attempt(self.math, earned=3); self.attempt(self.group, earned=9)
        r = self.get('context/'); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['goals'], r.data['deadlines'], r.data['weekly_minutes']), (2, 1, 840))
        self.assertEqual([(q['quiz_title'], q['group_name'], q['percent']) for q in r.data['quiz_results']],
            [('Quiz Python', 'Python', 90.0), ('Quiz Mathématiques', 'Mathématiques', 30.0)])
        self.assertEqual(r.data['weak_groups'], ['Mathématiques'])
        self.assertEqual((r.data['courses_available'], r.data['courses']), (False, []))
        self.assertEqual(r.data['ai'], {'provider': 'fake', 'configured': True, 'model': 'fake', 'remaining_today': 10})
        original = generation.apps.is_installed
        installed = lambda name: name == 'courses' or original(name)
        services = types.ModuleType('courses.services')
        services.visible_courses = lambda user: [types.SimpleNamespace(pk='c1', title='Algorithmique')]
        services.course_outline = lambda course_id: [{'chapter_id': 'a', 'title': 'Boucles', 'position': 1}, {'chapter_id': 'b', 'title': 'Fonctions', 'position': 2}]
        with patch('planning.generation.apps.is_installed', side_effect=installed), patch.dict(sys.modules, {'courses': types.ModuleType('courses'), 'courses.services': services}):
            r = self.get('context/')
            self.assertEqual((r.data['courses_available'], r.data['courses']), (True, [{'title': 'Algorithmique', 'chapters': 2}]))
            context = generation.ai_context(self.student, planner_inputs(self.student, self.tomorrow, self.tomorrow, at(self.today, 6)))
            self.assertEqual(context['courses'], [{'title': 'Algorithmique', 'chapters': ['Boucles', 'Fonctions']}])
            services.visible_courses = lambda user: 1 / 0
            self.assertEqual(self.get('context/').data['courses_available'], False)
        with patch('planning.generation.apps.is_installed', side_effect=installed):
            self.assertEqual(self.get('context/').data['courses_available'], False)
        with override_settings(GEMINI_PROVIDER='disabled'):
            self.assertEqual(self.get('context/').data['ai'], {'provider': 'disabled', 'configured': False, 'model': None, 'remaining_today': 0})
        with override_settings(GEMINI_PROVIDER='gemini', GEMINI_API_KEY=''):
            self.assertFalse(self.get('context/').data['ai']['configured'])
        with override_settings(GEMINI_PROVIDER='gemini', GEMINI_API_KEY='key', GEMINI_MODEL='gemini-3.5-flash-lite'):
            self.assertEqual(self.get('context/').data['ai'], {'provider': 'gemini', 'configured': True, 'model': 'gemini-3.5-flash-lite', 'remaining_today': 10})
