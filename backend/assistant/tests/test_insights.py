import csv
import io
from datetime import datetime, time, timedelta
from django.test import override_settings
from django.utils import timezone
from classrooms.models import LearningGroup
from assistant.insights import csv_safe, percentile
from assistant.models import AnswerFeedback, AssistantSettings, Citation, Conversation, Message
from .base import IN_SCOPE, OUT_OF_SCOPE, AssistantTestCase


def cite(kind, source_id, title):
    return Citation(number=1, source_kind=kind, source_id=source_id, source_title=title, excerpt='…', score=2.0)


NOTE_A, NOTE_B = cite('NOTE', 'a' * 24, 'Les vecteurs'), cite('RESOURCE', 'b' * 24, 'Cours PDF')


class ExchangeTestCase(AssistantTestCase):
    """Questions and answers written with chosen dates, statuses and measurements."""

    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.conversations = {}

    def at(self, days_ago, hour=10):
        return datetime.combine(self.today - timedelta(days=days_ago), time(hour), timezone.get_current_timezone())

    def exchange(self, owner, question, status='COMPLETE', days_ago=0, latency=None, input_mode='TEXT', citations=(), group=None, **fields):
        group = group or self.group
        key = (owner.pk, group.pk)
        if key not in self.conversations: self.conversations[key] = self.conversation_row(owner=owner, group=group)
        conversation = self.conversations[key]
        asked = self.message_row(conversation, content=question, input_mode=input_mode)
        answer = self.message_row(conversation, 'ASSISTANT', content='Réponse.', status=status, latency_ms=latency, reply_to=asked, citations=list(citations), **fields)
        Message.objects.filter(pk__in=[asked.pk, answer.pk]).update(created_at=self.at(days_ago))
        return answer

    def rate(self, answer, rating, shared=False, reasons=()):
        AnswerFeedback.objects.create(message=answer, conversation_id=answer.conversation_id, student_id=answer.owner_id, source_type=answer.source_type,
            scope_id=answer.scope_id, rating=rating, reasons=list(reasons), shared_with_teacher=shared)


