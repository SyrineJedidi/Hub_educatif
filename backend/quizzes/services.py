from django.core.exceptions import ValidationError as ModelValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from classrooms.services import get_object
from .models import Quiz, Question
from .serializers import QuizWriteSerializer, AdminQuizWriteSerializer


def manager_quizzes(user):
    return Quiz.objects.all() if user.role == 'ADMIN' else Quiz.objects.filter(teacher=user)


def managed_quiz(user, uid):
    quiz = get_object(Quiz, uid)
    if user.role != 'ADMIN' and quiz.teacher_id != user.pk: raise NotFound('Quiz introuvable.')
    return quiz


def student_quizzes(user):
    now = timezone.now()
    group_ids = list(Enrollment.objects.filter(student=user, starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('group_id', flat=True))
    active_ids = list(LearningGroup.objects.filter(pk__in=group_ids, archived=False).values_list('id', flat=True))
    return Quiz.objects.filter(learning_group_id__in=active_ids, status='PUBLISHED')


def draft_only(quiz):
    if quiz.status != Quiz.Status.DRAFT:
        raise ValidationError({'status': ['Ce quiz est verrouillé. Dupliquez-le pour préparer un nouveau brouillon.']})


def model_errors(instance):
    try: instance.full_clean(validate_unique=False, validate_constraints=False)
    except ModelValidationError as exc:
        errors = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
        errors = {('learning_group_id' if k == 'learning_group' else 'teacher_id' if k == 'teacher' else k): v for k, v in errors.items()}
        raise ValidationError(errors)


def quiz_values(request, data, instance=None, duplicate=False):
    cls = AdminQuizWriteSerializer if request.user.role == 'ADMIN' else QuizWriteSerializer
    serializer = cls(data=data, partial=bool(instance) and not duplicate)
    serializer.is_valid(raise_exception=True)
    attrs = dict(serializer.validated_data)
    try:
        teacher = get_object(User, attrs.pop('teacher_id')) if 'teacher_id' in attrs else instance.teacher if instance and request.user.role == 'ADMIN' else request.user
    except NotFound:
        raise ValidationError({'teacher_id': ['Sélectionnez un enseignant actif existant.']})
    try:
        group = get_object(LearningGroup, attrs.pop('learning_group_id')) if 'learning_group_id' in attrs else instance.learning_group
    except NotFound:
        raise ValidationError({'learning_group_id': ['Sélectionnez un groupe actif autorisé existant.']})
    candidate = Quiz(teacher=teacher, learning_group=group)
    for field in ('title', 'description', 'level', 'duration_minutes', 'max_attempts'):
        setattr(candidate, field, attrs.get(field, getattr(instance, field) if instance else getattr(candidate, field)))
    model_errors(candidate)
    return {**{f: getattr(candidate, f) for f in ('title', 'description', 'level', 'duration_minutes', 'max_attempts')}, 'teacher': teacher, 'learning_group': group}


def publication_blockers(quiz):
    reasons = []
    try: model_errors(quiz)
    except ValidationError as exc:
        for field, messages in exc.detail.items():
            label = {'learning_group_id': 'Groupe pédagogique', 'teacher_id': 'Enseignant', 'title': 'Titre', 'max_attempts': 'Tentatives', 'duration_minutes': 'Durée'}.get(field, field)
            reasons.extend(f'{label} : {message}' for message in messages)
    questions = list(Question.objects.filter(quiz=quiz))
    if not questions: reasons.append('Ajoutez au moins une question avant de publier.')
    for question in questions:
        try: model_errors(question)
        except ValidationError as exc:
            for field, messages in exc.detail.items():
                label = {'statement':'énoncé', 'explanation':'explication de correction', 'correct_answer':'bonne réponse', **{f'choice_{letter}':f'proposition {letter.upper()}' for letter in 'abcd'}}.get(field, field)
                reasons.extend(f'Question {question.position}, {label} : {message}' for message in messages)
    return reasons


def question_for(quiz, uid):
    question = get_object(Question, uid)
    if question.quiz_id != quiz.pk: raise NotFound('Question introuvable dans ce quiz.')
    return question


def filtered_quizzes(request, queryset):
    from rest_framework.fields import ChoiceField
    q = request.query_params.get('q', '')[:150]
    if q: queryset = queryset.filter(title__icontains=q)
    for parameter, choices in [('status', Quiz.Status.values), ('level', Quiz.Level.values)]:
        value = request.query_params.get(parameter)
        if value:
            value = ChoiceField(choices=choices).run_validation(value)
            queryset = queryset.filter(**{parameter: value})
    if request.query_params.get('group'):
        group = get_object(LearningGroup, request.query_params['group'])
        queryset = queryset.filter(learning_group=group)
    if request.user.role == 'ADMIN' and request.query_params.get('teacher'):
        teacher = get_object(User, request.query_params['teacher'])
        queryset = queryset.filter(teacher=teacher)
    return queryset.order_by('-created_at', 'id')
