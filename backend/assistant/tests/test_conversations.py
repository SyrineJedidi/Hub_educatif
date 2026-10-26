from datetime import timedelta
from unittest.mock import patch
from bson import ObjectId
from django.db import connection
from django.utils import timezone
from classrooms.models import Enrollment, LearningGroup
from assistant.models import AnswerFeedback, AssistantSettings, Citation, Conversation, Message
from assistant.services import auto_title
from .base import IN_SCOPE, AssistantTestCase


class ConversationTests(AssistantTestCase):
    def change(self, conversation_id, body, client=None):
        return (client or self.student_client).patch(f'/api/assistant/conversations/{conversation_id}/', body, format='json')

    def create(self, body, client=None):
        return (client or self.student_client).post('/api/assistant/conversations/', body, format='json')

    def test_new_conversation_takes_the_scope_defaults(self):
        response = self.create({'scope_key': f'group:{str(self.group.pk).upper()}'})
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertEqual(data, {'id': data['id'], 'source_type': 'group', 'scope_id': str(self.group.pk), 'scope_key': self.scope_key, 'scope_title': 'Seconde A',
            'title': 'Nouvelle conversation', 'mode': 'EXPLICATION', 'mode_label': 'Explication', 'status': 'ACTIVE', 'status_label': 'Active', 'pinned': False,
            'message_count': 0, 'last_message_at': data['last_message_at'], 'created_at': data['created_at'], 'purge_at': None, 'can_send': True})
        row = Conversation.objects.get(pk=data['id'])
        self.assertEqual((row.owner_id, row.title_is_custom, row.deleted_at), (self.student.pk, False, None))
        AssistantSettings.objects.filter(source_type='group', scope_id=str(self.group.pk)).update(default_mode='INDICE')
        self.assertEqual(self.create({'scope_key': self.scope_key}).data['mode'], 'INDICE')

    def test_title_and_mode_chosen_by_the_student(self):
        data = self.create({'scope_key': self.scope_key, 'title': '  Révisions du contrôle  ', 'mode': 'INDICE'}).data
        self.assertEqual((data['title'], data['mode'], data['mode_label']), ('Révisions du contrôle', 'INDICE', 'Indice'))
        self.assertTrue(Conversation.objects.get(pk=data['id']).title_is_custom)
        # A custom title survives the first answer.
        self.assertEqual(self.answered(data['id'])['conversation']['title'], 'Révisions du contrôle')

    def test_locked_mode(self):
        AssistantSettings.objects.create(source_type='group', scope_id=str(self.group.pk), scope_title='Seconde A', allow_mode_choice=False)
        response = self.create({'scope_key': self.scope_key, 'mode': 'INDICE'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['fields'], {'mode': ['Votre enseignant a fixé le mode de l’assistant pour ce cours.']})
        conversation = self.create({'scope_key': self.scope_key, 'mode': 'EXPLICATION'}).data['id']
        response = self.change(conversation, {'mode': 'INDICE'})
        self.assertEqual(response.status_code, 400); self.assertIn('mode', response.data['error']['fields'])
        self.assertEqual(self.change(conversation, {'mode': 'EXPLICATION'}).status_code, 200)
        AssistantSettings.objects.filter(source_type='group').update(allow_mode_choice=True)
        data = self.change(conversation, {'mode': 'INDICE'}).data
        self.assertEqual((data['mode'], data['mode_label']), ('INDICE', 'Indice'))

    def test_invalid_creations(self):
        empty = LearningGroup.objects.create(name='Atelier', code='ATELIER', teacher=self.teacher, level='Seconde', academic_year='2026')
        Enrollment.objects.create(student=self.student, group=empty, starts_at=timezone.now() - timedelta(days=1))
        cases = [({}, 'scope_key'), ({'scope_key': 'group:zz'}, 'scope_key'), ({'scope_key': 123}, 'scope_key'), ({'scope_key': f'GROUP:{self.group.pk}'}, 'scope_key'),
            ({'scope_key': f'video:{self.group.pk}'}, 'scope_key'), ({'scope_key': self.other_scope_key}, 'scope_key'), ({'scope_key': f'group:{empty.pk}'}, 'scope_key'),
            ({'scope_key': f'group:{ObjectId()}'}, 'scope_key'), ({'scope_key': self.scope_key, 'title': 'x' * 121}, 'title'),
            ({'scope_key': self.scope_key, 'title': '   '}, 'title'), ({'scope_key': self.scope_key, 'mode': 'AUTRE'}, 'mode'),
            ({'scope_key': self.scope_key, 'owner': str(self.other_student.pk)}, 'owner'), ({'scope_key': self.scope_key, 'status': 'ARCHIVED'}, 'status')]
        for body, field in cases:
            with self.subTest(body=body):
                response = self.create(body)
                self.assertEqual(response.status_code, 400, response.data); self.assertIn(field, response.data['error']['fields'])
        self.assertEqual(self.create({'scope_key': self.other_scope_key}).data['error']['fields'], {'scope_key': ['Sélectionnez un cours disponible.']})
        self.assertEqual(self.create(['liste']).status_code, 400)
        self.assertEqual(Conversation.objects.count(), 0)
        # The teacher may try the assistant on a group that has no note yet.
        self.assertEqual(self.create({'scope_key': f'group:{empty.pk}'}, self.teacher_client).status_code, 201)

    def test_rename(self):
        conversation = self.start()
        response = self.change(conversation, {'title': '  Mes révisions  '})
        self.assertEqual((response.status_code, response.data['title']), (200, 'Mes révisions'))
        self.assertTrue(Conversation.objects.get(pk=conversation).title_is_custom)
        self.assertEqual(self.answered(conversation)['conversation']['title'], 'Mes révisions')
        for title in ('', '   ', 'x' * 121, 12):
            with self.subTest(title=title): self.assertEqual(self.change(conversation, {'title': title}).status_code, 400)
        for body in ({'message_count': 0}, {'owner': str(self.other_student.pk)}, ['liste']):
            with self.subTest(body=body): self.assertEqual(self.change(conversation, body).status_code, 400)
        self.assertEqual(self.change(conversation, {}).data['title'], 'Mes révisions')

    def test_first_answer_names_the_conversation(self):
        conversation = self.start()
        question = 'Comment calculer le coefficient directeur d’une droite à partir de deux points ?'
        self.assertEqual(self.answered(conversation, question)['conversation']['title'], 'Comment calculer le coefficient directeur d’une droite à…')
        self.assertEqual(self.answered(conversation)['conversation']['title'], 'Comment calculer le coefficient directeur d’une droite à…')

    def test_auto_title_cuts_on_a_word(self):
        self.assertEqual(auto_title('  Une   question \n courte ? '), 'Une question courte ?')
        self.assertEqual(auto_title('x' * 60), 'x' * 60)
        self.assertEqual(auto_title('x' * 80), 'x' * 60 + '…')
        self.assertEqual(auto_title('a' * 55 + ', ' + 'b' * 10), 'a' * 55 + '…')
        self.assertTrue(all(len(auto_title(text)) <= 61 for text in ('mot ' * 40, 'a' * 200, IN_SCOPE * 3)))

    def test_at_most_five_pinned_conversations(self):
        ids = [self.start() for _ in range(6)]
        for conversation in ids[:5]: self.assertTrue(self.change(conversation, {'pinned': True}).data['pinned'])
        response = self.change(ids[5], {'pinned': True})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['fields'], {'pinned': ['Vous pouvez épingler au plus 5 conversations.']})
        self.assertEqual(self.change(ids[0], {'pinned': True}).status_code, 200)
        self.assertEqual(self.change(ids[0], {'pinned': False}).data['pinned'], False)
        self.assertEqual(self.change(ids[5], {'pinned': True}).status_code, 200)
        # Archived conversations stay pinned and count; trashed ones are unpinned.
        self.assertTrue(self.change(ids[1], {'status': 'ARCHIVED'}).data['pinned'])
        self.assertEqual(self.change(ids[0], {'pinned': True}).status_code, 400)
        self.assertFalse(self.student_client.delete(f'/api/assistant/conversations/{ids[2]}/').data['pinned'])
        self.assertEqual(self.change(ids[0], {'pinned': True}).status_code, 200)
        for value in ('true', 1, None):
            with self.subTest(value=value): self.assertEqual(self.change(ids[0], {'pinned': value}).status_code, 400)
        # Another student's pins do not count.
        Conversation.objects.filter(owner=self.student).update(pinned=True)
        self.enrol_classmate()
        self.assertEqual(self.change(self.start(client=self.classmate), {'pinned': True}, self.classmate).status_code, 200)

    def enrol_classmate(self):
        Enrollment.objects.create(student=self.other_student, group=self.group, starts_at=timezone.now() - timedelta(hours=1))
        self.classmate = self.as_user(self.other_student)

    def test_archive_and_unarchive(self):
        conversation = self.start()
        data = self.change(conversation, {'status': 'ARCHIVED'}).data
        self.assertEqual((data['status'], data['status_label'], data['can_send']), ('ARCHIVED', 'Archivée', False))
        self.assertEqual(self.change(conversation, {'title': 'Archivée et renommée', 'pinned': True}).status_code, 200)
        self.assertEqual(self.change(conversation, {'status': 'DELETED'}).status_code, 400)
        self.assertEqual(self.change(conversation, {'status': 'archived'}).status_code, 400)
        data = self.change(conversation, {'status': 'ACTIVE'}).data
        self.assertEqual((data['status'], data['can_send']), ('ACTIVE', True))
        self.assertEqual(self.ask(conversation).status_code, 201)

    def test_trash_restore_and_purge_dates(self):
        conversation = self.start()
        answer = self.answered(conversation)['answer']
        self.student_client.put(f'/api/assistant/messages/{answer["id"]}/feedback/', {'rating': 'UP'}, format='json')
        self.change(conversation, {'pinned': True})
        response = self.student_client.delete(f'/api/assistant/conversations/{conversation}/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['status'], response.data['status_label'], response.data['pinned'], response.data['can_send']), ('DELETED', 'Corbeille', False, False))
        row = Conversation.objects.get(pk=conversation)
        self.assertEqual(row.purge_at - row.deleted_at, timedelta(days=30))
        self.assertLess(abs(row.deleted_at - timezone.now()), timedelta(minutes=1))
        self.assertEqual(response.data['purge_at'], row.purge_at)
        self.assertEqual(set(Message.objects.filter(conversation_id=conversation).values_list('purge_at', flat=True)), {row.purge_at})
        self.assertEqual(AnswerFeedback.objects.get().purge_at, row.purge_at)
        self.assertEqual(self.student_client.get('/api/assistant/conversations/').data['count'], 0)
        self.assertEqual([c['id'] for c in self.student_client.get('/api/assistant/conversations/?status=deleted').data['results']], [conversation])
        # In the trash: readable, but closed to every change except restore.
        self.assertEqual(self.student_client.get(f'/api/assistant/conversations/{conversation}/messages/').status_code, 200)
        error = self.refused(self.change(conversation, {'title': 'Renommée'}), 409, 'conversation_locked')
        self.assertEqual(error['message'], 'Cette conversation est dans la corbeille : restaurez-la pour continuer.')
        self.refused(self.student_client.put(f'/api/assistant/messages/{answer["id"]}/feedback/', {'rating': 'UP'}, format='json'), 409, 'conversation_locked')
        again = self.student_client.delete(f'/api/assistant/conversations/{conversation}/')
        self.assertEqual((again.status_code, Conversation.objects.get(pk=conversation).deleted_at), (200, row.deleted_at))
        response = self.student_client.post(f'/api/assistant/conversations/{conversation}/restore/', {}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['status'], response.data['purge_at'], response.data['can_send']), ('ACTIVE', None, True))
        row.refresh_from_db(); self.assertEqual((row.deleted_at, row.purge_at), (None, None))
        self.assertEqual(set(Message.objects.filter(conversation_id=conversation).values_list('purge_at', flat=True)), {None})
        self.assertIsNone(AnswerFeedback.objects.get().purge_at)
        error = self.refused(self.student_client.post(f'/api/assistant/conversations/{conversation}/restore/', {}, format='json'), 409, 'conversation_not_deleted')
        self.assertEqual(error['message'], 'Cette conversation n’est pas dans la corbeille.')

    def test_expired_trash_is_gone_before_the_ttl_runs(self):
        conversation = self.start()
        answer = self.answered(conversation)['answer']
        self.student_client.delete(f'/api/assistant/conversations/{conversation}/')
        Conversation.objects.filter(pk=conversation).update(purge_at=timezone.now() - timedelta(seconds=1))
        for response in (self.student_client.get(f'/api/assistant/conversations/{conversation}/'), self.student_client.get(f'/api/assistant/conversations/{conversation}/messages/'),
                self.student_client.get(f'/api/assistant/conversations/{conversation}/export/'),
                self.student_client.post(f'/api/assistant/conversations/{conversation}/restore/', {}, format='json'),
                self.student_client.put(f'/api/assistant/messages/{answer["id"]}/feedback/', {'rating': 'UP'}, format='json')):
            self.refused(response, 404, 'not_found')
        self.assertEqual(self.student_client.get('/api/assistant/conversations/?status=deleted').data['count'], 0)

    def test_trash_expiry_is_a_real_ttl_index(self):
        connection.ensure_connection()
        for name in ('assistant_conversation', 'assistant_message', 'assistant_answerfeedback'):
            with self.subTest(collection=name):
                index = connection.database[name].index_information()['purge_expiration']
                self.assertEqual((index['key'], index['expireAfterSeconds']), ([('purge_at', 1)], 0))


class HistoryTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        def row(title, hours, **fields):
            conversation = self.conversation_row(title=title, last_message_at=now - timedelta(hours=hours), **fields)
            Conversation.objects.filter(pk=conversation.pk).update(created_at=now - timedelta(days=hours))
            return str(conversation.pk)
        self.vectors = row('Vecteurs et normes', 1)
        self.chance = row('Probabilités', 3, pinned=True)
        self.recent = row('Révisions', 0.5)
        self.energy = row('Énergie', 2, group=self.other_group)
        self.archived = row('Ancienne', 4, status='ARCHIVED')
        self.trashed = row('Jetée', 5, status='DELETED', deleted_at=now, purge_at=now + timedelta(days=29))
        self.expired = row('Expirée', 6, status='DELETED', deleted_at=now - timedelta(days=31), purge_at=now - timedelta(days=1))
        self.message_row(Conversation.objects.get(pk=self.vectors), content='Comment utiliser le théorème de PYTHAGORE ?')
        self.conversation_row(owner=self.other_student, group=self.other_group, title='Vecteurs du voisin')

    def ids(self, query='', status=200):
        response = self.student_client.get(f'/api/assistant/conversations/{query}')
        self.assertEqual(response.status_code, status, response.data)
        return [c['id'] for c in response.data['results']] if status == 200 else response.data['error']

    def test_active_conversations_pinned_first_then_most_recent(self):
        self.assertEqual(self.ids(), [self.chance, self.recent, self.vectors, self.energy])
        listed = self.student_client.get('/api/assistant/conversations/').data
        self.assertEqual((listed['count'], listed['page'], listed['page_size']), (4, 1, 20))
        # The student left no trace in the other group: that conversation can no longer receive questions.
        self.assertEqual({c['title']: c['can_send'] for c in listed['results']}, {'Probabilités': True, 'Révisions': True, 'Vecteurs et normes': True, 'Énergie': False})

    def test_search_in_titles_and_messages(self):
        self.assertEqual(self.ids('?q=VECTEURS'), [self.vectors])
        self.assertEqual(self.ids('?q=pythagore'), [self.vectors])
        self.assertEqual(self.ids('?q=  probabilités  '), [self.chance])
        for query in ('(', '.*', '[a-z]+', '$where', 'voisin'):
            with self.subTest(query=query): self.assertEqual(self.ids(f'?q={query}'), [])
        # Searches are cut to 100 characters.
        long_title = str(self.conversation_row(title='a' * 100).pk)
        self.assertEqual(self.ids('?q=' + 'a' * 100 + 'b' * 50), [long_title])
        self.assertEqual(self.ids('?q=Ancienne&status=archived'), [self.archived])

    def test_scope_filter(self):
        self.assertEqual(self.ids(f'?scope={self.other_scope_key}'), [self.energy])
        self.assertEqual(self.ids(f'?scope=group:{str(self.group.pk).upper()}'), [self.chance, self.recent, self.vectors])
        self.assertEqual(self.ids(f'?scope=course:{self.group.pk}'), [])
        for value in ('group:zz', 'group', str(self.group.pk)):
            with self.subTest(value=value): self.assertIn('scope', self.ids(f'?scope={value}', 400)['fields'])

    def test_status_tabs(self):
        self.assertEqual(self.ids('?status=active'), self.ids())
        self.assertEqual(self.ids('?status=archived'), [self.archived])
        self.assertEqual(self.ids('?status=deleted'), [self.trashed])
        for value in ('ACTIVE', 'all', 'expired'):
            with self.subTest(value=value): self.assertEqual(self.ids(f'?status={value}', 400)['fields'], {'status': ['Sélectionnez une valeur autorisée.']})

    def test_pinned_filter(self):
        self.assertEqual(self.ids('?pinned=true'), [self.chance])
        self.assertEqual(self.ids('?pinned=false'), [self.recent, self.vectors, self.energy])
        for value in ('yes', 'True', '1'):
            with self.subTest(value=value): self.assertEqual(self.ids(f'?pinned={value}', 400)['fields'], {'pinned': ['Envoyez true ou false.']})

    def test_orderings(self):
        self.assertEqual(self.ids('?ordering=-created_at'), [self.recent, self.vectors, self.energy, self.chance])
        self.assertEqual(self.ids('?ordering=title'), [self.chance, self.recent, self.vectors, self.energy])
        self.assertEqual(self.ids('?ordering=-last_message_at'), self.ids())
        for value in ('owner', '-pinned', 'created_at'):
            with self.subTest(value=value): self.assertIn('ordering', self.ids(f'?ordering={value}', 400)['fields'])

    def test_pages_of_twenty(self):
        for number in range(21): self.conversation_row(title=f'Série {number:02d}')
        first = self.student_client.get('/api/assistant/conversations/?ordering=title').data
        second = self.student_client.get('/api/assistant/conversations/?ordering=title&page=2').data
        self.assertEqual((first['count'], len(first['results']), len(second['results']), second['page']), (25, 20, 5, 2))
        self.assertFalse({c['id'] for c in first['results']} & {c['id'] for c in second['results']})
        self.assertEqual(self.student_client.get('/api/assistant/conversations/?page=0').data['page'], 1)
        self.assertIn('page', self.ids('?page=deux', 400)['fields'])

    def test_each_user_lists_only_their_own(self):
        self.assertEqual([c['title'] for c in self.as_user(self.other_student).get('/api/assistant/conversations/').data['results']], ['Vecteurs du voisin'])
        self.assertEqual(self.teacher_client.get('/api/assistant/conversations/').data['count'], 0)


class MessagePageTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = self.conversation_row(title='Longue conversation')
        start = timezone.now() - timedelta(hours=1)
        self.messages = []
        for number in range(7):
            role = 'USER' if number % 2 == 0 else 'ASSISTANT'
            message = self.message_row(self.conversation, role, content=f'Message {number}', latency_ms=120 if role == 'ASSISTANT' else None,
                reply_to=self.messages[-1] if role == 'ASSISTANT' else None)
            Message.objects.filter(pk=message.pk).update(created_at=start + timedelta(minutes=number))
            self.messages.append(message)
        self.ids = [str(m.pk) for m in self.messages]

    def page(self, query='', status=200):
        response = self.student_client.get(f'/api/assistant/conversations/{self.conversation.pk}/messages/{query}')
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def test_newest_page_in_reading_order(self):
        data = self.page()
        self.assertEqual(([m['id'] for m in data['results']], data['has_more']), (self.ids, False))
        data = self.page('?limit=3')
        self.assertEqual(([m['id'] for m in data['results']], data['has_more']), (self.ids[4:], True))
        data = self.page(f'?limit=3&before={self.ids[4]}')
        self.assertEqual(([m['id'] for m in data['results']], data['has_more']), (self.ids[1:4], True))
        data = self.page(f'?limit=3&before={self.ids[1]}')
        self.assertEqual(([m['id'] for m in data['results']], data['has_more']), (self.ids[:1], False))

    def test_messages_written_in_the_same_millisecond_keep_their_order(self):
        Message.objects.filter(pk__in=[m.pk for m in self.messages]).update(created_at=timezone.now())
        self.assertEqual([m['id'] for m in self.page()['results']], self.ids)
        self.assertEqual([m['id'] for m in self.page(f'?before={self.ids[3]}')['results']], self.ids[:3])

    def test_message_shape_and_feedback_only_on_answers(self):
        AnswerFeedback.objects.create(message=self.messages[1], conversation=self.conversation, student=self.student, source_type='group',
            scope_id=str(self.group.pk), rating='DOWN', reasons=['UNCLEAR'], comment='Trop court.')
        results = self.page()['results']
        self.assertEqual((results[0]['latency_ms'], results[0]['feedback'], results[1]['latency_ms']), (None, None, 120))
        self.assertEqual(results[1]['feedback'], {'rating': 'DOWN', 'reasons': ['UNCLEAR'], 'comment': 'Trop court.', 'shared_with_teacher': False,
            'status': 'NEW', 'status_label': 'Nouveau', 'teacher_note': ''})
        self.assertEqual(results[1]['reply_to_id'], self.ids[0]); self.assertIsNone(results[3]['feedback'])

    def test_invalid_pages(self):
        for value in ('0', '101', '-1', 'dix', '2.5'):
            with self.subTest(limit=value):
                self.assertEqual(self.page(f'?limit={value}', 400)['error']['fields'], {'limit': ['Saisissez un entier entre 1 et 100.']})
        self.assertEqual(len(self.page('?limit=100')['results']), 7)
        other = self.message_row(self.conversation_row(title='Autre'), content='Ailleurs')
        for value in ('pas-un-id', str(ObjectId()), str(other.pk)):
            with self.subTest(before=value): self.assertEqual(self.page(f'?before={value}', 404)['error']['code'], 'not_found')


