import hashlib
import json
from bson import ObjectId
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError, PermissionDenied
from rest_framework.response import Response
from accounts.models import User
from accounts.services import limit
from accounts.views import validated
from classrooms.services import mutation, Conflict
from .generation import GenerationInputSerializer, configuration, generate_questions, validate_proposals
from .generation_jobs import dispatch, expire_stale, job_data
from .models import Question, QuestionGenerationJob, QuestionImport
from .serializers import QuizInputSerializer, QuestionReadSerializer
from .services import managed_quiz, draft_only, model_errors
from .views import ManagerView


def editable_quiz(user, uid):
    quiz = managed_quiz(user, uid)
    draft_only(quiz)
    model_errors(quiz)
    return quiz


def private(response):
    response['Cache-Control'] = 'private, no-store'
    return response


class GenerateQuestionsView(ManagerView):
    def post(self, request, uid):
        quiz = editable_quiz(request.user, uid)
        inputs = validated(GenerationInputSerializer, request)
        configuration()
        limit(request, 'quiz-local-ai', maximum=5, seconds=300, identity=str(request.user.pk))
        if settings.QUIZ_GENERATION_ASYNC:
            # Ollama often needs 30 s or more: the page polls the job instead of holding the request.
            job = QuestionGenerationJob.objects.create(quiz=quiz, teacher=request.user, inputs=dict(inputs))
            dispatch(job)
            job.refresh_from_db()
            return private(Response(job_data(job), status=202))
        # Never hold the shared write transaction during an external request.
        proposals = generate_questions(quiz, inputs)
        actor = User.objects.filter(pk=request.user.pk).first()
        if actor is None or not actor.is_active or actor.role != request.user.role:
            raise PermissionDenied('Vos droits ont changé. Reconnectez-vous.')
        editable_quiz(actor, uid)  # A concurrent publication also locks this page.
        return private(Response({'questions': proposals}))


class GenerationJobView(ManagerView):
    def get(self, request, uid, job_id):
        quiz = editable_quiz(request.user, uid)  # Rights and the draft state are checked again on delivery.
        job = QuestionGenerationJob.objects.filter(pk=job_id if ObjectId.is_valid(job_id) else None, quiz=quiz, teacher=request.user).first()
        if job is None: raise NotFound('Génération introuvable.')
        job = expire_stale(job)
        if job.status != QuestionGenerationJob.Status.SUCCEEDED or job.delivered:
            return private(Response(job_data(job, [] if job.delivered else None)))
        # Proposals are handed over once, then forgotten: only confirmed questions are kept.
        if not QuestionGenerationJob.objects.filter(pk=job.pk, delivered=False).update(delivered=True, proposals=[]):
            job.refresh_from_db()
            return private(Response(job_data(job, [])))
        return private(Response(job_data(job, job.proposals)))


class ImportSerializer(QuizInputSerializer):
    import_key = serializers.UUIDField()
    confirmed = serializers.BooleanField()
    questions = serializers.ListField(child=serializers.JSONField(), min_length=1, max_length=10)

    def validate_confirmed(self, value):
        if not value:
            raise ValidationError('Vérifiez et confirmez les questions avant de les ajouter.')
        return value


class ImportQuestionsView(ManagerView):
    @mutation
    def post(self, request, uid):
        quiz = editable_quiz(request.user, uid)
        data = validated(ImportSerializer, request)
        values = validate_proposals(quiz, data['questions'])
        key = str(data['import_key'])
        fingerprint = hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        receipt = QuestionImport.objects.filter(quiz=quiz, key=key).first()
        if receipt:
            if receipt.fingerprint != fingerprint:
                raise Conflict('Cette confirmation concerne déjà d’autres questions. Rechargez la page.')
            questions = {str(q.pk): q for q in Question.objects.filter(quiz=quiz)}
            if any(uid not in questions for uid in receipt.question_ids):
                raise Conflict('Ces questions ont déjà été ajoutées puis modifiées ou supprimées. Consultez le quiz.')
            return Response({'results': QuestionReadSerializer([questions[uid] for uid in receipt.question_ids], many=True).data,
                             'replayed': True})
        last = Question.objects.filter(quiz=quiz).order_by('-position').first()
        position = last.position + 1 if last else 1
        questions = []
        for offset, value in enumerate(values):
            question = Question(quiz=quiz, position=position + offset, **value)
            model_errors(question)
            question.save()
            questions.append(question)
        QuestionImport.objects.create(quiz=quiz, key=key, fingerprint=fingerprint,
                                     question_ids=[str(q.pk) for q in questions])
        quiz.save(update_fields=['updated_at'])
        return Response({'results': QuestionReadSerializer(questions, many=True).data, 'replayed': False}, status=201)
