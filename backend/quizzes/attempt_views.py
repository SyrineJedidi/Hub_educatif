from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from accounts.views import SecureView, validated
from classrooms.services import mutation, get_object, paginated
from .models import Quiz, Attempt, Answer
from .permissions import QuizStudent
from .serializers import EmptyActionSerializer
from .attempt_serializers import SaveAnswerSerializer, SubmitAttemptSerializer, answer_data
from .attempt_services import (require_group_access, own_attempt, error_response, expire_if_due,
    finalize, attempt_summary, attempt_data, result_data, create_attempt, accessible_attempts, refresh_expired)


class StudentAttemptView(SecureView):
    permission_classes = [QuizStudent]


class StudentAttemptsListView(StudentAttemptView):
    def get(self, request):
        def serialize(attempt):
            refresh_expired(request, [attempt])
            return attempt_summary(attempt)
        return Response(paginated(request, accessible_attempts(request.user), serialize))


class QuizAttemptsView(StudentAttemptView):
    def get(self, request, uid):
        quiz = get_object(Quiz, uid)
        require_group_access(request.user, quiz.learning_group)
        attempts = list(Attempt.objects.filter(student=request.user, quiz=quiz))
        if quiz.status != 'PUBLISHED' and not attempts: raise NotFound('Quiz introuvable.')
        refresh_expired(request, attempts)
        current = next((a for a in attempts if a.status == 'IN_PROGRESS'), None)
        return Response({'quiz_status': quiz.status, 'attempts_used': len(attempts),
            'max_attempts': quiz.max_attempts, 'remaining_attempts': max(0, quiz.max_attempts - len(attempts)),
            'current_attempt_id': str(current.pk) if current else None,
            'attempts': [attempt_summary(a) for a in attempts]})

    @mutation
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        quiz = get_object(Quiz, uid)
        require_group_access(request.user, quiz.learning_group)
        attempts = list(Attempt.objects.filter(student=request.user, quiz=quiz))
        for attempt in attempts:
            expire_if_due(attempt)
            if attempt.status == 'IN_PROGRESS': return Response(attempt_data(attempt))
        if quiz.status != 'PUBLISHED': return error_response('quiz_unavailable', 'Ce quiz n’est pas publié. Aucun nouveau départ n’est possible.', 400)
        if len(attempts) >= quiz.max_attempts: return error_response('attempt_limit', 'Vous avez utilisé toutes les tentatives autorisées.', 400)
        attempt = create_attempt(request.user, quiz, len(attempts) + 1)
        if not attempt: return error_response('empty_quiz', 'Ce quiz ne contient aucune question.', 400)
        return Response(attempt_data(attempt), status=201)


class AttemptDetailView(StudentAttemptView):
    def get(self, request, attempt_id):
        attempt = own_attempt(request.user, attempt_id)
        refresh_expired(request, [attempt])
        return Response(attempt_data(attempt))


class SaveAnswerView(StudentAttemptView):
    @mutation
    def put(self, request, attempt_id, question_id):
        attempt = own_attempt(request.user, attempt_id)
        expire_if_due(attempt)
        if attempt.status != 'IN_PROGRESS': return error_response('attempt_closed', 'La tentative est terminée. Les réponses ne peuvent plus être enregistrées.')
        data = validated(SaveAnswerSerializer, request)
        if question_id not in {q['id'] for q in attempt.question_snapshot}: raise NotFound('Question introuvable dans cette tentative.')
        answer = Answer.objects.filter(attempt=attempt, question_id=question_id).first()
        revision = answer.revision if answer else 0
        if data['expected_revision'] != revision:
            # A lost acknowledgement can be retried without changing the answer.
            if answer and data['selected_choice'] == answer.selected_choice:
                return Response(answer_data(answer))
            return error_response('answer_conflict', 'Cette réponse a changé dans une autre fenêtre. Rechargez la tentative pour vérifier vos réponses.')
        if answer:
            answer.selected_choice = data['selected_choice']; answer.revision += 1
            answer.save(update_fields=['selected_choice', 'revision', 'updated_at'])
        else:
            answer = Answer.objects.create(attempt=attempt, question_id=question_id, selected_choice=data['selected_choice'])
        return Response(answer_data(answer))


class SubmitAttemptView(StudentAttemptView):
    @mutation
    def post(self, request, attempt_id):
        attempt = own_attempt(request.user, attempt_id)
        expire_if_due(attempt)
        if attempt.status == 'IN_PROGRESS':
            data = validated(SubmitAttemptSerializer, request)
            actual = {str(a.question_id): a.revision for a in Answer.objects.filter(attempt=attempt)}
            if actual != data['answer_revisions']:
                return error_response('answers_not_synchronized', 'Les réponses enregistrées ont changé. Rechargez la tentative et vérifiez-les avant de soumettre.')
            finalize(attempt)
        return Response(result_data(attempt))


class AttemptResultView(StudentAttemptView):
    def get(self, request, attempt_id):
        attempt = own_attempt(request.user, attempt_id)
        refresh_expired(request, [attempt])
        if attempt.status == 'IN_PROGRESS': return error_response('attempt_in_progress', 'Soumettez la tentative pour consulter sa correction.')
        return Response(result_data(attempt))
