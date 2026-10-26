import json
from unittest.mock import patch
from bson import ObjectId
from django.db import IntegrityError, connection
from django.utils import timezone
from classrooms.models import Enrollment
from assistant.content import NotesProvider
from assistant.indexing import ensure_index
from assistant.models import AnswerFeedback, ValidatedAnswer
from .base import IN_SCOPE, AssistantTestCase
from .test_ask import MESSAGE_KEYS

REVIEW_KEYS = {'id', 'scope_key', 'scope_title', 'question', 'answer', 'rating', 'reasons', 'reason_labels', 'comment', 'status', 'status_label',
    'teacher_note', 'reviewed_at', 'created_at'}


class FeedbackTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = self.start()
        data = self.answered(self.conversation)
        self.question_id, self.answer_id = data['question']['id'], data['answer']['id']

    def put(self, body, message_id=None, client=None):
        return (client or self.student_client).put(f'/api/assistant/messages/{message_id or self.answer_id}/feedback/', body, format='json')

    def delete(self, message_id=None, client=None):
        return (client or self.student_client).delete(f'/api/assistant/messages/{message_id or self.answer_id}/feedback/')

    def test_upsert_keeps_one_feedback_per_answer(self):
        response = self.put({'rating': 'DOWN', 'reasons': ['INCORRECT', 'BAD_SOURCE', 'INCORRECT'], 'comment': '  La source ne parle pas de ça.  ', 'shared_with_teacher': True})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((set(response.data), response.data['id']), (MESSAGE_KEYS, self.answer_id))
        self.assertEqual(response.data['feedback'], {'rating': 'DOWN', 'reasons': ['INCORRECT', 'BAD_SOURCE'], 'comment': 'La source ne parle pas de ça.',
            'shared_with_teacher': True, 'status': 'NEW', 'status_label': 'Nouveau', 'teacher_note': ''})
        stored = AnswerFeedback.objects.get()
        self.assertEqual((str(stored.message_id), str(stored.conversation_id), stored.student_id, stored.source_type, stored.scope_id, stored.purge_at),
            (self.answer_id, self.conversation, self.student.pk, 'group', str(self.group.pk), None))
        # A second PUT replaces the whole feedback: reasons only go with « À améliorer ».
        response = self.put({'rating': 'UP', 'reasons': ['UNCLEAR']})
        self.assertEqual(response.data['feedback'], {'rating': 'UP', 'reasons': [], 'comment': '', 'shared_with_teacher': False,
            'status': 'NEW', 'status_label': 'Nouveau', 'teacher_note': ''})
        self.assertEqual(AnswerFeedback.objects.get().pk, stored.pk)
        listed = self.student_client.get(f'/api/assistant/conversations/{self.conversation}/messages/').data['results']
        self.assertEqual([m['feedback'] and m['feedback']['rating'] for m in listed], [None, 'UP'])

    def test_invalid_feedback(self):
        cases = [({'rating': 'DOWN'}, 'reasons'), ({'rating': 'DOWN', 'reasons': []}, 'reasons'), ({}, 'rating'), ({'rating': 'MEH'}, 'rating'),
            ({'rating': None}, 'rating'), ({'rating': 'DOWN', 'reasons': ['FAUX']}, 'reasons'), ({'rating': 'DOWN', 'reasons': 'INCORRECT'}, 'reasons'),
            ({'rating': 'UP', 'comment': 'x' * 501}, 'comment'), ({'rating': 'UP', 'shared_with_teacher': 'oui'}, 'shared_with_teacher'),
            ({'rating': 'UP', 'status': 'CONFIRMED'}, 'status'), ({'rating': 'UP', 'teacher_note': 'Validé'}, 'teacher_note')]
        for body, field in cases:
            with self.subTest(body=body):
                response = self.put(body)
                self.assertEqual(response.status_code, 400, response.data); self.assertIn(field, response.data['error']['fields'])
        self.assertEqual(self.put({'rating': 'DOWN'}).data['error']['fields'], {'reasons': ['Indiquez au moins une raison.']})
        self.assertEqual(self.put({'rating': 'DOWN', 'reasons': ['INCORRECT', 'FAUX']}).data['error']['fields'], {'reasons': ['Élément 2 : Sélectionnez une valeur autorisée.']})
        self.assertEqual(self.put(['UP']).status_code, 400)
        self.assertFalse(AnswerFeedback.objects.exists())
        self.assertEqual(self.put({'rating': 'UP', 'comment': ''}).status_code, 200)

    def test_only_answers_of_own_conversations(self):
        error = self.refused(self.put({'rating': 'UP'}, self.question_id), 400, 'invalid')
        self.assertEqual(error['message'], 'Seules les réponses de l’assistant peuvent être évaluées.')
        for client in (self.as_user(self.other_student), self.teacher_client):
            with self.subTest(client=client):
                self.refused(self.put({'rating': 'UP'}, client=client), 404, 'not_found')
                self.refused(self.delete(client=client), 404, 'not_found')
        for message_id in (str(ObjectId()), 'pas-un-id'):
            with self.subTest(message_id=message_id): self.refused(self.put({'rating': 'UP'}, message_id), 404, 'not_found')
        self.assertFalse(AnswerFeedback.objects.exists())

    def test_failed_answers_cannot_be_rated_but_refusals_can(self):
        failed = self.answered(self.conversation, f'{IN_SCOPE} #erreur')['answer']['id']
        error = self.refused(self.put({'rating': 'DOWN', 'reasons': ['OTHER']}, failed), 400, 'invalid')
        self.assertEqual(error['message'], 'Une réponse en échec ne peut pas être évaluée : posez de nouveau la question.')
        for content in (f'{IN_SCOPE} #bloque', f'{IN_SCOPE} #horscours'):
            with self.subTest(content=content):
                answer = self.answered(self.conversation, content)['answer']['id']
                self.assertEqual(self.put({'rating': 'DOWN', 'reasons': ['HORS_SUJET']}, answer).status_code, 200)

    def test_delete_only_while_new(self):
        error = self.refused(self.delete(), 404, 'not_found')
        self.assertEqual(error['message'], 'Aucun retour sur cette réponse.')
        self.put({'rating': 'UP'})
        self.assertEqual(self.delete().status_code, 204)
        self.assertFalse(AnswerFeedback.objects.exists())
        self.put({'rating': 'DOWN', 'reasons': ['UNCLEAR'], 'shared_with_teacher': True})
        review = AnswerFeedback.objects.get()
        self.assertEqual(self.teacher_client.patch(f'/api/assistant/reviews/{review.pk}/', {'action': 'CONFIRM'}, format='json').status_code, 200)
        error = self.refused(self.delete(), 409, 'already_reviewed')
        self.assertEqual(error['message'], 'Ce retour a déjà été traité par l’enseignant : il ne peut plus être modifié.')
        self.refused(self.put({'rating': 'UP'}), 409, 'already_reviewed')
        review.refresh_from_db(); self.assertEqual((review.rating, review.status), ('DOWN', 'CONFIRMED'))

    def test_feedback_can_be_withdrawn_from_the_trash(self):
        self.put({'rating': 'UP'})
        self.student_client.delete(f'/api/assistant/conversations/{self.conversation}/')
        self.assertIsNotNone(AnswerFeedback.objects.get().purge_at)
        self.assertEqual(self.delete().status_code, 204)

    def test_two_first_feedbacks_at_once_end_as_one(self):
        create = AnswerFeedback.objects.create
        def raced(**fields):
            # Another tab saved its feedback between our lookup and our insert.
            create(**{**fields, 'rating': 'UP', 'reasons': [], 'comment': 'Autre onglet'})
            raise IntegrityError('E11000 duplicate key')
        with patch.object(AnswerFeedback.objects, 'create', raced):
            response = self.put({'rating': 'DOWN', 'reasons': ['UNCLEAR'], 'comment': 'Celui-ci'})
        self.assertEqual(response.status_code, 200, response.data)
        stored = AnswerFeedback.objects.get()
        self.assertEqual((stored.rating, stored.reasons, stored.comment), ('DOWN', ['UNCLEAR'], 'Celui-ci'))


class ReviewTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.conversation = self.start()
        data = self.answered(self.conversation)
        self.question, self.answer = data['question'], data['answer']
        self.feedback(self.answer['id'], {'rating': 'DOWN', 'reasons': ['INCOMPLETE', 'UNCLEAR'], 'comment': 'Il manque un exemple.', 'shared_with_teacher': True})
        self.review = AnswerFeedback.objects.get(message_id=self.answer['id'])
        # A private feedback never reaches the teacher.
        private = self.answered(self.conversation, 'Comment additionner deux vecteurs ?')['answer']['id']
        self.feedback(private, {'rating': 'DOWN', 'reasons': ['INCORRECT'], 'comment': 'Faux.'})
        self.private = AnswerFeedback.objects.get(message_id=private)
        neighbour = self.as_user(self.other_student)
        other = self.start(client=neighbour, scope_key=self.other_scope_key)
        answer = self.answered(other, 'Que vaut l’énergie cinétique ?', client=neighbour)['answer']['id']
        self.feedback(answer, {'rating': 'UP', 'shared_with_teacher': True}, neighbour)
        self.other_review = AnswerFeedback.objects.get(message_id=answer)

    def feedback(self, message_id, body, client=None):
        response = (client or self.student_client).put(f'/api/assistant/messages/{message_id}/feedback/', body, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def queue(self, query='', client=None, status=200):
        response = (client or self.teacher_client).get(f'/api/assistant/reviews/{query}')
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def act(self, body, review=None, client=None):
        return (client or self.teacher_client).patch(f'/api/assistant/reviews/{(review or self.review).pk}/', body, format='json')

    def test_queue_shows_the_answer_but_never_the_student(self):
        data = self.queue()
        self.assertEqual((data['count'], data['page'], data['page_size']), (1, 1, 20))
        review = data['results'][0]
        self.assertEqual(set(review), REVIEW_KEYS); self.assertEqual(set(review['answer']), {'content', 'citations', 'created_at'})
        self.assertEqual({k: review[k] for k in ('id', 'scope_key', 'scope_title', 'question', 'rating', 'reasons', 'reason_labels', 'comment', 'status', 'status_label', 'teacher_note', 'reviewed_at')},
            {'id': str(self.review.pk), 'scope_key': self.scope_key, 'scope_title': 'Seconde A', 'question': IN_SCOPE, 'rating': 'DOWN', 'reasons': ['INCOMPLETE', 'UNCLEAR'],
             'reason_labels': ['Incomplète', 'Pas claire'], 'comment': 'Il manque un exemple.', 'status': 'NEW', 'status_label': 'Nouveau', 'teacher_note': '', 'reviewed_at': None})
        self.assertEqual((review['answer']['content'], review['answer']['citations']), (self.answer['content'], self.answer['citations']))
        detail = self.teacher_client.get(f'/api/assistant/reviews/{self.review.pk}/').data
        self.assertEqual(detail, review)
        for payload in (review, detail, self.as_user(self.admin).get('/api/assistant/reviews/').data):
            text = json.dumps(payload, default=str, ensure_ascii=False)
            for private in (self.student.first_name, self.student.last_name, self.student.email, str(self.student.pk), self.conversation,
                    self.question['id'], self.answer['id'], self.other_student.last_name, str(self.other_student.pk)):
                self.assertNotIn(private, text)

    def test_each_teacher_sees_the_scopes_they_teach(self):
        self.assertEqual([r['id'] for r in self.queue(client=self.as_user(self.other_teacher))['results']], [str(self.other_review.pk)])
        self.assertEqual({r['id'] for r in self.queue(client=self.as_user(self.admin))['results']}, {str(self.review.pk), str(self.other_review.pk)})
        for review, client in ((self.other_review, self.teacher_client), (self.review, self.as_user(self.other_teacher)), (self.private, self.teacher_client),
                (self.private, self.as_user(self.admin))):
            with self.subTest(review=review.pk):
                self.refused(client.get(f'/api/assistant/reviews/{review.pk}/'), 404, 'not_found')
                self.refused(self.act({'action': 'CONFIRM'}, review, client), 404, 'not_found')
        for value in ('pas-un-id', str(ObjectId())):
            with self.subTest(value=value): self.refused(self.teacher_client.get(f'/api/assistant/reviews/{value}/'), 404, 'not_found')
        self.assertEqual(AnswerFeedback.objects.filter(status='NEW').count(), 3)

    def test_filters_and_pages(self):
        admin = self.as_user(self.admin)
        self.assertEqual(self.queue('?status=NEW')['count'], 1); self.assertEqual(self.queue('?status=CONFIRMED')['count'], 0)
        self.assertEqual(self.queue('?reason=UNCLEAR')['count'], 1); self.assertEqual(self.queue('?reason=BAD_SOURCE')['count'], 0)
        self.assertEqual([r['id'] for r in self.queue(f'?scope={self.other_scope_key}', admin)['results']], [str(self.other_review.pk)])
        self.assertEqual(self.queue(f'?scope={self.other_scope_key}')['count'], 0)
        for query, field in (('?status=OPEN', 'status'), ('?reason=FAUX', 'reason'), ('?scope=group', 'scope'), ('?page=deux', 'page')):
            with self.subTest(query=query): self.assertIn(field, self.queue(query, status=400)['error']['fields'])
        AnswerFeedback.objects.filter(pk=self.review.pk).update(status='DISMISSED')
        self.assertEqual(self.queue('?status=DISMISSED')['count'], 1)
        for number in range(21):
            conversation = self.conversation_row()
            answer = self.message_row(conversation, 'ASSISTANT', content=f'Réponse {number}', reply_to=self.message_row(conversation, content=f'Question {number}'))
            AnswerFeedback.objects.create(message=answer, conversation=conversation, student=self.student, source_type='group', scope_id=str(self.group.pk),
                rating='UP', shared_with_teacher=True)
        first, second = self.queue(), self.queue('?page=2')
        self.assertEqual((first['count'], len(first['results']), len(second['results'])), (22, 20, 2))
        self.assertFalse({r['id'] for r in first['results']} & {r['id'] for r in second['results']})

    def test_student_withdraws_a_shared_feedback_while_new(self):
        self.feedback(self.answer['id'], {'rating': 'DOWN', 'reasons': ['INCOMPLETE'], 'shared_with_teacher': False})
        self.assertEqual(self.queue()['count'], 0)
        self.refused(self.teacher_client.get(f'/api/assistant/reviews/{self.review.pk}/'), 404, 'not_found')

    def test_confirm_with_a_note(self):
        response = self.act({'action': 'CONFIRM', 'note': '  Bonne réponse : relisez la définition.  '})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['status'], response.data['status_label'], response.data['teacher_note']),
            ('CONFIRMED', 'Réponse confirmée', 'Bonne réponse : relisez la définition.'))
        self.assertIsNotNone(response.data['reviewed_at'])
        stored = AnswerFeedback.objects.get(pk=self.review.pk)
        self.assertEqual((stored.reviewed_by_id, stored.rating, stored.comment), (self.teacher.pk, 'DOWN', 'Il manque un exemple.'))
        self.assertFalse(ValidatedAnswer.objects.exists())
        # The student sees the outcome under the answer.
        listed = self.student_client.get(f'/api/assistant/conversations/{self.conversation}/messages/').data['results']
        outcome = next(m['feedback'] for m in listed if m['id'] == self.answer['id'])
        self.assertEqual((outcome['status'], outcome['status_label'], outcome['teacher_note']), ('CONFIRMED', 'Réponse confirmée', 'Bonne réponse : relisez la définition.'))

    def test_dismiss(self):
        data = self.act({'action': 'DISMISS'}).data
        self.assertEqual((data['status'], data['status_label'], data['teacher_note']), ('DISMISSED', 'Classé sans suite', ''))
        self.assertEqual(self.queue('?status=NEW')['count'], 0)

    def test_correction_teaches_the_assistant(self):
        response = self.act({'action': 'CORRECT'})
        self.assertEqual(response.status_code, 400); self.assertEqual(response.data['error']['fields'], {'correction': ['Rédigez la réponse corrigée.']})
        for body in ({'action': 'CORRECT', 'correction': '   '}, {'action': 'CONFIRM', 'correction': 'Non.'}, {'action': 'DISMISS', 'correction': ''},
                {'action': 'VALIDER'}, {}, {'action': 'CORRECT', 'correction': 'x' * 2001}, {'action': 'CONFIRM', 'note': 'x' * 2001},
                {'action': 'CONFIRM', 'status': 'CORRECTED'}):
            with self.subTest(body=body): self.assertEqual(self.act(body).status_code, 400)
        self.assertEqual(AnswerFeedback.objects.get(pk=self.review.pk).status, 'NEW')
        provider = NotesProvider()
        before = ensure_index(provider, str(self.group.pk)).content_version
        correction = 'La norme d’un vecteur est sa longueur ; on la note avec deux barres verticales. Exemple : un vecteur de coordonnées (3 ; 4) a une norme égale à 5.'
        data = self.act({'action': 'CORRECT', 'correction': correction}).data
        self.assertEqual((data['status'], data['status_label'], data['teacher_note']), ('CORRECTED', 'Correction publiée', correction))
        validated = ValidatedAnswer.objects.get()
        self.assertEqual((validated.source_type, validated.scope_id, validated.question, validated.answer, validated.teacher_id, validated.feedback_id),
            ('group', str(self.group.pk), IN_SCOPE, correction, self.teacher.pk, self.review.pk))
        self.assertNotEqual(provider.version(str(self.group.pk)), before.split(':', 1)[1])
        # The next question about the same point is answered from the correction first.
        answer = self.answered(self.start(), 'Comment noter la norme d’un vecteur ?')['answer']
        self.assertEqual((answer['citations'][0]['source_kind'], answer['citations'][0]['source_title'], answer['citations'][0]['source_id']),
            ('VALIDATED', 'Réponse validée par l’enseignant', str(validated.pk)))
        self.assertIn('deux barres verticales', answer['citations'][0]['excerpt'])

    def test_only_new_feedback_can_be_reviewed(self):
        self.assertEqual(self.act({'action': 'CONFIRM'}).status_code, 200)
        for body in ({'action': 'DISMISS'}, {'action': 'CORRECT', 'correction': 'Autre réponse.'}, {'action': 'CONFIRM', 'note': 'Encore'}):
            with self.subTest(body=body):
                error = self.refused(self.act(body), 409, 'already_reviewed')
                self.assertEqual(error['message'], 'Ce retour a déjà été traité.')
        stored = AnswerFeedback.objects.get(pk=self.review.pk)
        self.assertEqual((stored.status, stored.teacher_note), ('CONFIRMED', '')); self.assertFalse(ValidatedAnswer.objects.exists())

    def test_review_whose_answer_was_purged_first_is_gone(self):
        # The TTL monitor removes the answer and its feedback in separate passes.
        connection.ensure_connection()
        connection.database['assistant_message'].delete_one({'_id': ObjectId(self.answer['id'])})
        self.refused(self.teacher_client.get(f'/api/assistant/reviews/{self.review.pk}/'), 404, 'not_found')
        self.refused(self.act({'action': 'CORRECT', 'correction': 'Trop tard.'}), 404, 'not_found')
        self.assertEqual((AnswerFeedback.objects.get(pk=self.review.pk).status, ValidatedAnswer.objects.count()), ('NEW', 0))
        self.assertEqual(self.queue()['results'], [])

    def test_administrator_reviews_every_scope(self):
        data = self.act({'action': 'CORRECT', 'correction': 'Ec = ½ m v².'}, self.other_review, self.as_user(self.admin)).data
        self.assertEqual(data['status'], 'CORRECTED')
        self.assertEqual(ValidatedAnswer.objects.get().teacher_id, self.admin.pk)

    def test_teacher_loses_the_queue_of_a_group_given_to_someone_else(self):
        self.group.teacher = self.other_teacher; self.group.save()
        self.assertEqual(self.queue()['count'], 0)
        self.assertEqual(self.queue(client=self.as_user(self.other_teacher))['count'], 2)
        Enrollment.objects.filter(student=self.student).update(ends_at=timezone.now())
        # The review stays possible after the student left the group.
        self.assertEqual(self.act({'action': 'CONFIRM'}, client=self.as_user(self.other_teacher)).status_code, 200)