class InsightsTests(ExchangeTestCase):
    def dataset(self):
        first = self.exchange(self.student, 'Qu’est-ce qu’un vecteur ?', latency=100, citations=[NOTE_A, NOTE_A])
        second = self.exchange(self.student, 'Norme ?', days_ago=1, latency=300, input_mode='VOICE', citations=[NOTE_A, NOTE_B])
        self.exchange(self.student, 'Quelle est la capitale ?', 'OUT_OF_SCOPE', days_ago=1)
        self.exchange(self.student, '=HYPERLINK("http://exemple.test")', 'OUT_OF_SCOPE', days_ago=2)
        self.exchange(self.student, '  quelle est LA   capitale  ', 'OUT_OF_SCOPE')
        self.exchange(self.student, 'Une question qui échoue', 'FAILED', error_code='unavailable')
        self.exchange(self.other_student, 'Écrivez-moi à jean.dupont@example.com ou au 06 12 34 56 78', 'OUT_OF_SCOPE')
        third = self.exchange(self.other_student, 'Et la direction ?', latency=500, input_mode='VOICE', citations=[NOTE_B])
        self.exchange(self.other_student, 'Une question bloquée', 'BLOCKED', days_ago=3, error_code='blocked')
        preview = self.exchange(self.teacher, 'Test de l’enseignant', latency=9999, citations=[NOTE_A])
        self.exchange(self.student, 'Trop ancienne', latency=1, days_ago=40)
        self.exchange(self.student, 'Autre groupe', latency=1, group=self.other_group)
        self.rate(first, 'UP', shared=True); self.rate(second, 'DOWN', reasons=['UNCLEAR']); self.rate(third, 'DOWN', shared=True, reasons=['INCORRECT'])
        self.rate(preview, 'UP')

    def insights(self, query='', client=None, status=200):
        response = (client or self.teacher_client).get(f'/api/assistant/insights/group/{self.group.pk}/{query}')
        self.assertEqual(response.status_code, status, getattr(response, 'data', response))
        return response

    def test_numbers_over_the_default_period(self):
        self.dataset()
        data = self.insights().data
        start = self.today - timedelta(days=29)
        self.assertEqual({k: data[k] for k in ('scope', 'period', 'questions', 'active_students', 'voice_questions', 'voice_share', 'answers_by_status',
                'satisfaction', 'feedback', 'out_of_scope_rate', 'latency_ms', 'low_rated_answers')}, {
            'scope': {'source_type': 'group', 'scope_id': str(self.group.pk), 'key': self.scope_key, 'title': 'Seconde A'},
            'period': {'from': start.isoformat(), 'to': self.today.isoformat()},
            'questions': 9, 'active_students': 2, 'voice_questions': 2, 'voice_share': 0.222,
            'answers_by_status': {'COMPLETE': 3, 'OUT_OF_SCOPE': 4, 'FAILED': 1, 'BLOCKED': 1},
            'satisfaction': 0.333, 'feedback': {'up': 1, 'down': 2, 'shared': 2}, 'out_of_scope_rate': 0.444,
            'latency_ms': {'p50': 300, 'p95': 500}, 'low_rated_answers': 2})
        per_day = {item['date']: item['questions'] for item in data['questions_per_day']}
        self.assertEqual((len(per_day), list(per_day)[0], list(per_day)[-1]), (30, start.isoformat(), self.today.isoformat()))
        self.assertEqual([per_day[(self.today - timedelta(days=n)).isoformat()] for n in range(5)], [5, 2, 1, 1, 0])
        self.assertEqual(data['top_sources'], [{'source_kind': 'RESOURCE', 'source_id': 'b' * 24, 'title': 'Cours PDF', 'count': 2},
            {'source_kind': 'NOTE', 'source_id': 'a' * 24, 'title': 'Les vecteurs', 'count': 2}])
        # Unanswered questions are merged once normalised, anonymised, and the most recent wording is kept.
        self.assertEqual(data['unanswered_questions'], [{'question': 'quelle est LA capitale', 'count': 2},
            {'question': 'Écrivez-moi à [adresse] ou au [numéro]', 'count': 1}, {'question': '=HYPERLINK("http://exemple.test")', 'count': 1}])

    def test_empty_scope_has_no_rates(self):
        data = self.insights().data
        self.assertEqual((data['questions'], data['voice_share'], data['satisfaction'], data['out_of_scope_rate'], data['latency_ms'], data['top_sources'],
            data['unanswered_questions']), (0, None, None, None, {'p50': None, 'p95': None}, [], []))

    def test_questions_without_words_are_not_listed_as_unanswered(self):
        self.exchange(self.student, '???', 'OUT_OF_SCOPE'); self.exchange(self.student, '¿ … !', 'OUT_OF_SCOPE')
        data = self.insights().data
        self.assertEqual((data['questions'], data['answers_by_status']['OUT_OF_SCOPE'], data['unanswered_questions']), (2, 2, []))

    def test_real_exchanges_are_counted(self):
        conversation = self.start()
        answer = self.answered(conversation)['answer']
        self.answered(self.start(), OUT_OF_SCOPE)
        self.answered(conversation, IN_SCOPE, input_mode='VOICE')
        self.student_client.put(f'/api/assistant/messages/{answer["id"]}/feedback/', {'rating': 'UP'}, format='json')
        data = self.insights().data
        self.assertEqual((data['questions'], data['voice_questions'], data['answers_by_status']['COMPLETE'], data['answers_by_status']['OUT_OF_SCOPE'], data['satisfaction']),
            (3, 1, 2, 1, 1.0))
        self.assertEqual(data['top_sources'][0], {'source_kind': 'NOTE', 'source_id': str(self.note.pk), 'title': 'Les vecteurs', 'count': 2})
        self.assertEqual(data['unanswered_questions'], [{'question': OUT_OF_SCOPE, 'count': 1}])

    def test_period_choice(self):
        self.dataset()
        data = self.insights(f'?from={(self.today - timedelta(days=2)).isoformat()}&to={(self.today - timedelta(days=1)).isoformat()}').data
        self.assertEqual((data['questions'], [d['questions'] for d in data['questions_per_day']]), (3, [1, 2]))
        old = self.insights(f'?from={(self.today - timedelta(days=45)).isoformat()}').data
        self.assertEqual((old['questions'], len(old['questions_per_day'])), (10, 46))
        self.assertEqual(len(self.insights(f'?from={(self.today - timedelta(days=179)).isoformat()}').data['questions_per_day']), 180)
        cases = [(f'?from={self.today.isoformat()}&to={(self.today - timedelta(days=1)).isoformat()}', 'from'),
            (f'?from={(self.today - timedelta(days=180)).isoformat()}', 'to'), ('?from=26/10/2026', 'from'), ('?to=demain', 'to'), ('?format=xml', 'format')]
        for query, field in cases:
            with self.subTest(query=query): self.assertIn(field, self.insights(query, status=400).data['error']['fields'])

    def test_csv_export_neutralises_formulas(self):
        LearningGroup.objects.filter(pk=self.group.pk).update(name='=SOMME(A1:A9)')
        self.dataset()
        self.exchange(self.student, '@cmd bonjour', 'OUT_OF_SCOPE')
        self.exchange(self.student, '-2 est-il pair ?', 'OUT_OF_SCOPE')
        response = self.insights('?format=csv')
        self.assertEqual((response['Content-Type'], response['Content-Disposition'], response['Cache-Control']),
            ('text/csv; charset=utf-8', f'attachment; filename="assistant-group-{self.group.pk}.csv"', 'private, no-store'))
        text = response.content.decode('utf-8')
        self.assertTrue(text.startswith('﻿'))
        rows = list(csv.reader(io.StringIO(text[1:]), delimiter=';'))
        self.assertEqual(rows[0], ['Assistant pédagogique', "'=SOMME(A1:A9)"])
        values = dict(row for row in rows if len(row) == 2)
        self.assertEqual((values['Questions'], values['Étudiants actifs'], values['Part des questions vocales'], values['Satisfaction'], values['Latence médiane (ms)']),
            ('11', '2', '18,2 %', '33,3 %', '300'))
        questions = [row[0] for row in rows[rows.index(['Question restée sans réponse', 'Occurrences']) + 1:]]
        self.assertIn('\'=HYPERLINK("http://exemple.test")', questions)
        self.assertIn("'@cmd bonjour", questions); self.assertIn("'-2 est-il pair ?", questions)
        self.assertFalse([cell for row in rows for cell in row if cell[:1] in ('=', '+', '-', '@')])
        sources = rows[rows.index(['Source la plus citée', 'Citations']) + 1:rows.index(['Source la plus citée', 'Citations']) + 3]
        self.assertEqual(sources, [['Cours PDF', '2'], ['Les vecteurs', '2']])

    def test_csv_safe(self):
        cases = {'=1+1': "'=1+1", '+33 6': "'+33 6", '-5': "'-5", '@SUM(A1)': "'@SUM(A1)", '  =A1': "'  =A1", '\t=A1': "'\t=A1", 'Texte': 'Texte',
            '': '', None: '', 12: '12', 'a=b': 'a=b'}
        self.assertEqual({value: csv_safe(value) for value in cases}, cases)

    def test_percentiles_use_the_nearest_rank(self):
        self.assertEqual([percentile([], 50), percentile([7], 95), percentile([1, 2, 3, 4], 50), percentile(list(range(1, 101)), 95), percentile([5, 1, 3], 95)],
            [None, 7, 2, 95, 5])

    def test_only_managers_of_the_scope_read_insights(self):
        self.assertEqual(self.insights(client=self.as_user(self.admin)).status_code, 200)
        self.refused(self.insights(client=self.as_user(self.other_teacher), status=404), 404, 'not_found')
        self.refused(self.insights(client=self.student_client, status=403), 403, 'permission_denied')
        self.assertIn('source_type', self.teacher_client.get(f'/api/assistant/insights/video/{self.group.pk}/').data['error']['fields'])


