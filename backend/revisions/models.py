from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django_mongodb_backend.fields import ArrayField
from classrooms.models import LearningGroup

TITLE_MAX_LENGTH = 120
SUMMARY_MAX_LENGTH = 20000
MAX_KEY_POINTS = 15
MAX_GLOSSARY = 20
MAX_TAGS = 8
MAX_ILLUSTRATIONS = 12


def copy_title(title):
    suffix = ' (copie)'
    return title[:TITLE_MAX_LENGTH - len(suffix)] + suffix


class RevisionSheet(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        PUBLISHED = 'PUBLISHED', 'Publiée'
        ARCHIVED = 'ARCHIVED', 'Archivée'

    class Color(models.TextChoices):
        INDIGO = 'INDIGO', 'Indigo'
        CORAL = 'CORAL', 'Corail'
        TEAL = 'TEAL', 'Émeraude'
        AMBER = 'AMBER', 'Ambre'
        ROSE = 'ROSE', 'Rose'
        SKY = 'SKY', 'Ciel'

    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    course_label = models.CharField(max_length=120)
    summary = models.TextField(max_length=SUMMARY_MAX_LENGTH, blank=True)
    # [str, ...] and [{"term": str, "definition": str}, ...]; validated by the write serializers.
    key_points = models.JSONField(default=list, blank=True)
    glossary = models.JSONField(default=list, blank=True)
    tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    color = models.CharField(max_length=6, choices=Color.choices, default=Color.INDIGO)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='revision_sheets')
    # Null for a student's personal sheet; required for a teacher's sheet shared with a group.
    learning_group = models.ForeignKey(LearningGroup, on_delete=models.PROTECT, null=True, blank=True, related_name='revision_sheets')
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    pinned = models.BooleanField(default=False)
    ai_generated = models.BooleanField(default=False)
    ai_reviewed = models.BooleanField(default=False)
    ai_model = models.CharField(max_length=80, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    source_name = models.CharField(max_length=255, blank=True)
    illustration_prompt = models.CharField(max_length=600, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['owner', 'status']), models.Index(fields=['learning_group', 'status'])]

    @property
    def personal(self):
        return self.learning_group_id is None

    def clean(self):
        errors = {}
        if not isinstance(self.title, str) or not self.title.strip(): errors['title'] = 'Renseignez un titre non vide.'
        if not isinstance(self.course_label, str) or not self.course_label.strip(): errors['course_label'] = 'Indiquez le cours ou la matière concernée.'
        if self.owner_id:
            if not self.owner.is_active or self.owner.role == 'ADMIN':
                errors['owner'] = 'Sélectionnez un enseignant ou un étudiant actif.'
            elif self.owner.role == 'STUDENT' and self.learning_group_id:
                errors['learning_group'] = 'Une fiche personnelle ne peut pas être partagée avec un groupe.'
            elif self.owner.role == 'TEACHER' and not self.learning_group_id:
                errors['learning_group'] = 'Sélectionnez le groupe auquel la fiche est destinée.'
        if self.learning_group_id and 'learning_group' not in errors:
            if self.learning_group.archived: errors['learning_group'] = 'Le groupe est archivé.'
            elif self.learning_group.teacher_id != self.owner_id:
                errors['learning_group'] = 'Le groupe doit être affecté à l’enseignant propriétaire.'
        if errors: raise ValidationError(errors)


class Illustration(models.Model):
    class Source(models.TextChoices):
        UPLOAD = 'UPLOAD', 'Importée'
        AI = 'AI', 'Générée par IA'

    sheet = models.ForeignKey(RevisionSheet, on_delete=models.PROTECT, related_name='illustrations')
    image = models.ImageField(upload_to='illustrations/')
    caption = models.CharField(max_length=300)
    prompt = models.TextField(max_length=1000, blank=True)
    source = models.CharField(max_length=6, choices=Source.choices, default=Source.UPLOAD)
    ai_model = models.CharField(max_length=120, blank=True)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']
        indexes = [models.Index(fields=['sheet', 'position'])]


class AIJob(models.Model):
    """One AI generation, processed in the background and kept as a measurable record."""
    class Kind(models.TextChoices):
        SUMMARY = 'SUMMARY', 'Résumé'
        ILLUSTRATION = 'ILLUSTRATION', 'Illustration'

    class Status(models.TextChoices):
        QUEUED = 'QUEUED', 'En attente'
        RUNNING = 'RUNNING', 'En cours'
        SUCCEEDED = 'SUCCEEDED', 'Terminée'
        FAILED = 'FAILED', 'Échec'

    kind = models.CharField(max_length=12, choices=Kind.choices)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.QUEUED)
    sheet = models.ForeignKey(RevisionSheet, on_delete=models.SET_NULL, null=True, related_name='ai_jobs')
    sheet_title = models.CharField(max_length=TITLE_MAX_LENGTH)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ai_jobs')
    # Inputs (the source text is erased once the job ends).
    params = models.JSONField(default=dict)
    source_text = models.TextField(blank=True)
    source_name = models.CharField(max_length=255, blank=True)
    # Outcome and measurements.
    engine = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=120, blank=True)
    fallback = models.BooleanField(default=False)
    error = models.CharField(max_length=500, blank=True)
    illustration = models.ForeignKey(Illustration, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    metrics = models.JSONField(default=dict, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    queue_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', 'id']
        indexes = [models.Index(fields=['sheet', 'status']), models.Index(fields=['user', 'created_at']), models.Index(fields=['kind', 'created_at'])]


class SheetProgress(models.Model):
    """How one student reads and revises one shared sheet (views and flashcards mastered)."""
    sheet = models.ForeignKey(RevisionSheet, on_delete=models.CASCADE, related_name='progress')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sheet_progress')
    views = models.PositiveIntegerField(default=0)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    known = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    review_sessions = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['sheet', 'student'], name='unique_sheet_progress')]
