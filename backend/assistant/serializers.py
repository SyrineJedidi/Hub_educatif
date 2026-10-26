from collections.abc import Mapping
import re
from rest_framework import serializers
from accounts.serializers import StrictSerializer
from .models import (NOTE_BODY_MAX_LENGTH, QUESTION_MAX_LENGTH, AnswerFeedback,
    Conversation, Message, Mode)

MAX_SUGGESTED_QUESTIONS = 5
LANGUAGES = ['fr', 'en', 'ar']


class AssistantInputSerializer(StrictSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping): raise serializers.ValidationError({'non_field_errors': ['Envoyez un objet JSON.']})
        return super().to_internal_value(data)


class AssistantTextField(serializers.CharField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'blank': 'Ce champ est obligatoire et ne peut pas contenir uniquement des espaces.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez un texte valide.',
        'max_length': 'Limitez ce champ à {max_length} caractères.',
    }

    def to_internal_value(self, data):
        if not isinstance(data, str): self.fail('invalid')
        return super().to_internal_value(data)


class AssistantBooleanField(serializers.BooleanField):
    default_error_messages = {'required': 'Ce champ est obligatoire.', 'null': 'Ce champ ne peut pas être vide.', 'invalid': 'Envoyez true ou false.'}

    def to_internal_value(self, data):
        if not isinstance(data, bool): self.fail('invalid')
        return data


class AssistantIntegerField(serializers.IntegerField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez un nombre entier, sans décimale ni notation scientifique.',
        'min_value': 'Saisissez un entier supérieur ou égal à {min_value}.',
        'max_value': 'Saisissez un entier inférieur ou égal à {max_value}.',
        'max_string_length': 'Ce nombre est trop grand.',
    }

    def to_internal_value(self, data):
        if type(data) is not int and not (isinstance(data, str) and re.fullmatch(r'[0-9]+', data.strip())): self.fail('invalid')
        return super().to_internal_value(data)


class AssistantChoiceField(serializers.ChoiceField):
    default_error_messages = {'required': 'Sélectionnez une valeur.', 'null': 'Sélectionnez une valeur.', 'invalid_choice': 'Sélectionnez une valeur autorisée.'}


