import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from bson import ObjectId
from django.db import DatabaseError, IntegrityError, connection, connections
from django.test import override_settings
from django.utils import timezone
from django_mongodb_backend import transaction
from accounts.models import RateBucket
from classrooms.models import Enrollment, LearningGroup
from quizzes.models import Attempt, Quiz
from assistant import services
from assistant.content import NotesProvider
from assistant.indexing import ensure_index
from assistant.llm import MESSAGES, LLMError, LLMResult
from assistant.models import AssistantSettings, Conversation, Message, TeacherNote
from assistant.prompts import OUT_OF_SCOPE_MESSAGE
from assistant.services import bucket_key, remaining
from .base import DAY, FIRST_SENTENCE, IN_SCOPE, OUT_OF_SCOPE, AssistantTestCase
from .test_llm import SERVER_DATABASE, gemini, reply

MESSAGE_KEYS = {'id', 'conversation_id', 'role', 'reply_to_id', 'content', 'input_mode', 'status', 'status_label', 'unsourced', 'citations',
    'follow_ups', 'latency_ms', 'created_at', 'feedback'}
CONVERSATION_KEYS = {'id', 'source_type', 'scope_id', 'scope_key', 'scope_title', 'title', 'mode', 'mode_label', 'status', 'status_label',
    'pinned', 'message_count', 'last_message_at', 'created_at', 'purge_at', 'can_send'}


def model_answer(text='La norme est la longueur du vecteur [S1].', out_of_scope=False):
    return LLMResult({'answer': text, 'out_of_scope': out_of_scope, 'follow_ups': ['Et sa direction ?']}, 'gemini', 'gemini-3.5-flash-lite', 640, 900, 40)


