from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django_mongodb_backend.fields import EmbeddedModelArrayField
from django_mongodb_backend.models import EmbeddedModel
from classrooms.models import LearningGroup

DEFAULT_CONVERSATION_TITLE = 'Nouvelle conversation'
NOTE_BODY_MAX_LENGTH = 20000
QUESTION_MAX_LENGTH = 2000
ANSWER_MAX_LENGTH = 8000


class SourceType(models.TextChoices):
    GROUP = 'group', 'Groupe'
    COURSE = 'course', 'Cours'


class Mode(models.TextChoices):
    EXPLICATION = 'EXPLICATION', 'Explication'
    INDICE = 'INDICE', 'Indice'


class AssistantSettings(models.Model):
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    scope_id = models.CharField(max_length=24)
    scope_title = models.CharField(max_length=150, blank=True)
    enabled = models.BooleanField(default=True)
    default_mode = models.CharField(max_length=11, choices=Mode.choices, default=Mode.EXPLICATION)
    allow_mode_choice = models.BooleanField(default=True)
    daily_question_limit = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(200)])
    block_during_quiz = models.BooleanField(default=True)
    suggested_questions = models.JSONField(default=list)
    welcome_message = models.TextField(max_length=500, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source_type', 'scope_id'], name='unique_assistant_settings_scope')]


class TeacherNote(models.Model):
    group = models.ForeignKey(LearningGroup, on_delete=models.PROTECT, related_name='assistant_notes')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assistant_notes')
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=NOTE_BODY_MAX_LENGTH)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Note de cours'
        indexes = [models.Index(fields=['group', 'created_at'])]

    def clean(self):
        errors = {}
        if not isinstance(self.title, str) or not self.title.strip(): errors['title'] = 'Renseignez un titre non vide.'
        if not isinstance(self.body, str) or not self.body.strip(): errors['body'] = 'Renseignez le contenu de la note.'
        if self.group_id:
            if self.group.archived: errors['group'] = 'Le groupe est archivé.'
            elif self.teacher_id != self.group.teacher_id: errors['group'] = 'La note doit appartenir à l’enseignant du groupe.'
        if errors: raise ValidationError(errors)


class ScopeIndex(models.Model):
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    scope_id = models.CharField(max_length=24)
    # Empty when the index must be rebuilt before the next answer.
    content_version = models.CharField(max_length=80, blank=True)
    chunks_count = models.PositiveIntegerField(default=0)
    built_at = models.DateTimeField(null=True, blank=True)
    build_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source_type', 'scope_id'], name='unique_scope_index')]


class KnowledgeChunk(models.Model):
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    scope_id = models.CharField(max_length=24)
    order = models.PositiveIntegerField()
    source_kind = models.CharField(max_length=10)
    source_id = models.CharField(max_length=24)
    source_title = models.CharField(max_length=200)
    chapter_title = models.CharField(max_length=200, blank=True)
    page = models.PositiveIntegerField(null=True, blank=True)
    start_seconds = models.FloatField(null=True, blank=True)
    url = models.CharField(max_length=300, blank=True)
    text = models.TextField(max_length=2000)
    search_text = models.TextField()

    class Meta:
        indexes = [models.Index(fields=['source_type', 'scope_id', 'order'])]


class Conversation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ARCHIVED = 'ARCHIVED', 'Archivée'
        DELETED = 'DELETED', 'Corbeille'
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assistant_conversations')
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    scope_id = models.CharField(max_length=24)
    scope_title = models.CharField(max_length=150)
    title = models.CharField(max_length=120, default=DEFAULT_CONVERSATION_TITLE)
    title_is_custom = models.BooleanField(default=False)
    mode = models.CharField(max_length=11, choices=Mode.choices, default=Mode.EXPLICATION)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    pinned = models.BooleanField(default=False)
    message_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)
    # Expired by a TTL index (migration 0002).
    purge_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['owner', 'status', 'last_message_at'])]


