from unittest.mock import patch
from bson import ObjectId
from django.db import IntegrityError
from classrooms.models import LearningGroup
from assistant.models import AssistantSettings, Conversation, TeacherNote
from .base import ENERGY, IN_SCOPE, AssistantTestCase, without_courses

NOTE_KEYS = {'id', 'group', 'title', 'body', 'version', 'teacher', 'created_at', 'updated_at'}
SETTINGS_KEYS = {'source_type', 'scope_id', 'key', 'title', 'teacher', 'enabled', 'default_mode', 'allow_mode_choice', 'daily_question_limit',
    'effective_daily_limit', 'max_daily_question_limit', 'block_during_quiz', 'suggested_questions', 'welcome_message', 'updated_at'}


class NoteTests(AssistantTestCase):
    def create(self, body, client=None):
        return (client or self.teacher_client).post('/api/assistant/notes/', body, format='json')

    def edit(self, note_id, body, client=None):
        return (client or self.teacher_client).patch(f'/api/assistant/notes/{note_id}/', body, format='json')

    def payload(self, **fields):
        return {'group_id': str(self.group.pk), 'title': 'Repères', 'body': 'Un repère est formé d’une origine et de deux axes gradués.', **fields}

    def test_teacher_writes_notes_for_their_group(self):
        response = self.create(self.payload(group_id=str(self.group.pk).upper(), title='  Repères  ', body='\n  Un repère est formé d’une origine.  \n'))
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertEqual(set(data), NOTE_KEYS)
        self.assertEqual({k: data[k] for k in ('group', 'title', 'body', 'version', 'teacher')}, {
            'group': {'id': str(self.group.pk), 'name': 'Seconde A', 'code': 'SECA'}, 'title': 'Repères', 'body': 'Un repère est formé d’une origine.',
            'version': 1, 'teacher': {'id': str(self.teacher.pk), 'first_name': 'Claire', 'last_name': 'Martin'}})
        detail = self.teacher_client.get(f'/api/assistant/notes/{data["id"]}/').data
        self.assertEqual({k: v for k, v in detail.items() if not k.endswith('_at')}, {k: v for k, v in data.items() if not k.endswith('_at')})
        self.assertEqual(TeacherNote.objects.get(pk=data['id']).teacher_id, self.teacher.pk)

    def test_administrator_writes_on_behalf_of_the_group_teacher(self):
        data = self.create(self.payload(group_id=str(self.other_group.pk)), self.as_user(self.admin)).data
        self.assertEqual((data['group']['code'], data['teacher']['id']), ('TERMB', str(self.other_teacher.pk)))
        self.assertEqual(self.edit(data['id'], {'title': 'Repères (admin)'}, self.as_user(self.admin)).data['version'], 2)

    def test_only_the_group_teacher_writes(self):
        for client, group in ((self.as_user(self.other_teacher), self.group), (self.teacher_client, self.other_group)):
            with self.subTest(group=group.code):
                response = self.create(self.payload(group_id=str(group.pk)), client)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data['error']['fields'], {'group_id': ['Sélectionnez un de vos groupes.']})
        self.assertEqual(TeacherNote.objects.count(), 2)

    def test_archived_group_takes_no_new_note(self):
        LearningGroup.objects.filter(pk=self.group.pk).update(archived=True)
        for response in (self.create(self.payload()), self.edit(self.note_id(), {'title': 'Nouveau titre'})):
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(response.data['error']['fields'], {'group_id': ['Le groupe est archivé.']})
        self.assertEqual(TeacherNote.objects.get(pk=self.note.pk).title, 'Les vecteurs')
        self.assertEqual(self.teacher_client.delete(f'/api/assistant/notes/{self.note.pk}/').status_code, 204)

    def note_id(self):
        return str(self.note.pk)

    def test_validation(self):
        cases = [({'title': '  '}, 'title'), ({'title': 'x' * 121}, 'title'), ({'body': ' \n '}, 'body'), ({'body': 'x' * 20001}, 'body'),
            ({'group_id': 'pas-un-id'}, 'group_id'), ({'group_id': str(ObjectId())}, 'group_id'), ({'group_id': None}, 'group_id'),
            ({'title': 3}, 'title'), ({'version': 7}, 'version'), ({'teacher_id': str(self.other_teacher.pk)}, 'teacher_id')]
        for change, field in cases:
            with self.subTest(change=change):
                response = self.create(self.payload(**change))
                self.assertEqual(response.status_code, 400, response.data); self.assertIn(field, response.data['error']['fields'])
        missing = self.payload(); del missing['body']
        self.assertIn('body', self.create(missing).data['error']['fields'])
        self.assertEqual(self.create(['note']).status_code, 400)
        self.assertEqual(TeacherNote.objects.count(), 2)
        self.assertEqual(self.create(self.payload(title='x' * 120, body='x' * 20000)).status_code, 201)

    def test_lists_are_limited_to_managed_groups(self):
        self.create(self.payload())
        titles = lambda query='', client=None: [n['title'] for n in (client or self.teacher_client).get(f'/api/assistant/notes/{query}').data['results']]
        self.assertEqual(sorted(titles()), ['Les vecteurs', 'Repères'])
        self.assertEqual(titles(client=self.as_user(self.other_teacher)), ['L’énergie'])
        self.assertEqual(sorted(titles(client=self.as_user(self.admin))), ['Les vecteurs', 'L’énergie', 'Repères'])
        self.assertEqual(titles(f'?group={self.other_group.pk}', self.as_user(self.admin)), ['L’énergie'])
        self.assertEqual(sorted(titles(f'?group={self.group.pk}')), ['Les vecteurs', 'Repères'])
        self.assertEqual(titles('?q=REP'), ['Repères'])
        for query in (f'?group={self.other_group.pk}', '?group=pas-un-id', f'?group={ObjectId()}'):
            with self.subTest(query=query): self.refused(self.teacher_client.get(f'/api/assistant/notes/{query}'), 404, 'not_found')
        data = self.teacher_client.get('/api/assistant/notes/').data
        self.assertEqual((data['count'], data['page'], data['page_size']), (2, 1, 20))
        self.assertEqual(self.teacher_client.get('/api/assistant/notes/').data['results'][0]['title'], 'Repères')

    def test_version_changes_only_with_the_content(self):
        note = self.note_id()
        self.assertEqual(self.edit(note, {'title': 'Les vecteurs', 'body': TeacherNote.objects.get(pk=note).body}).data['version'], 1)
        self.assertEqual(self.edit(note, {}).data['version'], 1)
        self.assertEqual(self.edit(note, {'body': 'Un vecteur a une norme.'}).data['version'], 2)
        self.assertEqual(self.edit(note, {'title': 'Vecteurs', 'body': 'Un vecteur a une direction.'}).data['version'], 3)
        for body, field in (({'title': ' '}, 'title'), ({'group_id': str(self.other_group.pk)}, 'group_id'), ({'version': 9}, 'version'), ({'body': 'x' * 20001}, 'body')):
            with self.subTest(body=body):
                response = self.edit(note, body)
                self.assertEqual(response.status_code, 400, response.data); self.assertIn(field, response.data['error']['fields'])
        stored = TeacherNote.objects.get(pk=note)
        self.assertEqual((stored.title, stored.body, stored.version, str(stored.group_id)), ('Vecteurs', 'Un vecteur a une direction.', 3, str(self.group.pk)))

    def test_deleted_note_leaves_the_assistant(self):
        TeacherNote.objects.create(group=self.group, teacher=self.teacher, title='L’énergie', body=ENERGY)
        conversation = self.start()
        self.assertEqual(self.answered(conversation)['answer']['status'], 'COMPLETE')
        self.assertEqual(self.teacher_client.delete(f'/api/assistant/notes/{self.note.pk}/').status_code, 204)
        self.assertFalse(TeacherNote.objects.filter(pk=self.note.pk).exists())
        self.assertEqual(self.answered(self.start(), IN_SCOPE)['answer']['status'], 'OUT_OF_SCOPE')
        self.refused(self.teacher_client.get(f'/api/assistant/notes/{self.note.pk}/'), 404, 'not_found')

    def test_notes_follow_the_group_to_its_new_teacher(self):
        self.group.teacher = self.other_teacher; self.group.save()
        self.refused(self.teacher_client.get(f'/api/assistant/notes/{self.note.pk}/'), 404, 'not_found')
        self.refused(self.edit(self.note_id(), {'title': 'Ancien professeur'}), 404, 'not_found')
        data = self.edit(self.note_id(), {'title': 'Nouveau professeur'}, self.as_user(self.other_teacher)).data
        self.assertEqual((data['title'], data['teacher']['id']), ('Nouveau professeur', str(self.other_teacher.pk)))

    def test_group_with_notes_cannot_be_deleted(self):
        admin = self.as_user(self.admin)
        spare = LearningGroup.objects.create(name='Sans élève', code='SPARE', teacher=self.teacher, level='Seconde', academic_year='2026')
        note = self.create(self.payload(group_id=str(spare.pk))).data['id']
        response = admin.delete(f'/api/groups/{spare.pk}/')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertTrue(LearningGroup.objects.filter(pk=spare.pk).exists())
        self.assertEqual(self.teacher_client.delete(f'/api/assistant/notes/{note}/').status_code, 204)
        self.assertEqual(admin.delete(f'/api/groups/{spare.pk}/').status_code, 204)


