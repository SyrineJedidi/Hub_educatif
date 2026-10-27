import unicodedata
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from classrooms.models import LearningGroup

SUBJECT_CODE_PATTERN = r'^[A-Z0-9][A-Z0-9-]{1,19}$'
SEGMENT_MAX_LENGTH = 20000


def normalized_text(value):
    """Accent-, case- and spacing-insensitive form used for duplicates and search."""
    text = ''.join(c for c in unicodedata.normalize('NFKD', value or '') if not unicodedata.combining(c))
    return ' '.join(text.casefold().split())


class Subject(models.Model):
    name = models.CharField(max_length=80)
    name_key = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=20, unique=True, validators=[RegexValidator(SUBJECT_CODE_PATTERN,
        'Utilisez 2 à 20 lettres majuscules, chiffres ou tirets, en commençant par une lettre ou un chiffre.')])
    description = models.TextField(max_length=1000, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_subjects')
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError({'name': 'Renseignez un nom non vide.'})

    def save(self, *args, **kwargs):
        self.name_key = normalized_text(self.name)[:80]
        super().save(*args, **kwargs)


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        PUBLISHED = 'PUBLISHED', 'Publié'
        ARCHIVED = 'ARCHIVED', 'Archivé'
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='courses')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='courses')
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=2000)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    content_version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['teacher', 'status']), models.Index(fields=['subject', 'status'])]

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance.loaded_subject_id = instance.__dict__.get('subject_id')
        return instance

    def clean(self):
        errors = {}
        if not isinstance(self.title, str) or not self.title.strip(): errors['title'] = 'Renseignez un titre non vide.'
        if not isinstance(self.description, str) or not self.description.strip(): errors['description'] = 'Renseignez une description non vide.'
        if self.teacher_id and (self.teacher.role != 'TEACHER' or not self.teacher.is_active):
            errors['teacher'] = 'Sélectionnez un enseignant actif.'
        # A course may keep a subject archived later, but cannot be moved to one.
        if self.subject_id and self.subject_id != getattr(self, 'loaded_subject_id', None) and self.subject.archived:
            errors['subject'] = 'Cette matière est archivée : choisissez-en une autre.'
        if errors: raise ValidationError(errors)


class CourseGroup(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='group_links')
    group = models.ForeignKey(LearningGroup, on_delete=models.PROTECT, related_name='course_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['course', 'group'], name='unique_course_group')]
        indexes = [models.Index(fields=['group', 'course'])]


class Chapter(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='chapters')
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000, blank=True)
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        constraints = [models.UniqueConstraint(fields=['course', 'position'], name='unique_chapter_position_in_course')]

    def clean(self):
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValidationError({'title': 'Renseignez un titre non vide.'})


class Resource(models.Model):
    class Kind(models.TextChoices):
        PDF = 'PDF', 'Document PDF'
        AUDIO = 'AUDIO', 'Enregistrement audio'
    class ProcessingStatus(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        PROCESSING = 'PROCESSING', 'En cours de traitement'
        READY = 'READY', 'Prêt'
        NO_TEXT = 'NO_TEXT', 'Sans texte exploitable'
        FAILED = 'FAILED', 'Échec du traitement'
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='resources')
    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name='resources')
    kind = models.CharField(max_length=5, choices=Kind.choices)
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000, blank=True)
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    file = models.FileField(upload_to='courses/', max_length=200)
    original_name = models.CharField(max_length=180)
    mime_type = models.CharField(max_length=40)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    language = models.CharField(max_length=8, blank=True)
    processing_status = models.CharField(max_length=10, choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING)
    processing_error = models.CharField(max_length=300, blank=True)
    text_version = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='uploaded_resources')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['chapter', 'position'], name='unique_resource_position_in_chapter'),
            models.UniqueConstraint(fields=['course', 'sha256'], name='unique_resource_file_in_course'),
        ]
        indexes = [models.Index(fields=['course', 'kind']), models.Index(fields=['processing_status'])]

    def clean(self):
        errors = {}
        if not isinstance(self.title, str) or not self.title.strip(): errors['title'] = 'Renseignez un titre non vide.'
        if self.chapter_id and self.course_id and self.chapter.course_id != self.course_id:
            errors['chapter'] = 'Sélectionnez un chapitre de ce cours.'
        if errors: raise ValidationError(errors)


class ResourceSegment(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name='segments')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='+')
    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name='+')
    order = models.PositiveIntegerField()
    text = models.TextField(max_length=SEGMENT_MAX_LENGTH)
    search_text = models.TextField()
    page = models.PositiveIntegerField(null=True, blank=True)
    start_seconds = models.FloatField(null=True, blank=True)
    end_seconds = models.FloatField(null=True, blank=True)
    edited = models.BooleanField(default=False)
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        constraints = [models.UniqueConstraint(fields=['resource', 'order'], name='unique_segment_order')]
        indexes = [models.Index(fields=['course', 'resource'])]


class ProcessingJob(models.Model):
    class Kind(models.TextChoices):
        EXTRACT_PDF = 'EXTRACT_PDF', 'Extraction du texte'
        TRANSCRIBE_AUDIO = 'TRANSCRIBE_AUDIO', 'Transcription audio'
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        RUNNING = 'RUNNING', 'En cours'
        DONE = 'DONE', 'Terminé'
        FAILED = 'FAILED', 'Échec'
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name='jobs')
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.PENDING)
    # True while PENDING or RUNNING; the partial unique index allows one live job per resource.
    active = models.BooleanField(default=True)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    error = models.CharField(max_length=300, blank=True)
    provider = models.CharField(max_length=30, blank=True)
    model_name = models.CharField(max_length=80, blank=True)
    audio_seconds = models.FloatField(null=True, blank=True)
    processing_ms = models.PositiveIntegerField(null=True, blank=True)
    segments_count = models.PositiveIntegerField(null=True, blank=True)
    worker = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resource'], condition=models.Q(active=True), name='unique_active_processing_job')]
        indexes = [models.Index(fields=['status', 'available_at'])]


class ResourceView(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='resource_views')
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name='views')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='+')
    first_viewed_at = models.DateTimeField(default=timezone.now)
    last_viewed_at = models.DateTimeField(default=timezone.now)
    view_count = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['student', 'resource'], name='unique_student_resource_view')]
        indexes = [models.Index(fields=['course', 'student'])]