class ExportTests(AssistantTestCase):
    def test_markdown_lists_questions_answers_and_sources(self):
        conversation = self.conversation_row(title='Révisions', mode='INDICE')
        created = timezone.now().replace(microsecond=0) - timedelta(days=2)
        Conversation.objects.filter(pk=conversation.pk).update(created_at=created)
        def exchange(question, **answer):
            asked = self.message_row(conversation, content=question)
            if answer: self.message_row(conversation, 'ASSISTANT', reply_to=asked, **answer)
        citations = [Citation(number=1, source_kind='NOTE', source_id='a' * 24, source_title='Les vecteurs', chapter_title='Définition', excerpt='…', score=3.0),
            Citation(number=2, source_kind='RESOURCE', source_id='b' * 24, source_title='Cours PDF', chapter_title='Cours PDF', page=4, excerpt='…', score=2.0),
            Citation(number=3, source_kind='RESOURCE', source_id='c' * 24, source_title='Vidéo', chapter_title='', start_seconds=83.4, url='/x?t=83', excerpt='…', score=1.5)]
        exchange('Qu’est-ce que la norme ?', content='La norme est une longueur [S1][S2][S3].', citations=citations, follow_ups=['Une relance à omettre ?'])
        exchange('La capitale ?', content='Je ne trouve pas cette information dans le cours.', status='OUT_OF_SCOPE')
        exchange('Et alors ?', content='Le service d’IA est momentanément indisponible.', status='FAILED', error_code='unavailable')
        exchange('Une dernière ?', content='Réponse sans source.', unsourced=True)
        exchange('Sans réponse ?')
        exported = timezone.now().replace(microsecond=0)
        with patch('assistant.services.timezone.now', return_value=exported):
            response = self.student_client.get(f'/api/assistant/conversations/{conversation.pk}/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response['Content-Type'], response['Content-Disposition'], response['Cache-Control']),
            ('text/markdown; charset=utf-8', f'attachment; filename="conversation-{conversation.pk}.md"', 'private, no-store'))
        local = lambda value: timezone.localtime(value).strftime('%d/%m/%Y à %H:%M')
        self.assertEqual(response.content.decode('utf-8'), '\n'.join([
            '# Révisions', '', '- Cours : Seconde A', '- Mode : Indice', f'- Créée le {local(created)}', f'- Exportée le {local(exported)}', '',
            '## Question 1', '', 'Qu’est-ce que la norme ?', '', '### Réponse', '', 'La norme est une longueur [S1][S2][S3].', '',
            'Sources :', '', '1. Les vecteurs — Définition', '2. Cours PDF — page 4', '3. Vidéo — à 01:23', '',
            '## Question 2', '', 'La capitale ?', '', '### Réponse (Hors cours)', '', 'Je ne trouve pas cette information dans le cours.', '',
            '## Question 3', '', 'Et alors ?', '', '### Réponse (Échec)', '', 'Le service d’IA est momentanément indisponible.', '',
            '## Question 4', '', 'Une dernière ?', '', '### Réponse', '', 'Réponse sans source.', '', '_Réponse non sourcée._', '',
            '## Question 5', '', 'Sans réponse ?', '', '_Aucune réponse enregistrée._']) + '\n')

    def test_export_of_a_real_exchange(self):
        conversation = self.start()
        self.answered(conversation)
        text = self.student_client.get(f'/api/assistant/conversations/{conversation}/export/').content.decode('utf-8')
        self.assertTrue(text.startswith(f'# {IN_SCOPE}\n'))
        self.assertIn('1. Les vecteurs — Définition', text); self.assertNotIn('Peux-tu donner un exemple', text)
