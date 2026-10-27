from django.utils import timezone
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from accounts.views import SecureView, validated
from classrooms.services import mutation, paginated, get_object
from .models import Quiz, Question, duplicate_title
from .permissions import QuizManager, QuizStudent
from .serializers import (ManagementQuizSerializer, StudentQuizSerializer, QuestionReadSerializer,
    QuestionWriteSerializer, ReorderSerializer, EmptyActionSerializer)
from .services import (manager_quizzes, managed_quiz, student_quizzes, draft_only, model_errors,
    quiz_values, publication_blockers, question_for, filtered_quizzes)


class ManagerView(SecureView):
    permission_classes = [QuizManager]

class QuizzesView(ManagerView):
    def get(self, request):
        qs = filtered_quizzes(request, manager_quizzes(request.user))
        return Response(paginated(request, qs, lambda q: ManagementQuizSerializer(q).data))
    @mutation
    def post(self, request):
        quiz = Quiz.objects.create(**quiz_values(request, request.data))
        return Response(ManagementQuizSerializer(quiz).data, status=201)

class QuizDetailView(ManagerView):
    def get(self, request, uid):
        return Response(ManagementQuizSerializer(managed_quiz(request.user, uid)).data)
    @mutation
    def patch(self, request, uid):
        quiz = managed_quiz(request.user, uid); draft_only(quiz)
        for field, value in quiz_values(request, request.data, quiz).items(): setattr(quiz, field, value)
        quiz.save()
        return Response(ManagementQuizSerializer(quiz).data)
    @mutation
    def delete(self, request, uid):
        quiz = managed_quiz(request.user, uid); draft_only(quiz)
        # Explicit single-collection deletes: the MongoDB backend does not support joined deletes.
        Question.objects.filter(quiz=quiz).delete()
        quiz.delete()
        return Response(status=204)

class QuestionsView(ManagerView):
    def get(self, request, uid):
        quiz = managed_quiz(request.user, uid)
        return Response({'results': QuestionReadSerializer(Question.objects.filter(quiz=quiz), many=True).data})
    @mutation
    def post(self, request, uid):
        quiz = managed_quiz(request.user, uid); draft_only(quiz)
        data = validated(QuestionWriteSerializer, request)
        if 'position' not in data:
            last = Question.objects.filter(quiz=quiz).order_by('-position').first()
            data['position'] = last.position + 1 if last else 1
        if Question.objects.filter(quiz=quiz, position=data['position']).exists():
            raise ValidationError({'position': ['Cette position est déjà utilisée dans le quiz.']})
        question = Question(quiz=quiz, **data); model_errors(question); question.save()
        quiz.save(update_fields=['updated_at'])
        return Response(QuestionReadSerializer(question).data, status=201)

class QuestionDetailView(ManagerView):
    @mutation
    def patch(self, request, uid, question_id):
        quiz = managed_quiz(request.user, uid); draft_only(quiz)
        question = question_for(quiz, question_id)
        serializer = QuestionWriteSerializer(data=request.data, partial=True); serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items(): setattr(question, field, value)
        if Question.objects.filter(quiz=quiz, position=question.position).exclude(pk=question.pk).exists():
            raise ValidationError({'position': ['Cette position est déjà utilisée dans le quiz.']})
        model_errors(question); question.save(); quiz.save(update_fields=['updated_at'])
        return Response(QuestionReadSerializer(question).data)
    def get(self, request, uid, question_id):
        quiz = managed_quiz(request.user, uid)
        return Response(QuestionReadSerializer(question_for(quiz, question_id)).data)
    @mutation
    def delete(self, request, uid, question_id):
        quiz = managed_quiz(request.user, uid); draft_only(quiz)
        question_for(quiz, question_id).delete(); quiz.save(update_fields=['updated_at'])
        return Response(status=204)

