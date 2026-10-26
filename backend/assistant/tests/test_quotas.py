import hashlib
from types import SimpleNamespace
from unittest.mock import patch
from django.utils import timezone
from rest_framework.exceptions import Throttled
from accounts.models import RateBucket
from accounts.services import limit
from classrooms.models import Enrollment
from assistant import services
from assistant.models import AssistantSettings
from assistant.services import QuotaExceeded, bucket_key, consume, refund, remaining
from .base import DAY, IN_SCOPE, OUT_OF_SCOPE, AssistantTestCase

# A fixed instant 400 seconds before a daily window closes, so that Retry-After is known.
NOW = 20000 * DAY + DAY - 400


class RemainingTests(AssistantTestCase):
    def request(self, user=None):
        return SimpleNamespace(user=user or self.student, META={'REMOTE_ADDR': '203.0.113.9'})

    def test_remaining_reads_the_bucket_that_limit_writes(self):
        with patch('accounts.services.time.time', return_value=NOW):
            identity = f'{self.student.pk}:group:{self.group.pk}'
            self.assertEqual(remaining('assistant-question', identity, 5, DAY), {'limit': 5, 'used': 0, 'remaining': 5})
            for used in (1, 2, 3):
                limit(self.request(), 'assistant-question', maximum=5, seconds=DAY, identity=identity)
                self.assertEqual(remaining('assistant-question', identity, 5, DAY), {'limit': 5, 'used': used, 'remaining': 5 - used})
            expected = hashlib.sha256(f'assistant-question:{identity}:{int(NOW) // DAY}'.encode()).hexdigest()
            self.assertEqual(bucket_key('assistant-question', identity, DAY), expected)
            self.assertEqual(RateBucket.objects.get(key=expected).hits, 3)
            # Another name, identity or window is another bucket.
            self.assertEqual(remaining('assistant-global', identity, 5, DAY)['used'], 0)
            self.assertEqual(remaining('assistant-question', f'{self.other_student.pk}:group:{self.group.pk}', 5, DAY)['used'], 0)
            self.assertEqual(remaining('assistant-question', identity, 5, 3600)['used'], 0)
        with patch('accounts.services.time.time', return_value=NOW + 400):
            self.assertEqual(remaining('assistant-question', identity, 5, DAY), {'limit': 5, 'used': 0, 'remaining': 5})
            limit(self.request(), 'assistant-question', maximum=5, seconds=DAY, identity=identity)
            self.assertEqual(remaining('assistant-question', identity, 5, DAY)['used'], 1)

    def test_used_never_exceeds_the_limit(self):
        identity = 'global'
        for _ in range(7):
            try: limit(self.request(), 'assistant-global', maximum=5, seconds=DAY, identity=identity)
            except Throttled: pass
        self.assertEqual(remaining('assistant-global', identity, 5, DAY), {'limit': 5, 'used': 5, 'remaining': 0})
        self.assertEqual(remaining('assistant-global', identity, 3, DAY), {'limit': 3, 'used': 3, 'remaining': 0})

    def test_refused_and_refunded_calls_leave_the_counter_at_what_was_used(self):
        with patch('accounts.services.time.time', return_value=NOW):
            for _ in range(2): consume(self.request(), 'assistant-question', 2, DAY, 'x', 'Limite.')
            with self.assertRaises(QuotaExceeded) as caught: consume(self.request(), 'assistant-question', 2, DAY, 'x', 'Limite atteinte.')
            self.assertEqual((caught.exception.status_code, caught.exception.default_code, str(caught.exception.detail), caught.exception.wait), (429, 'quota_exceeded', 'Limite atteinte.', 400))
            self.assertEqual(remaining('assistant-question', 'x', 2, DAY)['used'], 2)
            self.assertEqual(RateBucket.objects.get(key=bucket_key('assistant-question', 'x', DAY)).hits, 2)
            # The anti-spam counter keeps every attempt.
            with self.assertRaises(QuotaExceeded):
                for _ in range(3): consume(self.request(), 'assistant-send', 2, 60, 'x', 'Trop vite.', keep_rejected=True)
            self.assertEqual(RateBucket.objects.get(key=bucket_key('assistant-send', 'x', 60)).hits, 3)
            refund('assistant-question', 'x', DAY); refund('assistant-question', 'x', DAY); refund('assistant-question', 'x', DAY)
            self.assertEqual(RateBucket.objects.get(key=bucket_key('assistant-question', 'x', DAY)).hits, 0)
            refund('assistant-question', 'absent', DAY)
            self.assertFalse(RateBucket.objects.filter(key=bucket_key('assistant-question', 'absent', DAY)).exists())


class QuestionQuotaTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = self.start()

    def daily(self, value):
        AssistantSettings.objects.filter(source_type='group', scope_id=str(self.group.pk)).update(daily_question_limit=value)

    def scope_quota(self, client=None):
        scopes = (client or self.student_client).get('/api/assistant/scopes/').data['results']
        return next(s['quota'] for s in scopes if s['key'] == self.scope_key)

    def test_daily_limit_per_scope_with_retry_after(self):
        self.daily(2)
        with patch('accounts.services.time.time', return_value=NOW):
            quotas = [self.answered(self.conversation)['quota'] for _ in range(2)]
            self.assertEqual(quotas, [{'limit': 2, 'used': 1, 'remaining': 1}, {'limit': 2, 'used': 2, 'remaining': 0}])
            response = self.ask(self.conversation)
            error = self.refused(response, 429, 'quota_exceeded')
            self.assertEqual(error['message'], 'Vous avez atteint votre limite de 2 questions pour aujourd’hui dans ce cours. Revenez demain.')
            self.assertEqual(response['Retry-After'], '400')
            self.assertEqual(self.scope_quota(), {'limit': 2, 'used': 2, 'remaining': 0})
            self.assertEqual(self.conversation_messages(), 4)
        with patch('accounts.services.time.time', return_value=NOW + 400):
            self.assertEqual(self.answered(self.conversation)['quota'], {'limit': 2, 'used': 1, 'remaining': 1})

    def conversation_messages(self):
        return len(self.student_client.get(f'/api/assistant/conversations/{self.conversation}/messages/').data['results'])

    def test_the_server_caps_the_teacher_limit(self):
        self.daily(200)
        with self.settings(ASSISTANT_DAILY_QUESTIONS=1):
            self.assertEqual(self.scope_quota(), {'limit': 1, 'used': 0, 'remaining': 1})
            self.answered(self.conversation)
            self.refused(self.ask(self.conversation), 429, 'quota_exceeded')
            data = self.teacher_client.get(f'/api/assistant/settings/group/{self.group.pk}/').data
            self.assertEqual((data['daily_question_limit'], data['effective_daily_limit'], data['max_daily_question_limit']), (200, 1, 1))

    def test_quota_belongs_to_one_student_and_one_scope(self):
        self.daily(1)
        self.answered(self.conversation)
        self.refused(self.ask(self.conversation), 429, 'quota_exceeded')
        classmate = self.as_user(self.other_student)
        self.enrol(self.other_student)
        self.assertEqual(self.ask(self.start(client=classmate), client=classmate).status_code, 201)
        # The teacher's preview has its own counter.
        self.assertEqual(self.ask(self.start(client=self.teacher_client), client=self.teacher_client).status_code, 201)
        # Another scope of the same student is not affected.
        self.enrol(self.student, self.other_group)
        other = self.start(scope_key=self.other_scope_key)
        self.assertEqual(self.answered(other, 'Que vaut l’énergie cinétique ?')['quota'], {'limit': 30, 'used': 1, 'remaining': 29})

    def enrol(self, student, group=None):
        Enrollment.objects.create(student=student, group=group or self.group, starts_at=timezone.now())

    def test_global_budget_is_shared_and_gives_the_scope_quota_back(self):
        with self.settings(ASSISTANT_GLOBAL_DAILY_BUDGET=1):
            self.answered(self.conversation)
            self.enrol(self.other_student)
            classmate = self.as_user(self.other_student)
            conversation = self.start(client=classmate)
            error = self.refused(self.ask(conversation, client=classmate), 429, 'quota_exceeded')
            self.assertEqual(error['message'], 'L’assistant a atteint sa limite d’utilisation pour aujourd’hui. Réessayez demain.')
            self.assertEqual(self.scope_quota(classmate), {'limit': 30, 'used': 0, 'remaining': 30})
            self.assertEqual(remaining('assistant-global', 'global', 1, DAY), {'limit': 1, 'used': 1, 'remaining': 0})
            usage = self.as_user(self.admin).get('/api/assistant/admin/usage/').data['limits']['global_daily_budget']
            self.assertEqual(usage, {'limit': 1, 'used': 1, 'remaining': 0})
            # Questions outside the course are still answered.
            self.assertEqual(self.answered(conversation, OUT_OF_SCOPE, client=classmate)['answer']['status'], 'OUT_OF_SCOPE')

    def test_failed_answers_give_the_question_back(self):
        self.daily(1)
        for marker in ('#erreur', '#quota'):
            self.assertEqual(self.answered(self.conversation, f'{IN_SCOPE} {marker}')['quota'], {'limit': 1, 'used': 0, 'remaining': 1})
        self.assertEqual(self.answered(self.conversation, f'{IN_SCOPE} #bloque')['quota'], {'limit': 1, 'used': 1, 'remaining': 0})
        self.refused(self.ask(self.conversation), 429, 'quota_exceeded')

    def test_scopes_and_answers_report_the_same_quota(self):
        data = self.answered(self.conversation)
        identity = f'{self.student.pk}:group:{self.group.pk}'
        self.assertEqual(data['quota'], self.scope_quota())
        self.assertEqual(data['quota'], remaining('assistant-question', identity, 30, DAY))

    def test_sending_too_fast_is_refused_before_anything_else(self):
        with patch.object(services, 'SEND_PER_MINUTE', 3), patch('accounts.services.time.time', return_value=NOW):
            for _ in range(3): self.answered(self.conversation, OUT_OF_SCOPE)
            for body in ({'content': OUT_OF_SCOPE}, {'content': ''}):
                response = self.student_client.post(f'/api/assistant/conversations/{self.conversation}/messages/', body, format='json')
                error = self.refused(response, 429, 'quota_exceeded')
                self.assertEqual(error['message'], 'Vous envoyez des questions trop rapidement. Patientez une minute avant de réessayer.')
                self.assertEqual(response['Retry-After'], str(60 - int(NOW) % 60))
            # The refusal comes before the conversation is even looked up.
            self.refused(self.ask('0' * 24), 429, 'quota_exceeded')
            self.assertEqual(RateBucket.objects.get(key=bucket_key('assistant-send', str(self.student.pk), 60)).hits, 6)
            self.assertEqual(self.ask(self.start(client=self.teacher_client), client=self.teacher_client).status_code, 201)

    def test_opening_too_many_conversations_is_refused(self):
        with patch.object(services, 'CONVERSATIONS_PER_HOUR', 2):
            self.start()
            error = self.refused(self.student_client.post('/api/assistant/conversations/', {'scope_key': self.scope_key}, format='json'), 429, 'quota_exceeded')
            self.assertEqual(error['message'], 'Vous avez ouvert beaucoup de conversations en peu de temps. Réessayez dans une heure.')
            self.assertEqual(self.student_client.get('/api/assistant/conversations/').data['count'], 2)
