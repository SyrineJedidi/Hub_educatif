import json
import secrets
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import Enrollment, LearningGroup
from assistant.models import AnswerFeedback, Message, TeacherNote, ValidatedAnswer

DATASET = json.loads((Path(__file__).resolve().parents[1] / 'evaluation' / 'demo_dataset.json').read_text(encoding='utf-8'))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], ASSISTANT_LLM_PROVIDER='fake', WHISPER_PROVIDER='fake')
class AssistantSmokeTests(TransactionTestCase):
    def setUp(self):
        password = secrets.token_urlsafe(24)
        self.admin = User.objects.create_superuser('admin@assistant.test', password, first_name='Admin', last_name='Nexora')
        self.teacher = User.objects.create_user('teacher@assistant.test', password, role='TEACHER', first_name='Prof', last_name='Un')
        self.student = User.objects.create_user('student@assistant.test', password, first_name='Élève', last_name='Un')
        self.group = LearningGroup.objects.create(name='Seconde A', code='SECA', teacher=self.teacher, level='Seconde', academic_year='2026')
        Enrollment.objects.create(student=self.student, group=self.group, starts_at=timezone.now() - timedelta(days=1))
        self.teacher_client, self.student_client = self.as_user(self.teacher), self.as_user(self.student)
        for note in DATASET['notes']:
            r = self.teacher_client.post('/api/assistant/notes/', {'group_id': str(self.group.pk), **note}, format='json'); self.assertEqual(r.status_code, 201, r.data)
        self.scope_key = f'group:{self.group.pk}'

    def as_user(self, user):
        c = APIClient(); c.force_login(user); return c

    def conversation(self):
        r = self.student_client.post('/api/assistant/conversations/', {'scope_key': self.scope_key}, format='json'); self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def ask(self, conversation_id, content, **extra):
        return self.student_client.post(f'/api/assistant/conversations/{conversation_id}/messages/', {'content': content, **extra}, format='json')

    def test_sourced_answer_feedback_review_and_validated_answer_reused(self):
        r = self.student_client.get('/api/assistant/scopes/'); self.assertEqual(r.status_code, 200)
        scope = next(s for s in r.data['results'] if s['key'] == self.scope_key)
        self.assertEqual(scope['quota'], {'limit': 30, 'used': 0, 'remaining': 30}); self.assertEqual(scope['teacher']['last_name'], 'Un')
        conversation_id = self.conversation(); client_id = str(uuid.uuid4())
        question = 'Comment calculer le coefficient directeur d’une droite à partir de deux points ?'
        r = self.ask(conversation_id, question, client_id=client_id); self.assertEqual(r.status_code, 201, r.data)
        answer = r.data['answer']
        self.assertEqual(answer['status'], 'COMPLETE'); self.assertFalse(answer['unsourced']); self.assertIn('[S1]', answer['content'])
        self.assertEqual(answer['citations'][0]['source_title'], 'Les fonctions affines'); self.assertEqual(answer['citations'][0]['number'], 1)
        self.assertEqual(r.data['quota'], {'limit': 30, 'used': 1, 'remaining': 29})
        self.assertEqual(r.data['conversation']['title'], 'Comment calculer le coefficient directeur d’une droite à…')
        self.assertTrue(r.data['conversation']['can_send']); self.assertEqual(r.data['conversation']['message_count'], 2)
        replay = self.ask(conversation_id, question, client_id=client_id); self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(replay.data['answer']['id'], answer['id']); self.assertEqual(replay.data['quota']['used'], 1)
        r = self.student_client.put(f'/api/assistant/messages/{answer["id"]}/feedback/', {'rating': 'DOWN', 'reasons': ['INCOMPLETE'],
            'comment': 'Il manque un exemple.', 'shared_with_teacher': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data); self.assertEqual(r.data['feedback']['status'], 'NEW')
        r = self.teacher_client.get('/api/assistant/reviews/?status=NEW'); self.assertEqual(r.status_code, 200); self.assertEqual(r.data['count'], 1)
        review = r.data['results'][0]
        self.assertEqual(review['question'], question); self.assertEqual(review['reason_labels'], ['Incomplète'])
        self.assertNotIn('Élève', json.dumps(review, default=str)); self.assertNotIn(str(self.student.pk), json.dumps(review, default=str))
        correction = 'On choisit deux points A et B de la droite puis a = (yB − yA) / (xB − xA). Exemple : A(0 ; 1) et B(2 ; 5) donnent a = 2.'
        r = self.teacher_client.patch(f'/api/assistant/reviews/{review["id"]}/', {'action': 'CORRECT', 'correction': correction}, format='json')
        self.assertEqual(r.status_code, 200, r.data); self.assertEqual(r.data['status'], 'CORRECTED')
        self.assertEqual(ValidatedAnswer.objects.get().answer, correction)
        again = self.teacher_client.patch(f'/api/assistant/reviews/{review["id"]}/', {'action': 'DISMISS'}, format='json')
        self.assertEqual(again.status_code, 409); self.assertEqual(again.data['error']['code'], 'already_reviewed')
        r = self.ask(conversation_id, 'Comment calculer le coefficient directeur avec deux points ?'); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['answer']['citations'][0]['source_kind'], 'VALIDATED')
        r = self.student_client.get(f'/api/assistant/conversations/{conversation_id}/messages/'); self.assertEqual(r.status_code, 200)
        first = next(m for m in r.data['results'] if m['id'] == answer['id'])
        self.assertEqual(first['feedback']['status'], 'CORRECTED'); self.assertEqual(first['feedback']['teacher_note'], correction)
        self.assertEqual([m['role'] for m in r.data['results']], ['USER', 'ASSISTANT', 'USER', 'ASSISTANT']); self.assertFalse(r.data['has_more'])

    def test_out_of_scope_question_skips_the_model_and_the_quota(self):
        conversation_id = self.conversation()
        with patch('assistant.services.generate_answer', side_effect=AssertionError('the model must not be called')):
            r = self.ask(conversation_id, 'Quelle est la capitale de l’Australie ?')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['answer']['status'], 'OUT_OF_SCOPE'); self.assertEqual(r.data['answer']['citations'], [])
        self.assertEqual(r.data['quota']['used'], 0)
        stored = Message.objects.get(pk=r.data['answer']['id']); self.assertEqual(stored.provider, ''); self.assertIsNone(stored.top_score)

    def test_voice_question_is_transcribed_but_not_sent(self):
        audio = SimpleUploadedFile('question.webm', b'\x1a\x45\xdf\xa3' + b'\x00' * 256, content_type='audio/webm')
        r = self.student_client.post('/api/assistant/transcriptions/', {'audio': audio, 'language': 'fr'}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['text'].startswith('Transcription de démonstration')); self.assertEqual(r.data['language'], 'fr')
        self.assertEqual(r.data['duration_seconds'], 15.0); self.assertEqual(Message.objects.count(), 0)
        fake = SimpleUploadedFile('question.webm', b'<svg></svg>' * 10, content_type='audio/webm')
        r = self.student_client.post('/api/assistant/transcriptions/', {'audio': fake}, format='multipart')
        self.assertEqual(r.status_code, 400); self.assertIn('audio', r.data['error']['fields'])

    def test_lifecycle_and_manager_endpoints_answer(self):
        conversation_id = self.conversation()
        r = self.ask(conversation_id, 'Quels sont les principaux gaz à effet de serre ?'); self.assertEqual(r.status_code, 201, r.data)
        answer_id = r.data['answer']['id']
        r = self.student_client.get(f'/api/assistant/conversations/{conversation_id}/export/')
        self.assertEqual(r.status_code, 200); self.assertEqual(r['Content-Type'], 'text/markdown; charset=utf-8')
        self.assertIn('Le dioxyde de carbone et l’effet de serre', r.content.decode())
        r = self.student_client.patch(f'/api/assistant/conversations/{conversation_id}/', {'status': 'ARCHIVED', 'pinned': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data); self.assertFalse(r.data['can_send'])
        r = self.ask(conversation_id, 'Et le méthane ?'); self.assertEqual(r.status_code, 409); self.assertEqual(r.data['error']['code'], 'conversation_locked')
        r = self.student_client.delete(f'/api/assistant/conversations/{conversation_id}/'); self.assertEqual(r.status_code, 200); self.assertEqual(r.data['status'], 'DELETED')
        self.assertIsNotNone(Message.objects.get(pk=answer_id).purge_at)
        self.assertEqual(self.student_client.get('/api/assistant/conversations/?status=deleted').data['count'], 1)
        r = self.student_client.post(f'/api/assistant/conversations/{conversation_id}/restore/', {}, format='json'); self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'ACTIVE'); self.assertIsNone(Message.objects.get(pk=answer_id).purge_at)
        r = self.student_client.put(f'/api/assistant/messages/{answer_id}/feedback/', {'rating': 'UP'}, format='json'); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(AnswerFeedback.objects.get().rating, 'UP')
        r = self.teacher_client.get('/api/assistant/settings/'); self.assertEqual(r.status_code, 200); self.assertEqual(r.data['results'][0]['key'], self.scope_key)
        r = self.teacher_client.put(f'/api/assistant/settings/group/{self.group.pk}/', {'enabled': False, 'suggested_questions': ['Qu’est-ce qu’une fonction affine ?']}, format='json')
        self.assertEqual(r.status_code, 200, r.data); self.assertFalse(r.data['enabled'])
        r = self.ask(conversation_id, 'Et le méthane ?'); self.assertEqual(r.status_code, 403); self.assertEqual(r.data['error']['code'], 'assistant_disabled')
        r = self.teacher_client.get(f'/api/assistant/insights/group/{self.group.pk}/'); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['questions'], 1); self.assertEqual(r.data['satisfaction'], 1.0); self.assertEqual(len(r.data['questions_per_day']), 30)
        r = self.teacher_client.get(f'/api/assistant/insights/group/{self.group.pk}/?format=csv')
        self.assertEqual(r.status_code, 200); self.assertTrue(r.content.decode('utf-8').startswith('﻿'))
        r = self.as_user(self.admin).get('/api/assistant/admin/usage/'); self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['totals']['questions'], 1); self.assertEqual(r.data['providers']['llm']['provider'], 'fake')
        self.assertEqual(self.as_user(self.admin).get('/api/assistant/scopes/').status_code, 403)
        self.assertEqual(self.student_client.get('/api/assistant/notes/').status_code, 403)
        spare = LearningGroup.objects.create(name='Sans élève', code='SPARE', teacher=self.teacher, level='Seconde', academic_year='2026')
        TeacherNote.objects.create(group=spare, teacher=self.teacher, title='Brouillon', body='Une note suffit à garder le groupe.')
        r = self.as_user(self.admin).delete(f'/api/groups/{spare.pk}/'); self.assertEqual(r.status_code, 400)