@override_settings(ASSISTANT_GLOBAL_DAILY_BUDGET=50, ASSISTANT_DAILY_QUESTIONS=20, ASSISTANT_VOICE_PER_HOUR=7, ASSISTANT_MAX_AUDIO_SECONDS=45)
class AdminUsageTests(ExchangeTestCase):
    def test_numbers_over_the_last_thirty_days(self):
        AssistantSettings.objects.create(source_type='group', scope_id=str(self.group.pk), scope_title='Seconde A')
        AssistantSettings.objects.create(source_type='group', scope_id=str(self.other_group.pk), scope_title='Terminale B')
        self.exchange(self.student, 'Q1', provider='gemini', model_name='gemini-3.5-flash-lite', prompt_tokens=800, output_tokens=60)
        self.exchange(self.student, 'Q2', 'FAILED', provider='gemini', error_code='quota')
        self.exchange(self.student, 'Q3', 'OUT_OF_SCOPE')
        self.exchange(self.other_student, 'Q4', 'BLOCKED', days_ago=3, group=self.other_group, provider='fake', error_code='blocked', prompt_tokens=50)
        self.exchange(self.other_student, 'Q5', 'FAILED', group=self.other_group, provider='disabled', error_code='disabled')
        self.exchange(self.teacher, 'Q6', 'FAILED', provider='gemini')
        self.exchange(self.student, 'Q7', provider='gemini', prompt_tokens=10, output_tokens=10, days_ago=31)
        response = self.as_user(self.admin).get('/api/assistant/admin/usage/')
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(data['period'], {'from': (self.today - timedelta(days=29)).isoformat(), 'to': self.today.isoformat()})
        self.assertEqual(len(data['days']), 30)
        self.assertEqual(data['days'][-1], {'date': self.today.isoformat(), 'questions': 5, 'gemini_calls': 3, 'failures': 3, 'prompt_tokens': 800, 'output_tokens': 60})
        self.assertEqual(data['days'][-4], {'date': (self.today - timedelta(days=3)).isoformat(), 'questions': 1, 'gemini_calls': 1, 'failures': 1, 'prompt_tokens': 50, 'output_tokens': 0})
        self.assertEqual(data['totals'], {'questions': 6, 'gemini_calls': 4, 'failures': 4, 'prompt_tokens': 850, 'output_tokens': 60})
        self.assertEqual(data['failures_by_code'], {'blocked': 1, 'disabled': 1, 'quota': 1, 'unknown': 1})
        self.assertEqual(data['top_scopes'], [{'scope_key': self.scope_key, 'source_type': 'group', 'scope_id': str(self.group.pk), 'title': 'Seconde A', 'questions': 4},
            {'scope_key': self.other_scope_key, 'source_type': 'group', 'scope_id': str(self.other_group.pk), 'title': 'Terminale B', 'questions': 2}])
        self.assertEqual(data['providers'], {'llm': {'provider': 'fake', 'configured': True, 'model': 'fake-gemini', 'fallback_model': ''},
            'transcription': {'provider': 'fake', 'configured': True, 'model': 'fake-whisper'}})
        self.assertEqual(data['limits'], {'global_daily_budget': {'limit': 50, 'used': 0, 'remaining': 50}, 'daily_questions_per_user': 20,
            'voice_per_hour': 7, 'max_audio_seconds': 45})

    def test_only_the_administrator_reads_usage(self):
        for client in (self.teacher_client, self.student_client):
            self.refused(client.get('/api/assistant/admin/usage/'), 403, 'permission_denied')

    def test_global_budget_in_use(self):
        self.answered(self.start())
        self.assertEqual(self.as_user(self.admin).get('/api/assistant/admin/usage/').data['limits']['global_daily_budget'], {'limit': 50, 'used': 1, 'remaining': 49})