class Citation(EmbeddedModel):
    number = models.PositiveIntegerField()
    source_kind = models.CharField(max_length=10)
    source_id = models.CharField(max_length=24)
    source_title = models.CharField(max_length=200)
    chapter_title = models.CharField(max_length=200, blank=True)
    page = models.PositiveIntegerField(null=True, blank=True)
    start_seconds = models.FloatField(null=True, blank=True)
    url = models.CharField(max_length=300, blank=True)
    excerpt = models.CharField(max_length=310)
    score = models.FloatField(default=0)


class Message(models.Model):
    class Role(models.TextChoices):
        USER = 'USER', 'Question'
        ASSISTANT = 'ASSISTANT', 'Réponse'
    class InputMode(models.TextChoices):
        TEXT = 'TEXT', 'Texte'
        VOICE = 'VOICE', 'Voix'
    class Status(models.TextChoices):
        COMPLETE = 'COMPLETE', 'Réponse'
        OUT_OF_SCOPE = 'OUT_OF_SCOPE', 'Hors cours'
        FAILED = 'FAILED', 'Échec'
        BLOCKED = 'BLOCKED', 'Bloquée'
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT, related_name='messages')
    # Denormalised so that every lookup can be filtered by owner.
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    scope_id = models.CharField(max_length=24)
    role = models.CharField(max_length=9, choices=Role.choices)
    reply_to = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    content = models.TextField(max_length=ANSWER_MAX_LENGTH)
    input_mode = models.CharField(max_length=5, choices=InputMode.choices, default=InputMode.TEXT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETE)
    unsourced = models.BooleanField(default=False)
    client_id = models.CharField(max_length=36, null=True, blank=True)
    has_client_id = models.BooleanField(default=False)
    citations = EmbeddedModelArrayField(Citation, default=list)
    follow_ups = models.JSONField(default=list)
    provider = models.CharField(max_length=20, blank=True)
    model_name = models.CharField(max_length=80, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    retrieval_ms = models.PositiveIntegerField(null=True, blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    top_score = models.FloatField(null=True, blank=True)
    chunks_used = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=30, blank=True)
    purge_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation', 'client_id'], condition=models.Q(has_client_id=True), name='unique_message_client_id')]
        indexes = [models.Index(fields=['conversation', 'created_at']), models.Index(fields=['source_type', 'scope_id', 'role', 'created_at'])]


class AnswerFeedback(models.Model):
    class Rating(models.TextChoices):
        UP = 'UP', 'Utile'
        DOWN = 'DOWN', 'À améliorer'
    class Reason(models.TextChoices):
        INCORRECT = 'INCORRECT', 'Incorrecte'
        HORS_SUJET = 'HORS_SUJET', 'Hors sujet'
        INCOMPLETE = 'INCOMPLETE', 'Incomplète'
        UNCLEAR = 'UNCLEAR', 'Pas claire'
        BAD_SOURCE = 'BAD_SOURCE', 'Source erronée'
        OTHER = 'OTHER', 'Autre'
    class Status(models.TextChoices):
        NEW = 'NEW', 'Nouveau'
        CONFIRMED = 'CONFIRMED', 'Réponse confirmée'
        CORRECTED = 'CORRECTED', 'Correction publiée'
        DISMISSED = 'DISMISSED', 'Classé sans suite'
    message = models.OneToOneField(Message, on_delete=models.PROTECT, related_name='feedback')
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT, related_name='+')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assistant_feedback')
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    scope_id = models.CharField(max_length=24)
    rating = models.CharField(max_length=4, choices=Rating.choices)
    reasons = models.JSONField(default=list)
    comment = models.TextField(max_length=500, blank=True)
    shared_with_teacher = models.BooleanField(default=False)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.NEW)
    teacher_note = models.TextField(max_length=2000, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # Follows the conversation to the trash, so a purged answer leaves no dangling review.
    purge_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Retour sur une réponse'
        indexes = [models.Index(fields=['source_type', 'scope_id', 'shared_with_teacher', 'status'])]


class ValidatedAnswer(models.Model):
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    scope_id = models.CharField(max_length=24)
    question = models.TextField(max_length=QUESTION_MAX_LENGTH)
    answer = models.TextField(max_length=ANSWER_MAX_LENGTH)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    feedback = models.ForeignKey(AnswerFeedback, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['source_type', 'scope_id'])]
