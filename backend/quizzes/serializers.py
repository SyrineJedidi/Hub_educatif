from collections.abc import Mapping
import re
from datetime import datetime
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from accounts.serializers import StrictSerializer
from .models import Quiz, Question, QUIZ_TITLE_MAX_LENGTH

class QuizInputSerializer(StrictSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping): raise serializers.ValidationError({'non_field_errors': ['Envoyez un objet JSON.']})
        return super().to_internal_value(data)


class QuizTextField(serializers.CharField):
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


class QuizIntegerField(serializers.IntegerField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez un nombre entier, sans décimale ni notation scientifique.',
        'min_value': 'Saisissez un entier supérieur ou égal à {min_value}.',
        'max_value': 'Saisissez un entier inférieur ou égal à {max_value}.',
        'max_string_length': 'Ce nombre est trop grand.',
    }

    def to_internal_value(self, data):
        if type(data) is not int and not (isinstance(data, str) and re.fullmatch(r'[0-9]+', data.strip())):
            self.fail('invalid')
        return super().to_internal_value(data)


class QuizChoiceField(serializers.ChoiceField):
    default_error_messages = {
        'required': 'Sélectionnez une valeur.',
        'null': 'Sélectionnez une valeur.',
        'invalid_choice': 'Sélectionnez une valeur autorisée.',
    }


class QuizReferenceField(QuizTextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(r'[0-9a-fA-F]{24}', value):
            raise serializers.ValidationError('Sélectionnez une valeur existante dans la liste.')
        return value

class QuizDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, data):
        try: parsed = parse_datetime(data) if isinstance(data, str) else data
        except (ValueError, TypeError): parsed = None
        if not isinstance(parsed, datetime) or timezone.is_naive(parsed):
            raise serializers.ValidationError('Précisez une date valide avec son fuseau horaire.')
        return super().to_internal_value(data)

class QuizWriteSerializer(QuizInputSerializer):
    title = QuizTextField(max_length=QUIZ_TITLE_MAX_LENGTH)
    description = QuizTextField(max_length=2000)
    learning_group_id = QuizReferenceField()
    level = QuizChoiceField(choices=Quiz.Level.choices)
    duration_minutes = QuizIntegerField(min_value=1, max_value=2147483647, allow_null=True)
    max_attempts = QuizIntegerField(min_value=1, max_value=10)
    opens_at = QuizDateTimeField(allow_null=True, required=False)
    closes_at = QuizDateTimeField(allow_null=True, required=False)

class AdminQuizWriteSerializer(QuizWriteSerializer):
    teacher_id = QuizReferenceField()

class QuestionWriteSerializer(QuizInputSerializer):
    statement = QuizTextField(max_length=2000)
    choice_a = QuizTextField(max_length=500)
    choice_b = QuizTextField(max_length=500)
    choice_c = QuizTextField(max_length=500)
    choice_d = QuizTextField(max_length=500)
    correct_answer = QuizChoiceField(choices=list('ABCD'))
    explanation = QuizTextField()
    notion = QuizTextField(max_length=200, required=False)
    points = QuizIntegerField(min_value=1, max_value=10)
    position = QuizIntegerField(min_value=1, max_value=2147483647, required=False)

class ReorderSerializer(QuizInputSerializer):
    question_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)

class EmptyActionSerializer(QuizInputSerializer):
    pass

class StudentQuizSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    learning_group_id = serializers.CharField()
    learning_group_name = serializers.CharField(source='learning_group.name')
    level = serializers.CharField()
    duration_minutes = serializers.IntegerField(allow_null=True)
    max_attempts = serializers.IntegerField()
    status = serializers.CharField()
    published_at = serializers.DateTimeField(allow_null=True)
    opens_at = serializers.DateTimeField(allow_null=True)
    closes_at = serializers.DateTimeField(allow_null=True)
    availability = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    def get_question_count(self, quiz): return Question.objects.filter(quiz=quiz).count()
    def get_total_points(self, quiz): return sum(Question.objects.filter(quiz=quiz).values_list('points', flat=True))
    def get_availability(self, quiz):
        from .schedule import availability
        return availability(quiz)

class ManagementQuizSerializer(StudentQuizSerializer):
    teacher_id = serializers.CharField()
    teacher_name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    next_position = serializers.SerializerMethodField()
    def get_teacher_name(self, quiz): return f'{quiz.teacher.first_name} {quiz.teacher.last_name}'
    def get_next_position(self, quiz):
        last = Question.objects.filter(quiz=quiz).order_by('-position').first()
        return last.position + 1 if last else 1

class QuestionReadSerializer(serializers.Serializer):
    id = serializers.CharField()
    quiz_id = serializers.CharField()
    statement = serializers.CharField()
    choice_a = serializers.CharField()
    choice_b = serializers.CharField()
    choice_c = serializers.CharField()
    choice_d = serializers.CharField()
    correct_answer = serializers.CharField()
    explanation = serializers.CharField()
    notion = serializers.CharField()
    points = serializers.IntegerField()
    position = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