class SettingsTests(AssistantTestCase):
    def url(self, group=None, source_type='group'):
        return f'/api/assistant/settings/{source_type}/{(group or self.group).pk}/'

    def put(self, body, client=None, group=None):
        return (client or self.teacher_client).put(self.url(group), body, format='json')

    def test_managed_scopes_are_listed_with_their_settings(self):
        LearningGroup.objects.create(name='Atelier', code='ATELIER', teacher=self.teacher, level='Seconde', academic_year='2026')
        LearningGroup.objects.create(name='Ancien', code='OLD', teacher=self.teacher, level='Seconde', academic_year='2025', archived=True)
        keys = lambda client: [s['title'] for s in client.get('/api/assistant/settings/').data['results']]
        self.assertEqual(keys(self.teacher_client), ['Atelier', 'Seconde A'])
        self.assertEqual(keys(self.as_user(self.other_teacher)), ['Terminale B'])
        self.assertEqual(keys(self.as_user(self.admin)), ['Atelier', 'Seconde A', 'Terminale B'])
        item = self.teacher_client.get('/api/assistant/settings/').data['results'][1]
        self.assertEqual(set(item), SETTINGS_KEYS)
        self.assertEqual(item['teacher'], {'id': str(self.teacher.pk), 'first_name': 'Claire', 'last_name': 'Martin'})

    def test_defaults_are_written_on_first_read(self):
        self.assertFalse(AssistantSettings.objects.exists())
        data = self.teacher_client.get(self.url()).data
        self.assertEqual({k: v for k, v in data.items() if k != 'updated_at'}, {'source_type': 'group', 'scope_id': str(self.group.pk), 'key': self.scope_key,
            'title': 'Seconde A', 'teacher': {'id': str(self.teacher.pk), 'first_name': 'Claire', 'last_name': 'Martin'}, 'enabled': True,
            'default_mode': 'EXPLICATION', 'allow_mode_choice': True, 'daily_question_limit': 30, 'effective_daily_limit': 30,
            'max_daily_question_limit': 30, 'block_during_quiz': True, 'suggested_questions': [], 'welcome_message': ''})
        row = AssistantSettings.objects.get()
        self.assertEqual((row.scope_title, row.updated_by_id), ('Seconde A', None))
        # A renamed group refreshes the stored title.
        LearningGroup.objects.filter(pk=self.group.pk).update(name='Seconde A (2026)')
        self.assertEqual(self.teacher_client.get(self.url()).data['title'], 'Seconde A (2026)')
        self.assertEqual(AssistantSettings.objects.get().scope_title, 'Seconde A (2026)')

    def test_partial_update(self):
        response = self.put({'welcome_message': '  Bienvenue : posez vos questions sur le chapitre 3.  '})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['welcome_message'], response.data['enabled'], response.data['daily_question_limit']),
            ('Bienvenue : posez vos questions sur le chapitre 3.', True, 30))
        row = AssistantSettings.objects.get()
        self.assertEqual((row.updated_by_id, row.welcome_message), (self.teacher.pk, 'Bienvenue : posez vos questions sur le chapitre 3.'))
        self.assertIsNotNone(response.data['updated_at'])
        self.assertEqual(self.put({}).data['welcome_message'], 'Bienvenue : posez vos questions sur le chapitre 3.')
        self.assertEqual(self.put({'welcome_message': ''}).data['welcome_message'], '')

    def test_students_see_what_the_teacher_chose(self):
        body = {'enabled': True, 'default_mode': 'INDICE', 'allow_mode_choice': False, 'daily_question_limit': 12, 'block_during_quiz': False,
            'suggested_questions': ['  Qu’est-ce qu’un vecteur ?  ', 'Comment additionner deux vecteurs ?', 'Qu’est-ce qu’un vecteur ?'], 'welcome_message': 'Bonjour !'}
        data = self.put(body).data
        self.assertEqual(data['suggested_questions'], ['Qu’est-ce qu’un vecteur ?', 'Comment additionner deux vecteurs ?'])
        scope = self.student_client.get('/api/assistant/scopes/').data['results'][0]
        self.assertEqual(scope, {'source_type': 'group', 'scope_id': str(self.group.pk), 'key': self.scope_key, 'title': 'Seconde A',
            'teacher': {'id': str(self.teacher.pk), 'first_name': 'Claire', 'last_name': 'Martin'}, 'enabled': True, 'default_mode': 'INDICE',
            'allow_mode_choice': False, 'suggested_questions': ['Qu’est-ce qu’un vecteur ?', 'Comment additionner deux vecteurs ?'],
            'welcome_message': 'Bonjour !', 'quota': {'limit': 12, 'used': 0, 'remaining': 12}})
        self.assertEqual(self.student_client.post('/api/assistant/conversations/', {'scope_key': self.scope_key}, format='json').data['mode'], 'INDICE')

    def test_strict_validation(self):
        cases = [({'enabled': 'true'}, 'enabled'), ({'enabled': 1}, 'enabled'), ({'enabled': None}, 'enabled'), ({'daily_question_limit': 0}, 'daily_question_limit'),
            ({'daily_question_limit': 201}, 'daily_question_limit'), ({'daily_question_limit': 1.5}, 'daily_question_limit'), ({'daily_question_limit': True}, 'daily_question_limit'),
            ({'daily_question_limit': '1e2'}, 'daily_question_limit'), ({'default_mode': 'AUTRE'}, 'default_mode'), ({'allow_mode_choice': 'non'}, 'allow_mode_choice'),
            ({'block_during_quiz': 0}, 'block_during_quiz'), ({'suggested_questions': [f'Question {n} ?' for n in range(6)]}, 'suggested_questions'), ({'suggested_questions': ['  ']}, 'suggested_questions'),
            ({'suggested_questions': ['x' * 201]}, 'suggested_questions'), ({'suggested_questions': 'Une question ?'}, 'suggested_questions'),
            ({'suggested_questions': [3]}, 'suggested_questions'), ({'welcome_message': 'x' * 501}, 'welcome_message'), ({'teacher': str(self.other_teacher.pk)}, 'teacher'),
            ({'scope_title': 'Autre'}, 'scope_title')]
        for body, field in cases:
            with self.subTest(body=body):
                response = self.put(body)
                self.assertEqual(response.status_code, 400, response.data); self.assertIn(field, response.data['error']['fields'])
        self.assertEqual(self.put(['liste']).status_code, 400)
        self.assertEqual(self.put({'suggested_questions': ['Une question ?', 'x' * 201]}).data['error']['fields'], {'suggested_questions': ['Élément 2 : Limitez ce champ à 200 caractères.']})
        self.assertEqual(self.put({'daily_question_limit': '200', 'suggested_questions': [f'Q{n}' for n in range(5)]}).data['daily_question_limit'], 200)
        self.assertFalse(AssistantSettings.objects.exclude(daily_question_limit=200).exists())

    def test_unknown_scopes(self):
        self.assertIn('source_type', self.teacher_client.get(self.url(source_type='video')).data['error']['fields'])
        with without_courses(): self.assertIn('source_type', self.teacher_client.put(self.url(source_type='course'), {}, format='json').data['error']['fields'])
        for client, url in ((self.teacher_client, '/api/assistant/settings/group/pas-un-id/'), (self.teacher_client, f'/api/assistant/settings/group/{ObjectId()}/'),
                (self.teacher_client, self.url(self.other_group)), (self.as_user(self.other_teacher), self.url())):
            with self.subTest(url=url):
                self.refused(client.get(url), 404, 'not_found')
                self.refused(client.put(url, {'enabled': False}, format='json'), 404, 'not_found')
        self.assertFalse(AssistantSettings.objects.filter(enabled=False).exists())

    def test_administrator_manages_every_scope(self):
        data = self.put({'enabled': False}, self.as_user(self.admin), self.other_group).data
        self.assertEqual((data['enabled'], data['teacher']['last_name']), (False, 'Durand'))
        self.assertEqual(AssistantSettings.objects.get(scope_id=str(self.other_group.pk)).updated_by_id, self.admin.pk)

    def test_two_first_readers_share_one_row(self):
        def raced(**lookup):
            # Another request wrote the row between our lookup and our insert.
            AssistantSettings.objects.create(source_type='group', scope_id=str(self.group.pk), scope_title='Ancien nom', daily_question_limit=9)
            raise IntegrityError('E11000 duplicate key')
        with patch.object(AssistantSettings.objects, 'get_or_create', raced):
            data = self.teacher_client.get(self.url()).data
        self.assertEqual((data['daily_question_limit'], data['title']), (9, 'Seconde A'))
        self.assertEqual(list(AssistantSettings.objects.values_list('scope_title', flat=True)), ['Seconde A'])

    def test_a_fixed_mode_applies_to_open_conversations(self):
        hint = self.student_client.post('/api/assistant/conversations/', {'scope_key': self.scope_key, 'mode': 'INDICE'}, format='json').data['id']
        elsewhere = self.conversation_row(owner=self.other_student, group=self.other_group, mode='INDICE')
        self.put({'allow_mode_choice': False})
        detail = self.student_client.get(f'/api/assistant/conversations/{hint}/').data
        self.assertEqual((detail['mode'], detail['mode_label']), ('EXPLICATION', 'Explication'))
        self.assertIn('- Mode : Explication', self.student_client.get(f'/api/assistant/conversations/{hint}/export/').content.decode())
        self.assertEqual(self.student_client.patch(f'/api/assistant/conversations/{hint}/', {'mode': 'EXPLICATION'}, format='json').status_code, 200)
        self.put({'default_mode': 'INDICE'})
        self.assertEqual(self.student_client.get(f'/api/assistant/conversations/{hint}/').data['mode'], 'INDICE')
        # Lifting the rule gives the choice back without changing anything; other scopes never move.
        self.put({'allow_mode_choice': True, 'default_mode': 'EXPLICATION'})
        self.assertEqual(self.student_client.get(f'/api/assistant/conversations/{hint}/').data['mode'], 'INDICE')
        self.assertEqual(Conversation.objects.get(pk=elsewhere.pk).mode, 'INDICE')
