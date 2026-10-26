from bson import ObjectId
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from assistant.models import AnswerFeedback, AssistantSettings, Conversation, Message, TeacherNote
from .base import IN_SCOPE, AssistantTestCase
from .test_voice import OGG

CHAT = 'L’assistant pédagogique est réservé aux étudiants et aux enseignants.'
MANAGER = 'Le suivi de l’assistant est réservé aux enseignants et à l’administrateur.'


class PermissionTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = self.start()
        data = self.answered(self.conversation)
        self.question_id, self.answer_id = data['question']['id'], data['answer']['id']
        self.student_client.put(f'/api/assistant/messages/{self.answer_id}/feedback/', {'rating': 'DOWN', 'reasons': ['UNCLEAR'], 'shared_with_teacher': True}, format='json')
        self.review_id = str(AnswerFeedback.objects.get().pk)

    def chat_routes(self):
        conversation, answer = self.conversation, self.answer_id
        return [('get', 'scopes/', None), ('get', 'conversations/', None), ('post', 'conversations/', {'scope_key': self.scope_key}),
            ('get', f'conversations/{conversation}/', None), ('patch', f'conversations/{conversation}/', {'title': 'Volée'}),
            ('delete', f'conversations/{conversation}/', None), ('post', f'conversations/{conversation}/restore/', {}),
            ('get', f'conversations/{conversation}/messages/', None), ('post', f'conversations/{conversation}/messages/', {'content': IN_SCOPE}),
            ('get', f'conversations/{conversation}/export/', None), ('put', f'messages/{answer}/feedback/', {'rating': 'UP'}),
            ('delete', f'messages/{answer}/feedback/', None), ('post', 'transcriptions/', {})]

    def manager_routes(self):
        note, group, review = self.note.pk, self.group.pk, self.review_id
        return [('get', 'notes/', None), ('post', 'notes/', {'group_id': str(group), 'title': 'T', 'body': 'B'}), ('get', f'notes/{note}/', None),
            ('patch', f'notes/{note}/', {'title': 'Volée'}), ('delete', f'notes/{note}/', None), ('get', 'settings/', None),
            ('get', f'settings/group/{group}/', None), ('put', f'settings/group/{group}/', {'enabled': False}), ('get', f'insights/group/{group}/', None),
            ('get', 'reviews/', None), ('get', f'reviews/{review}/', None), ('patch', f'reviews/{review}/', {'action': 'DISMISS'})]

    def call(self, client, method, path, body):
        url = f'/api/assistant/{path}'
        return getattr(client, method)(url, body, format='json') if body is not None else getattr(client, method)(url)

    def snapshot(self):
        return (list(Conversation.objects.order_by('id').values_list('id', 'title', 'status', 'pinned', 'message_count', 'purge_at')),
            list(Message.objects.order_by('id').values_list('id', 'content', 'status', 'purge_at')),
            list(AnswerFeedback.objects.order_by('id').values_list('id', 'rating', 'status', 'shared_with_teacher', 'teacher_note')),
            list(TeacherNote.objects.order_by('id').values_list('id', 'title', 'body', 'version')),
            list(AssistantSettings.objects.order_by('id').values_list('id', 'enabled', 'daily_question_limit')))

    def test_anonymous_and_inactive_accounts_get_401(self):
        teacher, student = self.as_user(self.teacher), self.as_user(self.student)
        self.teacher.is_active = False; self.teacher.save(); self.student.is_active = False; self.student.save()
        before = self.snapshot()
        routes = self.chat_routes() + self.manager_routes() + [('get', 'admin/usage/', None)]
        for client in (APIClient(), teacher, student):
            for method, path, body in routes:
                with self.subTest(method=method, path=path):
                    self.refused(self.call(client, method, path, body), 401, 'not_authenticated')
        self.assertEqual(self.snapshot(), before)

    def test_administrator_manages_but_never_chats(self):
        admin = self.as_user(self.admin)
        before = self.snapshot()
        for method, path, body in self.chat_routes():
            with self.subTest(method=method, path=path):
                self.assertEqual(self.refused(self.call(admin, method, path, body), 403, 'permission_denied')['message'], CHAT)
        self.assertEqual(self.snapshot(), before)
        for method, path, body in self.manager_routes() + [('get', 'admin/usage/', None)]:
            if method == 'get':
                with self.subTest(path=path): self.assertEqual(self.call(admin, method, path, body).status_code, 200)

    def test_students_cannot_reach_management(self):
        before = self.snapshot()
        for method, path, body in self.manager_routes():
            with self.subTest(method=method, path=path):
                self.assertEqual(self.refused(self.call(self.student_client, method, path, body), 403, 'permission_denied')['message'], MANAGER)
        for client in (self.student_client, self.teacher_client):
            self.assertEqual(self.refused(self.call(client, 'get', 'admin/usage/', None), 403, 'permission_denied')['message'],
                'Cette action est réservée aux administrateurs.')
        self.assertEqual(self.snapshot(), before)

    def test_nobody_else_reads_or_changes_a_conversation(self):
        before = self.snapshot()
        # Teachers never read their students' conversations either.
        for user in (self.other_student, self.teacher):
            client = self.as_user(user)
            for method, path, body in self.chat_routes()[3:-1]:
                with self.subTest(user=user.email, method=method, path=path):
                    self.refused(self.call(client, method, path, body), 404, 'not_found')
            self.assertEqual(client.get(f'/api/assistant/conversations/?q=norme&scope={self.scope_key}').data['count'], 0)
        self.assertEqual(self.snapshot(), before)
        # A message of someone else's conversation is no anchor for paging either way.
        neighbour = self.as_user(self.other_student)
        own = self.start(client=neighbour, scope_key=self.other_scope_key)
        own_question = self.answered(own, 'Que vaut l’énergie cinétique ?', client=neighbour)['question']['id']
        self.refused(neighbour.get(f'/api/assistant/conversations/{own}/messages/?before={self.question_id}'), 404, 'not_found')
        self.refused(self.student_client.get(f'/api/assistant/conversations/{self.conversation}/messages/?before={own_question}'), 404, 'not_found')

    def test_a_trashed_conversation_cannot_be_restored_by_someone_else(self):
        self.student_client.delete(f'/api/assistant/conversations/{self.conversation}/')
        self.refused(self.as_user(self.other_student).post(f'/api/assistant/conversations/{self.conversation}/restore/', {}, format='json'), 404, 'not_found')
        self.assertEqual(Conversation.objects.get(pk=self.conversation).status, 'DELETED')

    def test_another_teacher_finds_nothing_to_manage(self):
        before = self.snapshot()
        other = self.as_user(self.other_teacher)
        for method, path, body in self.manager_routes():
            if path in ('notes/', 'settings/', 'reviews/'): continue
            with self.subTest(method=method, path=path): self.refused(self.call(other, method, path, body), 404, 'not_found')
        self.refused(other.get(f'/api/assistant/notes/?group={self.group.pk}'), 404, 'not_found')
        response = other.post('/api/assistant/notes/', {'group_id': str(self.group.pk), 'title': 'Intrusion', 'body': 'Texte.'}, format='json')
        self.assertEqual(response.data['error']['fields'], {'group_id': ['Sélectionnez un de vos groupes.']})
        self.assertEqual(other.get(f'/api/assistant/reviews/?scope={self.scope_key}').data['count'], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn(self.scope_key, [s['key'] for s in other.get('/api/assistant/settings/').data['results']])

    def test_unknown_ids_are_not_found(self):
        for value in ('pas-un-id', str(ObjectId()), '0' * 23):
            for client, path in ((self.student_client, f'conversations/{value}/'), (self.student_client, f'conversations/{value}/messages/'),
                    (self.student_client, f'conversations/{value}/export/'), (self.teacher_client, f'notes/{value}/'), (self.teacher_client, f'reviews/{value}/'),
                    (self.teacher_client, f'settings/group/{value}/'), (self.teacher_client, f'insights/group/{value}/')):
                with self.subTest(path=path): self.refused(self.call(client, 'get', path, None), 404, 'not_found')
            with self.subTest(value=value):
                self.refused(self.call(self.student_client, 'put', f'messages/{value}/feedback/', {'rating': 'UP'}), 404, 'not_found')
                self.refused(self.call(self.student_client, 'post', f'conversations/{value}/restore/', {}), 404, 'not_found')


class CsrfTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = self.start()
        answer = self.answered(self.conversation)['answer']['id']
        self.student_client.put(f'/api/assistant/messages/{answer}/feedback/', {'rating': 'DOWN', 'reasons': ['UNCLEAR'], 'shared_with_teacher': True}, format='json')
        self.review = AnswerFeedback.objects.get().pk
        self.tokens = {}

    def guarded(self, user):
        client = APIClient(enforce_csrf_checks=True); client.force_login(user)
        self.tokens[id(client)] = client.get('/api/csrf/').data['csrfToken']
        return client

    def send(self, client, method, path, body, **extra):
        url = f'/api/assistant/{path}'
        if callable(body): return client.post(url, body(), format='multipart', **extra)
        if body is None: return getattr(client, method)(url, **extra)
        return getattr(client, method)(url, body, format='json', **extra)

    def write(self, client, method, path, body, status):
        """Refused without the token, then applied once with it."""
        refused = self.send(client, method, path, body)
        self.assertEqual(refused.status_code, 403, getattr(refused, 'data', refused))
        self.assertEqual(refused.json()['error'], {'code': 'csrf_failed', 'message': 'Protection CSRF : rechargez la page puis réessayez.', 'fields': {}})
        response = self.send(client, method, path, body, HTTP_X_CSRFTOKEN=self.tokens[id(client)])
        self.assertEqual(response.status_code, status, getattr(response, 'data', response))
        return response

    def test_every_write_needs_the_token(self):
        student, teacher = self.guarded(self.student), self.guarded(self.teacher)
        self.write(student, 'patch', f'conversations/{self.conversation}/', {'title': 'Renommée'}, 200)
        answer = self.write(student, 'post', f'conversations/{self.conversation}/messages/', {'content': IN_SCOPE}, 201).data['answer']['id']
        self.write(student, 'put', f'messages/{answer}/feedback/', {'rating': 'UP'}, 200)
        self.write(student, 'delete', f'messages/{answer}/feedback/', None, 204)
        self.write(student, 'delete', f'conversations/{self.conversation}/', None, 200)
        self.write(student, 'post', f'conversations/{self.conversation}/restore/', {}, 200)
        self.write(student, 'post', 'conversations/', {'scope_key': self.scope_key}, 201)
        self.write(student, 'post', 'transcriptions/', lambda: {'audio': SimpleUploadedFile('question.ogg', OGG, content_type='audio/ogg')}, 200)
        self.write(teacher, 'patch', f'reviews/{self.review}/', {'action': 'DISMISS'}, 200)
        note = self.write(teacher, 'post', 'notes/', {'group_id': str(self.group.pk), 'title': 'Repères', 'body': 'Une origine et deux axes.'}, 201).data['id']
        self.write(teacher, 'patch', f'notes/{note}/', {'title': 'Repères du plan'}, 200)
        self.write(teacher, 'put', f'settings/group/{self.group.pk}/', {'welcome_message': 'Bonjour'}, 200)
        self.write(teacher, 'delete', f'notes/{note}/', None, 204)
        conversation = Conversation.objects.get(pk=self.conversation)
        self.assertEqual((conversation.title, conversation.status, conversation.message_count), ('Renommée', 'ACTIVE', 4))
        self.assertEqual((Conversation.objects.count(), TeacherNote.objects.count(), AnswerFeedback.objects.get().status), (2, 2, 'DISMISSED'))
        self.assertEqual(AssistantSettings.objects.get(scope_id=str(self.group.pk)).welcome_message, 'Bonjour')
