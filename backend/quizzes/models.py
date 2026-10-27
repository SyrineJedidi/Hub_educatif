from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from classrooms.models import LearningGroup

QUIZ_TITLE_MAX_LENGTH = 50


def duplicate_title(title):
    suffix = ' (copie)'
    return title[:QUIZ_TITLE_MAX_LENGTH - len(suffix)] + suffix

def normalized_choice(value):
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


class Quiz(models.Model):
    class Level(models.TextChoices):
        EASY = 'EASY', 'Facile'
        MEDIUM = 'MEDIUM', 'Intermédiaire'
        HARD = 'HARD', 'Difficile'
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        PUBLISHED = 'PUBLISHED', 'Publié'
        ARCHIVED = 'ARCHIVED', 'Archivé'
    title = models.CharField(max_length=QUIZ_TITLE_MAX_LENGTH)
    description = models.TextField(max_length=2000)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='quizzes')
    learning_group = models.ForeignKey(LearningGroup, on_delete=models.PROTECT, related_name='quizzes')
    level = models.CharField(max_length=6, choices=Level.choices, default=Level.EASY)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(2147483647)])
    max_attempts = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)])
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=['teacher', 'status']), models.Index(fields=['learning_group', 'status'])]
    def clean(self):
        errors = {}
        from datetime import datetime
        for field in ('opens_at', 'closes_at'):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, datetime) or timezone.is_naive(value)):
                errors[field] = 'Précisez une date avec son fuseau horaire.'
        if not errors and self.opens_at and self.closes_at and self.opens_at >= self.closes_at:
            errors['closes_at'] = 'La fermeture doit être postérieure à l’ouverture.'
        if not isinstance(self.title, str) or not self.title.strip(): errors['title'] = 'Renseignez un titre non vide.'
        if not isinstance(self.description, str) or not self.description.strip(): errors['description'] = 'Renseignez une description non vide.'
        if self.teacher_id and (self.teacher.role != 'TEACHER' or not self.teacher.is_active):
            errors['teacher'] = 'Sélectionnez un enseignant actif.'
        if self.learning_group_id:
            if self.learning_group.archived: errors['learning_group'] = 'Le groupe est archivé.'
            elif self.teacher_id != self.learning_group.teacher_id:
                errors['learning_group'] = 'Le groupe doit être affecté à l’enseignant propriétaire.'
        if errors: raise ValidationError(errors)


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    statement = models.TextField(max_length=2000)
    choice_a = models.CharField(max_length=500)
    choice_b = models.CharField(max_length=500)
    choice_c = models.CharField(max_length=500)
    choice_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1, choices=[(x, x) for x in 'ABCD'])
    explanation = models.TextField()
    notion = models.CharField(max_length=200, blank=True, default='')
    points = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    position = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(2147483647)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['position', 'id']
        constraints = [models.UniqueConstraint(fields=['quiz', 'position'], name='unique_question_position_in_quiz')]
    def clean(self):
        errors = {}
        if not isinstance(self.statement, str) or not self.statement.strip(): errors['statement'] = 'Renseignez un énoncé non vide.'
        if not isinstance(self.explanation, str) or not self.explanation.strip(): errors['explanation'] = 'Renseignez une explication de correction non vide.'
        choices = {}
        for letter in 'abcd':
            field = 'choice_' + letter
            text = normalized_choice(getattr(self, field))
            if not text: errors[field] = 'Cette proposition ne peut pas être vide.'
            elif text in choices: errors[field] = f'Cette proposition est identique à la proposition {choices[text]} après normalisation des espaces et de la casse.'
            else: choices[text] = letter.upper()
        if errors: raise ValidationError(errors)


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        SUBMITTED = 'SUBMITTED', 'Soumise'
        EXPIRED = 'EXPIRED', 'Expirée'

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name='attempts')
    learning_group = models.ForeignKey(LearningGroup, on_delete=models.PROTECT, related_name='quiz_attempts')
    number = models.PositiveIntegerField()
    quiz_title = models.CharField(max_length=150)
    # Never expose this JSON through a generic model serializer.
    question_snapshot = models.JSONField(default=list)
    started_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=11, choices=Status.choices, default=Status.IN_PROGRESS)
    points_earned = models.PositiveIntegerField(null=True, blank=True)
    total_points = models.PositiveIntegerField()

    class Meta:
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(fields=['student', 'quiz', 'number'], name='unique_student_quiz_attempt_number'),
            models.UniqueConstraint(fields=['student', 'quiz'], condition=models.Q(status='IN_PROGRESS'), name='unique_active_student_quiz_attempt'),
        ]


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.PROTECT, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name='attempt_answers')
    selected_choice = models.CharField(max_length=1, choices=[(x, x) for x in 'ABCD'])
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['attempt', 'question'], name='unique_attempt_question_answer')]


class QuestionImport(models.Model):
    """Receipt only: unconfirmed generated content is never persisted."""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='question_imports')
    key = models.CharField(max_length=36)
    fingerprint = models.CharField(max_length=64)
    question_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['quiz', 'key'], name='unique_quiz_question_import')]


class QuizFeedback(models.Model):
    class Rating(models.TextChoices):
        TOO_EASY = 'TOO_EASY', 'Trop facile'
        SUITABLE = 'SUITABLE', 'Adapté'
        TOO_HARD = 'TOO_HARD', 'Trop difficile'
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name='feedback')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='quiz_feedback')
    rating = models.CharField(max_length=8, choices=Rating.choices)
    comment = models.TextField(max_length=1000, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['quiz', 'student'], name='unique_student_quiz_feedback')]


class QuestionGenerationJob(models.Model):
    """One generation of quiz questions by the local AI, run outside the HTTP request (Celery or a thread).

    The course text is kept only while the job runs, and the proposals only until the teacher first
    retrieves them: as with the synchronous preview, nothing generated is kept until it is confirmed.
    """
    class Status(models.TextChoices):
        QUEUED = 'QUEUED', 'En attente'
        RUNNING = 'RUNNING', 'En cours'
        SUCCEEDED = 'SUCCEEDED', 'Terminée'
        FAILED = 'FAILED', 'Échec'
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='generation_jobs')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_generation_jobs')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    inputs = models.JSONField(default=dict)
    proposals = models.JSONField(default=list)
    delivered = models.BooleanField(default=False)
    error_code = models.CharField(max_length=40, blank=True, default='')
    error_message = models.CharField(max_length=500, blank=True, default='')
    error_status = models.IntegerField(null=True, blank=True)
    error_fields = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=['status', 'created_at'])]