class AskFlowTests(AssistantTestCase):
    def quota(self, user=None, group=None, maximum=30):
        user, group = user or self.student, group or self.group
        return remaining('assistant-question', f'{user.pk}:group:{group.pk}', maximum, DAY)

    def test_sourced_answer_with_its_citations_and_metrics(self):
        conversation = self.start()
        data = self.answered(conversation)
        self.assertEqual(set(data), {'question', 'answer', 'conversation', 'quota'})
        question, answer = data['question'], data['answer']
        self.assertEqual((set(question), set(answer), set(data['conversation'])), (MESSAGE_KEYS, MESSAGE_KEYS, CONVERSATION_KEYS))
        self.assertEqual((question['role'], question['content'], question['input_mode'], question['status'], question['latency_ms'], question['feedback'],
            question['citations'], question['reply_to_id']), ('USER', IN_SCOPE, 'TEXT', 'COMPLETE', None, None, [], None))
        self.assertEqual((answer['role'], answer['status'], answer['status_label'], answer['unsourced'], answer['reply_to_id'], answer['feedback'],
            answer['conversation_id']), ('ASSISTANT', 'COMPLETE', 'Réponse', False, question['id'], None, conversation))
        self.assertEqual(answer['content'], f'D’après le cours : {FIRST_SENTENCE} [S1]')
        self.assertEqual(answer['follow_ups'], ['Peux-tu donner un exemple ?', 'Quels sont les points essentiels à retenir ?'])
        citation = answer['citations'][0]
        self.assertEqual(citation, {'number': 1, 'source_kind': 'NOTE', 'source_id': str(self.note.pk), 'source_title': 'Les vecteurs',
            'chapter_title': 'Définition', 'page': None, 'start_seconds': None, 'url': '',
            'excerpt': 'Un vecteur est défini par une direction, un sens et une norme. La norme d’un vecteur est sa longueur.', 'score': citation['score']})
        self.assertGreater(citation['score'], 1.0); self.assertIsInstance(answer['latency_ms'], int)
        self.assertEqual((data['conversation']['title'], data['conversation']['message_count'], data['conversation']['can_send']), (IN_SCOPE, 2, True))
        self.assertEqual(data['quota'], {'limit': 30, 'used': 1, 'remaining': 29})
        stored = Message.objects.get(pk=answer['id'])
        self.assertEqual((stored.provider, stored.model_name, stored.error_code, stored.chunks_used, stored.top_score, stored.purge_at),
            ('fake', 'fake-gemini', '', 3, citation['score'], None))
        self.assertGreater(stored.prompt_tokens, 0); self.assertGreater(stored.output_tokens, 0); self.assertGreaterEqual(stored.retrieval_ms, 0)
        self.assertEqual(Message.objects.get(pk=question['id']).owner_id, self.student.pk)

    def test_voice_questions_are_marked(self):
        data = self.answered(self.start(), IN_SCOPE, input_mode='VOICE')
        self.assertEqual((data['question']['input_mode'], data['answer']['input_mode']), ('VOICE', 'TEXT'))

    def test_model_runs_after_the_question_is_saved_and_outside_any_transaction(self):
        with transaction.atomic(): self.assertTrue(connection.in_atomic_block_mongo)
        conversation = self.start()
        seen = []
        def answer(system, contents, schema, **options):
            seen.append((connection.in_atomic_block_mongo, connection.in_atomic_block,
                Message.objects.filter(conversation_id=conversation, role='USER').count(), Message.objects.filter(conversation_id=conversation, role='ASSISTANT').count()))
            return model_answer()
        with patch('assistant.services.generate_answer', side_effect=answer):
            data = self.answered(conversation)
        self.assertEqual(seen, [(False, False, 1, 0)])
        stored = Message.objects.get(pk=data['answer']['id'])
        self.assertEqual((stored.provider, stored.model_name, stored.prompt_tokens, stored.output_tokens, stored.content),
            ('gemini', 'gemini-3.5-flash-lite', 900, 40, 'La norme est la longueur du vecteur [S1].'))

    @override_settings(ASSISTANT_LLM_PROVIDER='gemini', GEMINI_API_KEY='test-key-0000', GEMINI_MODEL='gemini-3.5-flash-lite', GEMINI_FALLBACK_MODEL='gemini-3.1-flash-lite')
    def test_gemini_request_runs_outside_transactions_and_names_nobody(self):
        conversation = self.start()
        requests = []
        def urlopen(request, timeout):
            requests.append((json.loads(request.data), connection.in_atomic_block_mongo)); return reply(gemini())
        with patch('assistant.llm.connection', SERVER_DATABASE), patch('urllib.request.urlopen', side_effect=urlopen):
            answer = self.answered(conversation)['answer']
        (body, atomic), = requests
        self.assertFalse(atomic)
        sent = json.dumps(body, ensure_ascii=False)
        self.assertIn(IN_SCOPE, sent); self.assertIn('Seconde A', sent)
        for private in (self.student.first_name, self.student.last_name, self.student.email, str(self.student.pk), self.teacher.last_name, str(self.teacher.pk), conversation):
            self.assertNotIn(private, sent)
        self.assertEqual((answer['status'], answer['content'], answer['citations'][0]['number']), ('COMPLETE', 'La norme est une longueur [S1].', 1))
        stored = Message.objects.get(pk=answer['id'])
        self.assertEqual((stored.provider, stored.model_name, stored.prompt_tokens, stored.output_tokens), ('gemini', 'gemini-3.5-flash-lite', 812, 64))

    @override_settings(ASSISTANT_LLM_PROVIDER='gemini', GEMINI_API_KEY='test-key-0000')
    def test_real_provider_never_runs_against_the_test_database(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        conversation = self.start()
        with patch('urllib.request.urlopen', side_effect=AssertionError('network')) as urlopen:
            answer = self.answered(conversation)['answer']
        self.assertFalse(urlopen.called)
        self.assertEqual((answer['status'], answer['content']), ('FAILED', 'Le fournisseur Gemini réel est désactivé sur une base de test.'))
        self.assertEqual(Message.objects.get(pk=answer['id']).error_code, 'disabled')

    def test_out_of_scope_question_needs_neither_the_model_nor_the_quota(self):
        AssistantSettings.objects.create(source_type='group', scope_id=str(self.group.pk), scope_title='Seconde A', daily_question_limit=1)
        conversation = self.start()
        self.answered(conversation)
        counters = lambda: {key: RateBucket.objects.filter(key=key).values_list('hits', flat=True).first()
            for key in (bucket_key('assistant-question', f'{self.student.pk}:group:{self.group.pk}', DAY), bucket_key('assistant-global', 'global', DAY))}
        before = counters()
        self.assertEqual(list(before.values()), [1, 1])
        # The quota is exhausted, and a question outside the course is still answered.
        fresh = self.start()
        with patch('assistant.services.generate_answer', side_effect=AssertionError('the model must not be called')):
            data = self.answered(fresh, OUT_OF_SCOPE)
        answer = data['answer']
        self.assertEqual((answer['status'], answer['status_label'], answer['content'], answer['citations'], answer['follow_ups'], answer['unsourced']),
            ('OUT_OF_SCOPE', 'Hors cours', OUT_OF_SCOPE_MESSAGE, [], [], False))
        self.assertEqual((data['quota'], counters()), ({'limit': 1, 'used': 1, 'remaining': 0}, before))
        stored = Message.objects.get(pk=answer['id'])
        self.assertEqual((stored.provider, stored.model_name, stored.top_score, stored.chunks_used, stored.prompt_tokens, stored.error_code), ('', '', None, 0, None, ''))
        self.assertEqual(data['conversation']['title'], OUT_OF_SCOPE)
        self.refused(self.ask(fresh), 429, 'quota_exceeded')
        # After a question of the course, its words are borrowed for the follow-up: the model, not the index, refuses.
        self.refused(self.ask(conversation, OUT_OF_SCOPE), 429, 'quota_exceeded')

    def test_out_of_scope_decided_by_the_model_counts(self):
        data = self.answered(self.start(), f'{IN_SCOPE} #horscours')
        self.assertEqual((data['answer']['status'], data['answer']['content'], data['answer']['citations'], data['quota']['used']),
            ('OUT_OF_SCOPE', 'Les extraits du cours ne traitent pas de cette question.', [], 1))
        self.assertEqual(Message.objects.get(pk=data['answer']['id']).provider, 'fake')

    def test_provider_failures_are_saved_as_answers(self):
        conversation = self.start()
        # Only a request that no model processed gives the question back.
        used = 0
        for marker, status, code, cost in (('#erreur', 'FAILED', 'unavailable', 1), ('#quota', 'FAILED', 'quota', 0), ('#bloque', 'BLOCKED', 'blocked', 1)):
            with self.subTest(marker=marker):
                data = self.answered(conversation, f'{IN_SCOPE} {marker}')
                answer, used = data['answer'], used + cost
                self.assertEqual((answer['status'], answer['content'], answer['citations'], answer['follow_ups']), (status, MESSAGES[code], [], []))
                stored = Message.objects.get(pk=answer['id'])
                self.assertEqual((stored.error_code, stored.provider, stored.model_name, stored.chunks_used), (code, 'fake', 'fake-gemini', 3))
                self.assertEqual((data['quota']['used'], self.quota()['used']), (used, used))
                self.assertTrue(data['conversation']['can_send'])
        for code, cost in (('auth', 0), ('refused', 1), ('invalid_response', 1), ('disabled', 0)):
            error = LLMError(code, model='gemini-3.5-flash-lite'); error.provider = 'gemini'
            with self.subTest(code=code), patch('assistant.services.generate_answer', side_effect=error):
                data = self.answered(conversation, IN_SCOPE)
                answer, used = data['answer'], used + cost
                self.assertEqual((answer['status'], answer['content'], data['quota']['used']), ('FAILED', MESSAGES[code], used))
                self.assertEqual(Message.objects.get(pk=answer['id']).error_code, code)
        self.assertEqual((self.quota()['used'], remaining('assistant-global', 'global', 400, DAY)['used']), (4, 4))
        self.assertEqual(Conversation.objects.get(pk=conversation).message_count, 14)

    @override_settings(ASSISTANT_LLM_PROVIDER='disabled')
    def test_unconfigured_assistant_explains_itself(self):
        answer = self.answered(self.start())['answer']
        self.assertEqual((answer['status'], answer['content']), ('FAILED', MESSAGES['disabled']))
        stored = Message.objects.get(pk=answer['id'])
        self.assertEqual((stored.provider, stored.error_code), ('disabled', 'disabled'))

    def test_replayed_client_id_returns_the_stored_pair(self):
        conversation = self.start(); client_id = str(uuid.uuid4())
        first = self.answered(conversation, IN_SCOPE, client_id=client_id)
        self.assertEqual(Message.objects.get(pk=first['question']['id']).client_id, client_id)
        self.student_client.put(f'/api/assistant/messages/{first["answer"]["id"]}/feedback/', {'rating': 'UP'}, format='json')
        with patch('assistant.services.generate_answer', side_effect=AssertionError('answered twice')):
            for value in (client_id, client_id.upper()):
                with self.subTest(client_id=value):
                    replay = self.ask(conversation, 'Un tout autre texte', client_id=value)
                    self.assertEqual(replay.status_code, 200, replay.data)
                    self.assertEqual((replay.data['question']['id'], replay.data['answer']['id'], replay.data['answer']['content'], replay.data['quota']),
                        (first['question']['id'], first['answer']['id'], first['answer']['content'], first['quota']))
                    self.assertEqual(replay.data['answer']['feedback']['rating'], 'UP')
        self.assertEqual((Message.objects.filter(conversation_id=conversation).count(), Conversation.objects.get(pk=conversation).message_count), (2, 2))
        # A replay reports what happened to the first send, even once the conversation is archived.
        self.student_client.patch(f'/api/assistant/conversations/{conversation}/', {'status': 'ARCHIVED'}, format='json')
        replay = self.ask(conversation, IN_SCOPE, client_id=client_id)
        self.assertEqual((replay.status_code, replay.data['answer']['id'], replay.data['conversation']['can_send']), (200, first['answer']['id'], False))
        # The key belongs to one conversation.
        self.assertEqual(self.ask(self.start(), IN_SCOPE, client_id=client_id).status_code, 201)

    def test_replay_before_the_answer_is_written_is_refused(self):
        conversation = self.start(); client_id = str(uuid.uuid4())
        self.message_row(Conversation.objects.get(pk=conversation), content=IN_SCOPE, client_id=client_id, has_client_id=True)
        self.refused(self.ask(conversation, IN_SCOPE, client_id=client_id), 409, 'answer_in_progress')
        self.assertEqual(Message.objects.filter(conversation_id=conversation).count(), 1)

    def test_one_question_per_client_id_is_enforced_by_the_database(self):
        conversation = Conversation.objects.get(pk=self.start()); client_id = str(uuid.uuid4())
        self.message_row(conversation, content='Q', client_id=client_id, has_client_id=True)
        with self.assertRaises(IntegrityError): self.message_row(conversation, content='Q', client_id=client_id, has_client_id=True)
        # Questions without a key never collide.
        self.message_row(conversation, content='A'); self.message_row(conversation, content='B')
        self.message_row(Conversation.objects.get(pk=self.start()), content='Q', client_id=client_id, has_client_id=True)

    def test_concurrent_sends_of_one_client_id_create_one_pair(self):
        conversation = self.start(); client_id = str(uuid.uuid4())
        ensure_index(NotesProvider(), str(self.group.pk))
        barrier, save = threading.Barrier(2, timeout=20), services.save_question
        def together(*args):
            # Both requests have passed the replay check before either one saves its question.
            barrier.wait(); return save(*args)
        def slow(*args, **kwargs):
            time.sleep(0.3); return model_answer()
        def send(_):
            try: return self.ask(conversation, IN_SCOPE, client=self.as_user(self.student), client_id=client_id).status_code
            finally: connections.close_all()
        with patch('assistant.services.save_question', together), patch('assistant.services.generate_answer', side_effect=slow), ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(send, range(2)))
        self.assertIn(statuses, ([201, 409], [200, 201]))
        self.assertEqual(sorted(Message.objects.filter(conversation_id=conversation).values_list('role', flat=True)), ['ASSISTANT', 'USER'])
        self.assertEqual(Conversation.objects.get(pk=conversation).message_count, 2)
        self.assertEqual(self.quota()['used'], 1)
        self.assertEqual(remaining('assistant-global', 'global', 400, DAY)['used'], 1)

    def test_question_that_cannot_be_saved_gives_the_quota_back(self):
        conversation = self.start()
        with patch('assistant.services.save_question', side_effect=IntegrityError('E11000 duplicate key')), \
                patch('assistant.services.generate_answer', side_effect=AssertionError('the model must not be called')):
            self.refused(self.ask(conversation, IN_SCOPE, client_id=str(uuid.uuid4())), 409, 'conflict')
        self.assertEqual((self.quota()['used'], remaining('assistant-global', 'global', 400, DAY)['used'], Message.objects.count()), (0, 0, 0))

    def test_write_conflicts_on_the_question_are_retried_without_counting_twice(self):
        conversation = self.start()
        create, calls = Message.objects.create, []
        def flaky(**fields):
            calls.append(fields['role'])
            if len(calls) == 1: raise DatabaseError('WriteConflict')
            return create(**fields)
        with patch.object(Message.objects, 'create', flaky):
            data = self.answered(conversation)
        self.assertEqual((calls, data['conversation']['message_count'], data['quota']['used']), (['USER', 'USER', 'ASSISTANT'], 2, 1))
        self.assertEqual(Message.objects.filter(conversation_id=conversation).count(), 2)
        # A write that keeps conflicting is reported, and the question it could not save is not counted.
        with patch.object(Message.objects, 'create', side_effect=DatabaseError('WriteConflict')), \
                patch('assistant.services.generate_answer', side_effect=AssertionError('the model must not be called')):
            self.refused(self.ask(conversation), 409, 'conflict')
        self.assertEqual((Message.objects.count(), Conversation.objects.get(pk=conversation).message_count), (2, 2))
        self.assertEqual((self.quota()['used'], remaining('assistant-global', 'global', 400, DAY)['used']), (1, 1))

    def test_conversation_of_a_module_no_longer_installed_is_read_only(self):
        row = Conversation.objects.create(owner=self.student, source_type='course', scope_id=str(ObjectId()), scope_title='Physique')
        self.assertFalse(self.student_client.get(f'/api/assistant/conversations/{row.pk}/').data['can_send'])
        self.assertFalse(self.student_client.get('/api/assistant/conversations/').data['results'][0]['can_send'])
        self.refused(self.ask(str(row.pk)), 403, 'scope_unavailable')
        self.assertEqual(self.student_client.get(f'/api/assistant/conversations/{row.pk}/export/').status_code, 200)

    def test_duplicate_whose_twin_already_finished_gets_the_twin_answer(self):
        conversation = self.start(); client_id = str(uuid.uuid4())
        row = Conversation.objects.get(pk=conversation)
        def twin_finished(*args):
            # The first send saved its question and its answer after this one checked for a replay.
            question = self.message_row(row, content=IN_SCOPE, client_id=client_id, has_client_id=True)
            self.message_row(row, 'ASSISTANT', content='Réponse du premier envoi [S1].', reply_to=question)
            raise IntegrityError('E11000 duplicate key')
        with patch('assistant.services.save_question', side_effect=twin_finished):
            response = self.ask(conversation, IN_SCOPE, client_id=client_id)
        self.assertEqual((response.status_code, response.data['answer']['content']), (200, 'Réponse du premier envoi [S1].'))
        self.assertEqual((self.quota()['used'], remaining('assistant-global', 'global', 400, DAY)['used']), (0, 0))

    def test_archived_and_trashed_conversations_are_read_only(self):
        archived, trashed = self.start(), self.start()
        self.student_client.patch(f'/api/assistant/conversations/{archived}/', {'status': 'ARCHIVED'}, format='json')
        self.student_client.delete(f'/api/assistant/conversations/{trashed}/')
        error = self.refused(self.ask(archived), 409, 'conversation_locked')
        self.assertEqual(error['message'], 'Cette conversation est archivée : désarchivez-la pour poser une nouvelle question.')
        error = self.refused(self.ask(trashed), 409, 'conversation_locked')
        self.assertEqual(error['message'], 'Cette conversation est dans la corbeille : restaurez-la pour continuer.')
        self.assertEqual((Message.objects.count(), self.quota()['used']), (0, 0))

    def test_lost_access_makes_the_conversation_read_only(self):
        conversation = self.start()
        self.answered(conversation)
        cases = [('enrollment ended', lambda: Enrollment.objects.filter(student=self.student).update(ends_at=timezone.now()),
                lambda: Enrollment.objects.filter(student=self.student).update(ends_at=None)),
            ('group archived', lambda: LearningGroup.objects.filter(pk=self.group.pk).update(archived=True), lambda: LearningGroup.objects.filter(pk=self.group.pk).update(archived=False)),
            ('notes removed', lambda: TeacherNote.objects.filter(group=self.group).update(group=self.other_group), lambda: TeacherNote.objects.filter(pk=self.note.pk).update(group=self.group))]
        for label, lose, regain in cases:
            with self.subTest(label):
                lose()
                error = self.refused(self.ask(conversation), 403, 'scope_unavailable')
                self.assertEqual(error['message'], 'Ce cours n’est plus accessible : la conversation est en lecture seule.')
                self.assertFalse(self.student_client.get(f'/api/assistant/conversations/{conversation}/').data['can_send'])
                self.assertFalse(self.student_client.get('/api/assistant/conversations/').data['results'][0]['can_send'])
                self.assertEqual(len(self.student_client.get(f'/api/assistant/conversations/{conversation}/messages/').data['results']), 2)
                self.assertEqual(self.student_client.get(f'/api/assistant/conversations/{conversation}/export/').status_code, 200)
                regain()
                self.assertTrue(self.student_client.get(f'/api/assistant/conversations/{conversation}/').data['can_send'])
        self.assertEqual(Message.objects.filter(conversation_id=conversation).count(), 2)

    def test_disabled_assistant_refuses_questions(self):
        conversation = self.start()
        response = self.teacher_client.put(f'/api/assistant/settings/group/{self.group.pk}/', {'enabled': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        error = self.refused(self.ask(conversation), 403, 'assistant_disabled')
        self.assertEqual(error['message'], 'L’assistant est désactivé pour ce cours par votre enseignant.')
        self.refused(self.student_client.post('/api/assistant/conversations/', {'scope_key': self.scope_key}, format='json'), 403, 'assistant_disabled')
        self.assertFalse(self.student_client.get(f'/api/assistant/conversations/{conversation}/').data['can_send'])
        self.assertFalse(self.student_client.get('/api/assistant/conversations/').data['results'][0]['can_send'])
        self.assertFalse(self.student_client.get('/api/assistant/scopes/').data['results'][0]['enabled'])
        self.assertEqual(Message.objects.count(), 0)

    def test_follow_up_questions_reuse_the_previous_question_and_history(self):
        conversation = self.start()
        self.answered(conversation)
        calls = []
        def answer(system, contents, schema, **options):
            calls.append(contents); return model_answer('Parce qu’elle mesure une longueur [S1].')
        with patch('assistant.services.generate_answer', side_effect=answer):
            data = self.answered(conversation, 'Et pourquoi ?')
        self.assertEqual((data['answer']['status'], data['answer']['citations'][0]['chapter_title'], data['quota']['used']), ('COMPLETE', 'Définition', 2))
        contents = calls[0]
        self.assertEqual([c['role'] for c in contents], ['user', 'model', 'user'])
        self.assertEqual(contents[0]['parts'][0]['text'], IN_SCOPE)
        self.assertEqual(contents[1]['parts'][0]['text'], f'D’après le cours : {FIRST_SENTENCE}')
        self.assertTrue(contents[2]['parts'][0]['text'].endswith('QUESTION:\nEt pourquoi ?'))
        # Without a previous question, the same words are outside the course.
        self.assertEqual(self.answered(self.start(), 'Et pourquoi ?')['answer']['status'], 'OUT_OF_SCOPE')

    def test_failed_exchanges_are_left_out_of_the_history(self):
        conversation = self.start()
        self.answered(conversation, f'{IN_SCOPE} #erreur')
        calls = []
        with patch('assistant.services.generate_answer', side_effect=lambda system, contents, schema, **o: calls.append(contents) or model_answer()):
            self.answered(conversation, IN_SCOPE)
        self.assertEqual([c['role'] for c in calls[0]], ['user'])

    def test_teacher_mode_choice_reaches_the_prompt(self):
        systems = []
        def answer(system, contents, schema, **options):
            systems.append(system); return model_answer()
        hint = self.start(mode='INDICE')
        with patch('assistant.services.generate_answer', side_effect=answer):
            self.answered(hint)
            AssistantSettings.objects.filter(source_type='group', scope_id=str(self.group.pk)).update(allow_mode_choice=False, default_mode='EXPLICATION')
            self.answered(hint)
        self.assertIn('Mode indice', systems[0]); self.assertIn('Mode explication', systems[1])
        self.assertTrue(systems[0].startswith('Tu es l’assistant pédagogique du cours « Seconde A ».'))

    def test_question_validation(self):
        conversation = self.start()
        cases = [{'content': '   '}, {'content': ''}, {'content': 'x' * 2001}, {'content': 42}, {'content': None}, {}, {'content': 'ok', 'input_mode': 'AUDIO'},
            {'content': 'ok', 'client_id': 'pas-un-uuid'}, {'content': 'ok', 'client_id': str(uuid.uuid4())[:-1]}, {'content': 'ok', 'role': 'ASSISTANT'}]
        for body in cases:
            with self.subTest(body=body):
                response = self.student_client.post(f'/api/assistant/conversations/{conversation}/messages/', body, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertTrue(set(response.data['error']['fields']) & {'content', 'input_mode', 'client_id', 'role'}, response.data)
        self.assertEqual(self.student_client.post(f'/api/assistant/conversations/{conversation}/messages/', ['liste'], format='json').status_code, 400)
        # The limit applies once the surrounding spaces are removed.
        longest = ('vecteur ' * 250).strip()
        data = self.answered(conversation, f'   {longest}   ')
        self.assertEqual(data['question']['content'], longest)
        self.assertEqual((Message.objects.count(), self.quota()['used']), (2, 1))

    def test_note_changes_reach_the_next_answer(self):
        conversation = self.start()
        self.answered(conversation)
        response = self.teacher_client.patch(f'/api/assistant/notes/{self.note.pk}/', {'body': 'La norme d’un vecteur se calcule avec le théorème de Pythagore.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        answer = self.answered(conversation)['answer']
        self.assertEqual(answer['content'], 'D’après le cours : La norme d’un vecteur se calcule avec le théorème de Pythagore. [S1]')

    def test_logs_keep_measurements_but_never_the_question(self):
        conversation = self.start()
        question = 'Comment calculer la norme du vecteur de Léa ?'
        with self.assertLogs('assistant', 'INFO') as logs:
            answer = self.answered(conversation, question)['answer']
        line = next(entry for entry in logs.output if 'assistant answer' in entry)
        self.assertIn(f'message={answer["id"]}', line); self.assertIn('status=COMPLETE', line); self.assertIn('provider=fake', line)
        for private in ('Léa', 'calculer', answer['content'], self.student.email, str(self.student.pk)):
            self.assertNotIn(private, '\n'.join(logs.output))

    def test_conversation_closed_before_the_question_is_saved(self):
        # Another tab archives or trashes the conversation while this request searches the course; or the TTL monitor removes it.
        cases = [(lambda c: Conversation.objects.filter(pk=c).update(status='ARCHIVED'), 409, 'conversation_locked',
                'Cette conversation est archivée : désarchivez-la pour poser une nouvelle question.'),
            (lambda c: services.trash(Conversation.objects.get(pk=c)), 409, 'conversation_locked', 'Cette conversation est dans la corbeille : restaurez-la pour continuer.'),
            (lambda c: Conversation.objects.filter(pk=c).delete(), 404, 'not_found', 'Conversation introuvable.')]
        for close, status, code, message in cases:
            conversation, search = self.start(), services.retrieve
            def closing(*args):
                close(conversation); return search(*args)
            with self.subTest(message=message), patch('assistant.services.retrieve', side_effect=closing):
                self.assertEqual(self.refused(self.ask(conversation), status, code)['message'], message)
            # Nothing was saved, so nothing escapes the purge, and the question is not counted.
            self.assertEqual((Message.objects.filter(conversation_id=conversation).count(), Conversation.objects.filter(pk=conversation, message_count__gt=0).exists()), (0, False))
        self.assertEqual((self.quota()['used'], remaining('assistant-global', 'global', 400, DAY)['used']), (0, 0))

    def test_conversation_trashed_while_answering_purges_the_answer_too(self):
        conversation = self.start()
        def answer(*args, **kwargs):
            services.trash(Conversation.objects.get(pk=conversation)); return model_answer()
        with patch('assistant.services.generate_answer', side_effect=answer):
            data = self.answered(conversation)
        purge_at = Conversation.objects.get(pk=conversation).purge_at
        self.assertIsNotNone(purge_at)
        self.assertEqual(set(Message.objects.filter(conversation_id=conversation).values_list('purge_at', flat=True)), {purge_at})
        self.assertEqual((data['conversation']['status'], data['conversation']['can_send']), ('DELETED', False))


class AntiCheatTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.quiz = Quiz.objects.create(title='Contrôle sur les vecteurs', description='Dix minutes.', teacher=self.teacher, learning_group=self.group,
            duration_minutes=10, max_attempts=3, status='PUBLISHED')
        self.conversation = self.start()

    def attempt(self, number=1, student=None, group=None, **fields):
        return Attempt.objects.create(student=student or self.student, quiz=self.quiz, learning_group=group or self.group, number=number,
            quiz_title=self.quiz.title, total_points=4, **fields)

    def test_a_running_timed_quiz_suspends_the_assistant(self):
        now = timezone.now()
        self.attempt(started_at=now - timedelta(minutes=2), deadline=now + timedelta(minutes=8))
        error = self.refused(self.ask(self.conversation), 409, 'quiz_in_progress')
        self.assertEqual(error['message'], 'Terminez d’abord votre quiz en cours : l’assistant est suspendu pendant une évaluation.')
        self.assertEqual((Message.objects.count(), remaining('assistant-question', f'{self.student.pk}:group:{self.group.pk}', 30, DAY)['used']), (0, 0))
        # The teacher may lift the rule, and never blocks their own preview.
        self.assertEqual(self.ask(self.start(client=self.teacher_client), client=self.teacher_client).status_code, 201)
        self.teacher_client.put(f'/api/assistant/settings/group/{self.group.pk}/', {'block_during_quiz': False}, format='json')
        self.assertEqual(self.ask(self.conversation).status_code, 201)

    def test_expiry_is_lazy_so_the_deadline_decides(self):
        now = timezone.now()
        attempt = self.attempt(started_at=now - timedelta(minutes=5), deadline=now + timedelta(minutes=5))
        self.refused(self.ask(self.conversation), 409, 'quiz_in_progress')
        # Nobody opened the quiz again: the attempt is still IN_PROGRESS after its deadline.
        with patch('assistant.services.timezone.now', return_value=now + timedelta(minutes=6)):
            self.assertEqual(self.ask(self.conversation).status_code, 201)
        attempt.refresh_from_db(); self.assertEqual(attempt.status, 'IN_PROGRESS')
        Attempt.objects.filter(pk=attempt.pk).update(deadline=now - timedelta(seconds=1))
        self.assertEqual(self.ask(self.conversation).status_code, 201)

    def test_untimed_quiz_locks_for_a_limited_window(self):
        now = timezone.now()
        attempt = self.attempt(started_at=now - timedelta(hours=2), deadline=None)
        self.refused(self.ask(self.conversation), 409, 'quiz_in_progress')
        with self.settings(ASSISTANT_QUIZ_LOCK_HOURS=1.5): self.assertEqual(self.ask(self.conversation).status_code, 201)
        Attempt.objects.filter(pk=attempt.pk).update(started_at=now - timedelta(hours=3, minutes=1))
        self.assertEqual(self.ask(self.conversation).status_code, 201)

    def test_finished_or_unrelated_attempts_do_not_lock(self):
        now = timezone.now()
        other_quiz = Quiz.objects.create(title='Autre', description='Autre groupe.', teacher=self.other_teacher, learning_group=self.other_group, status='PUBLISHED')
        Attempt.objects.create(student=self.student, quiz=other_quiz, learning_group=self.other_group, number=1, quiz_title='Autre', total_points=1,
            started_at=now, deadline=now + timedelta(minutes=30))
        self.attempt(1, status='SUBMITTED', started_at=now, deadline=now + timedelta(minutes=8), ended_at=now)
        self.attempt(2, status='EXPIRED', started_at=now, deadline=now + timedelta(minutes=8))
        self.attempt(1, student=self.other_student, started_at=now, deadline=now + timedelta(minutes=8))
        self.assertEqual(self.ask(self.conversation).status_code, 201)