class AssistantReferenceField(AssistantTextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(r'[0-9a-fA-F]{24}', value): raise serializers.ValidationError('Sélectionnez une valeur existante dans la liste.')
        return value.lower()


class ClientIdField(AssistantTextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', value):
            raise serializers.ValidationError('Envoyez un identifiant UUID.')
        return value.lower()


class TextListField(serializers.ListField):
    default_error_messages = {'not_a_list': 'Envoyez une liste.', 'max_length': 'Indiquez au plus {max_length} éléments.', 'null': 'Ce champ ne peut pas être vide.'}

    def to_internal_value(self, data):
        if not isinstance(data, list): self.fail('not_a_list', input_type=type(data).__name__)
        try: values = super().to_internal_value(data)
        except serializers.ValidationError as exc:
            # Item errors come keyed by position; the client prints field errors as plain text.
            raise serializers.ValidationError([f'Élément {index + 1} : {message}' for index, messages in sorted(exc.detail.items()) for message in messages])
        return list(dict.fromkeys(values))


class ConversationCreateSerializer(AssistantInputSerializer):
    scope_key = AssistantTextField(max_length=40)
    title = AssistantTextField(max_length=120, required=False)
    mode = AssistantChoiceField(choices=Mode.choices, required=False)


class ConversationUpdateSerializer(AssistantInputSerializer):
    title = AssistantTextField(max_length=120, required=False)
    pinned = AssistantBooleanField(required=False)
    status = AssistantChoiceField(choices=[('ACTIVE', 'Active'), ('ARCHIVED', 'Archivée')], required=False)
    mode = AssistantChoiceField(choices=Mode.choices, required=False)


class MessageCreateSerializer(AssistantInputSerializer):
    content = AssistantTextField(max_length=QUESTION_MAX_LENGTH)
    input_mode = AssistantChoiceField(choices=Message.InputMode.choices, required=False, default=Message.InputMode.TEXT)
    client_id = ClientIdField(required=False)


class FeedbackSerializer(AssistantInputSerializer):
    rating = AssistantChoiceField(choices=AnswerFeedback.Rating.choices)
    reasons = TextListField(child=AssistantChoiceField(choices=AnswerFeedback.Reason.choices), required=False, max_length=len(AnswerFeedback.Reason.values))
    comment = AssistantTextField(max_length=500, required=False, allow_blank=True)
    shared_with_teacher = AssistantBooleanField(required=False)

    def validate(self, attrs):
        if attrs['rating'] == AnswerFeedback.Rating.DOWN and not attrs.get('reasons'):
            raise serializers.ValidationError({'reasons': ['Indiquez au moins une raison.']})
        if attrs['rating'] == AnswerFeedback.Rating.UP: attrs['reasons'] = []
        return attrs


class NoteCreateSerializer(AssistantInputSerializer):
    group_id = AssistantReferenceField()
    title = AssistantTextField(max_length=120)
    body = AssistantTextField(max_length=NOTE_BODY_MAX_LENGTH)


class NoteUpdateSerializer(AssistantInputSerializer):
    title = AssistantTextField(max_length=120, required=False)
    body = AssistantTextField(max_length=NOTE_BODY_MAX_LENGTH, required=False)


class SettingsSerializer(AssistantInputSerializer):
    enabled = AssistantBooleanField(required=False)
    default_mode = AssistantChoiceField(choices=Mode.choices, required=False)
    allow_mode_choice = AssistantBooleanField(required=False)
    daily_question_limit = AssistantIntegerField(min_value=1, max_value=200, required=False)
    block_during_quiz = AssistantBooleanField(required=False)
    suggested_questions = TextListField(child=AssistantTextField(max_length=200), required=False, max_length=MAX_SUGGESTED_QUESTIONS)
    welcome_message = AssistantTextField(max_length=500, required=False, allow_blank=True)


class ReviewActionSerializer(AssistantInputSerializer):
    action = AssistantChoiceField(choices=[('CONFIRM', 'Confirmer'), ('CORRECT', 'Corriger'), ('DISMISS', 'Classer sans suite')])
    correction = AssistantTextField(max_length=2000, required=False)
    note = AssistantTextField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['action'] == 'CORRECT' and not attrs.get('correction'):
            raise serializers.ValidationError({'correction': ['Rédigez la réponse corrigée.']})
        if attrs['action'] != 'CORRECT' and 'correction' in attrs:
            raise serializers.ValidationError({'correction': ['Une correction accompagne uniquement l’action « Corriger ».']})
        return attrs


class TranscriptionSerializer(StrictSerializer):
    audio = serializers.FileField(error_messages={'required': 'Joignez un enregistrement audio.', 'invalid': 'Joignez un enregistrement audio.',
        'empty': 'L’enregistrement audio est vide.', 'no_name': 'Joignez un enregistrement audio.'})
    language = AssistantChoiceField(choices=LANGUAGES, required=False)


def person_data(user):
    return {'id': str(user.pk), 'first_name': user.first_name, 'last_name': user.last_name} if user else None


def scope_key(source_type, scope_id):
    return f'{source_type}:{scope_id}'


def scope_data(scope, row, quota, teacher):
    return {'source_type': scope.source_type, 'scope_id': scope.scope_id, 'key': scope.key, 'title': scope.title,
        'teacher': person_data(teacher), 'enabled': row.enabled, 'default_mode': row.default_mode,
        'allow_mode_choice': row.allow_mode_choice, 'suggested_questions': list(row.suggested_questions or []),
        'welcome_message': row.welcome_message, 'quota': quota}


def settings_data(scope, row, teacher, max_daily_limit):
    return {'source_type': scope.source_type, 'scope_id': scope.scope_id, 'key': scope.key, 'title': scope.title,
        'teacher': person_data(teacher), 'enabled': row.enabled, 'default_mode': row.default_mode,
        'allow_mode_choice': row.allow_mode_choice, 'daily_question_limit': row.daily_question_limit,
        'effective_daily_limit': min(row.daily_question_limit, max_daily_limit), 'max_daily_question_limit': max_daily_limit,
        'block_during_quiz': row.block_during_quiz, 'suggested_questions': list(row.suggested_questions or []),
        'welcome_message': row.welcome_message, 'updated_at': row.updated_at}


def conversation_data(conversation, can_send=False):
    return {'id': str(conversation.pk), 'source_type': conversation.source_type, 'scope_id': conversation.scope_id,
        'scope_key': scope_key(conversation.source_type, conversation.scope_id), 'scope_title': conversation.scope_title,
        'title': conversation.title, 'mode': conversation.mode, 'mode_label': Mode(conversation.mode).label,
        'status': conversation.status, 'status_label': Conversation.Status(conversation.status).label,
        'pinned': conversation.pinned, 'message_count': conversation.message_count, 'last_message_at': conversation.last_message_at,
        'created_at': conversation.created_at, 'purge_at': conversation.purge_at,
        'can_send': bool(can_send and conversation.status == Conversation.Status.ACTIVE)}


def citation_data(citation):
    return {'number': citation.number, 'source_kind': citation.source_kind, 'source_id': citation.source_id,
        'source_title': citation.source_title, 'chapter_title': citation.chapter_title, 'page': citation.page,
        'start_seconds': citation.start_seconds, 'url': citation.url, 'excerpt': citation.excerpt, 'score': citation.score}


def feedback_data(feedback):
    if not feedback: return None
    return {'rating': feedback.rating, 'reasons': list(feedback.reasons or []), 'comment': feedback.comment,
        'shared_with_teacher': feedback.shared_with_teacher, 'status': feedback.status,
        'status_label': AnswerFeedback.Status(feedback.status).label, 'teacher_note': feedback.teacher_note}


def message_data(message, feedback=None):
    assistant = message.role == Message.Role.ASSISTANT
    return {'id': str(message.pk), 'conversation_id': str(message.conversation_id), 'role': message.role,
        'reply_to_id': str(message.reply_to_id) if message.reply_to_id else None,
        'content': message.content, 'input_mode': message.input_mode, 'status': message.status,
        'status_label': Message.Status(message.status).label, 'unsourced': message.unsourced,
        'citations': [citation_data(c) for c in message.citations or []], 'follow_ups': list(message.follow_ups or []),
        'latency_ms': message.latency_ms if assistant else None, 'created_at': message.created_at,
        'feedback': feedback_data(feedback) if assistant else None}


def note_data(note):
    group = note.group
    return {'id': str(note.pk), 'group': {'id': str(group.pk), 'name': group.name, 'code': group.code}, 'title': note.title,
        'body': note.body, 'version': note.version, 'teacher': person_data(note.teacher), 'created_at': note.created_at, 'updated_at': note.updated_at}


def review_data(feedback, question, answer, scope_title):
    # Deliberately no student, owner or conversation id: teachers review answers, not students.
    return {'id': str(feedback.pk), 'scope_key': scope_key(feedback.source_type, feedback.scope_id), 'scope_title': scope_title,
        'question': question.content if question else '',
        'answer': {'content': answer.content, 'citations': [citation_data(c) for c in answer.citations or []], 'created_at': answer.created_at},
        'rating': feedback.rating, 'reasons': list(feedback.reasons or []),
        'reason_labels': [AnswerFeedback.Reason(r).label for r in feedback.reasons or [] if r in AnswerFeedback.Reason.values],
        'comment': feedback.comment, 'status': feedback.status, 'status_label': AnswerFeedback.Status(feedback.status).label,
        'teacher_note': feedback.teacher_note, 'reviewed_at': feedback.reviewed_at, 'created_at': feedback.created_at}