class ReorderView(ManagerView):
    @mutation
    def post(self, request, uid):
        quiz = managed_quiz(request.user, uid); draft_only(quiz)
        ids = validated(ReorderSerializer, request)['question_ids']
        questions = list(Question.objects.filter(quiz=quiz))
        if len(ids) != len(set(ids)) or set(ids) != {str(q.pk) for q in questions}:
            raise ValidationError({'question_ids': ['Envoyez exactement les questions de ce quiz, sans doublon.']})
        by_id = {str(q.pk): q for q in questions}
        occupied = {q.position for q in questions}; temporary = len(questions) + 1
        for q in questions:
            while temporary in occupied: temporary += 1
            q.position = temporary; q.save(update_fields=['position', 'updated_at']); occupied.add(temporary); temporary += 1
        for position, question_id in enumerate(ids, 1):
            q = by_id[question_id]; q.position = position; q.save(update_fields=['position', 'updated_at'])
        quiz.save(update_fields=['updated_at'])
        return Response({'results': QuestionReadSerializer(Question.objects.filter(quiz=quiz), many=True).data})

class PreviewView(ManagerView):
    def get(self, request, uid):
        quiz = managed_quiz(request.user, uid)
        return Response({'quiz': ManagementQuizSerializer(quiz).data, 'questions': QuestionReadSerializer(Question.objects.filter(quiz=quiz), many=True).data,
            'publication_blockers': publication_blockers(quiz) if quiz.status == 'DRAFT' else []})

class PublishView(ManagerView):
    @mutation
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        quiz = managed_quiz(request.user, uid); draft_only(quiz)
        reasons = publication_blockers(quiz)
        if reasons: raise ValidationError({'publication': reasons})
        quiz.status = Quiz.Status.PUBLISHED; quiz.published_at = timezone.now(); quiz.save(update_fields=['status', 'published_at', 'updated_at'])
        return Response(ManagementQuizSerializer(quiz).data)

class ArchiveView(ManagerView):
    @mutation
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        quiz = managed_quiz(request.user, uid)
        if quiz.status != Quiz.Status.PUBLISHED: raise ValidationError({'status': ['Seul un quiz publié peut être archivé.']})
        quiz.status = Quiz.Status.ARCHIVED; quiz.save(update_fields=['status', 'updated_at'])
        return Response(ManagementQuizSerializer(quiz).data)

class DuplicateView(ManagerView):
    @mutation
    def post(self, request, uid):
        original = managed_quiz(request.user, uid)
        if original.status not in ('PUBLISHED', 'ARCHIVED'): raise ValidationError('Seul un quiz publié ou archivé peut être dupliqué.')
        initial = {field: getattr(original, field) for field in ('title', 'description', 'level', 'duration_minutes', 'max_attempts', 'opens_at', 'closes_at')}
        for field in ('opens_at', 'closes_at'):
            if initial[field]: initial[field] = initial[field].isoformat()
        initial['title'] = duplicate_title(original.title)
        initial['learning_group_id'] = str(original.learning_group_id)
        if request.user.role == 'ADMIN': initial['teacher_id'] = str(original.teacher_id)
        if not isinstance(request.data, dict): raise ValidationError('Envoyez un objet JSON.')
        initial.update(request.data)
        quiz = Quiz.objects.create(**quiz_values(request, initial))
        for old in Question.objects.filter(quiz=original):
            attrs = {field: getattr(old, field) for field in ('statement','choice_a','choice_b','choice_c','choice_d','correct_answer','explanation','notion','points','position')}
            if not attrs['notion']: attrs.pop('notion')
            copied = Question(quiz=quiz, **attrs)
            try: model_errors(copied)
            except ValidationError as exc:
                raise ValidationError({'questions': [f'Question {old.position} : {field} — {message}' for field,messages in exc.detail.items() for message in messages]})
            copied.save()
        return Response(ManagementQuizSerializer(quiz).data, status=201)

class StudentQuizzesView(SecureView):
    permission_classes = [QuizStudent]
    def get(self, request):
        qs = filtered_quizzes(request, student_quizzes(request.user))
        return Response(paginated(request, qs, lambda q: StudentQuizSerializer(q).data))

class StudentQuizDetailView(StudentQuizzesView):
    def get(self, request, uid):
        quiz = get_object(Quiz, uid)
        if not student_quizzes(request.user).filter(pk=quiz.pk).exists(): raise NotFound('Quiz introuvable.')
        return Response(StudentQuizSerializer(quiz).data)
