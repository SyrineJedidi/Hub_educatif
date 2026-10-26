from rest_framework import serializers
from .serializers import QuizInputSerializer, QuizChoiceField, QuizIntegerField


class SaveAnswerSerializer(QuizInputSerializer):
    selected_choice = QuizChoiceField(choices=list('ABCD'))
    expected_revision = QuizIntegerField(min_value=0)


class SubmitAttemptSerializer(QuizInputSerializer):
    answer_revisions = serializers.DictField(child=QuizIntegerField(min_value=1))


def answer_data(answer):
    return {'question_id': str(answer.question_id), 'selected_choice': answer.selected_choice, 'revision': answer.revision}
