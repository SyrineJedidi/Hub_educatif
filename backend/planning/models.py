from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from classrooms.models import LearningGroup

LOCAL_TZ = ZoneInfo('Africa/Tunis')
TITLE_MAX_LENGTH = 120
MAX_SLOTS = 21
MAX_PLAN_DAYS = 28


def blank(value):
    return not isinstance(value, str) or not value.strip()


def clock_minutes(value):
    return value.hour * 60 + value.minute


class StudyGoal(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Faible'
        MEDIUM = 'MEDIUM', 'Moyenne'
        HIGH = 'HIGH', 'Haute'
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'En cours'
        ACHIEVED = 'ACHIEVED', 'Atteint'
        ABANDONED = 'ABANDONED', 'Abandonné'
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='study_goals')
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    description = models.TextField(max_length=1000, blank=True)
    learning_group = models.ForeignKey(LearningGroup, on_delete=models.PROTECT, null=True, blank=True, related_name='study_goals')
    target_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=6, choices=Priority.choices, default=Priority.MEDIUM)
    estimated_hours = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(200)])
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['student', 'status'])]
    def clean(self):
        if blank(self.title): raise ValidationError({'title': 'Renseignez un titre non vide.'})


class Deadline(models.Model):
    class Kind(models.TextChoices):
        EXAM = 'EXAM', 'Examen'
        QUIZ = 'QUIZ', 'Quiz'
        ASSIGNMENT = 'ASSIGNMENT', 'Devoir'
        OTHER = 'OTHER', 'Autre'
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='study_deadlines')
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OTHER)
    due_at = models.DateTimeField()
    goal = models.ForeignKey(StudyGoal, on_delete=models.PROTECT, null=True, blank=True, related_name='deadlines')
    notes = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['student', 'due_at'])]
    def clean(self):
        errors = {}
        if blank(self.title): errors['title'] = 'Renseignez un titre non vide.'
        if self.goal_id and self.goal.student_id != self.student_id: errors['goal'] = 'Sélectionnez un de vos objectifs.'
        if errors: raise ValidationError(errors)


class Availability(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, 'Lundi'
        TUESDAY = 1, 'Mardi'
        WEDNESDAY = 2, 'Mercredi'
        THURSDAY = 3, 'Jeudi'
        FRIDAY = 4, 'Vendredi'
        SATURDAY = 5, 'Samedi'
        SUNDAY = 6, 'Dimanche'
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='study_slots')
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['student', 'weekday'])]
    @property
    def minutes(self):
        return clock_minutes(self.end_time) - clock_minutes(self.start_time)
    def clean(self):
        errors = {}
        for field in ('start_time', 'end_time'):
            value = getattr(self, field)
            if value and (value.minute % 15 or value.second or value.microsecond):
                errors[field] = 'Utilisez des quarts d’heure (00, 15, 30 ou 45 minutes).'
        if not errors and self.start_time and self.end_time:
            if self.minutes <= 0: errors['end_time'] = 'La fin doit suivre le début.'
            elif not 30 <= self.minutes <= 360: errors['end_time'] = 'Un créneau dure entre 30 minutes et 6 heures.'
            else:
                others = Availability.objects.filter(student_id=self.student_id, weekday=self.weekday)
                if self.pk: others = others.exclude(pk=self.pk)
                # Touching slots are allowed: 10:00–12:00 then 12:00–13:00.
                if any(o.start_time < self.end_time and self.start_time < o.end_time for o in others):
                    errors['start_time'] = 'Ce créneau chevauche un autre créneau du même jour.'
        if errors: raise ValidationError(errors)


class StudyPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        ACTIVE = 'ACTIVE', 'Actif'
        ARCHIVED = 'ARCHIVED', 'Archivé'
    class Generator(models.TextChoices):
        AI = 'AI', 'IA (Gemini)'
        RULES = 'RULES', 'Règles'
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='study_plans')
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    generator = models.CharField(max_length=5, choices=Generator.choices, default=Generator.RULES)
    advice = models.TextField(max_length=3000, blank=True)
    fallback_reason = models.CharField(max_length=300, blank=True)
    provider = models.CharField(max_length=30, blank=True)
    model_name = models.CharField(max_length=80, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['student', 'status'])]
        constraints = [models.UniqueConstraint(fields=['student'], condition=models.Q(status='ACTIVE'), name='unique_active_study_plan')]
    def clean(self):
        errors = {}
        if blank(self.title): errors['title'] = 'Renseignez un titre non vide.'
        if self.start_date and self.end_date:
            days = (self.end_date - self.start_date).days + 1
            if days < 1: errors['end_date'] = 'La date de fin doit suivre la date de début.'
            elif days > MAX_PLAN_DAYS: errors['end_date'] = f'Un planning couvre {MAX_PLAN_DAYS} jours au maximum.'
        if errors: raise ValidationError(errors)


class RevisionTask(models.Model):
    class Status(models.TextChoices):
        TODO = 'TODO', 'À faire'
        DONE = 'DONE', 'Terminée'
        SKIPPED = 'SKIPPED', 'Ignorée'
    class Source(models.TextChoices):
        AI = 'AI', 'IA'
        RULES = 'RULES', 'Règles'
        MANUAL = 'MANUAL', 'Manuelle'
    plan = models.ForeignKey(StudyPlan, on_delete=models.PROTECT, related_name='tasks')
    # Denormalised so per-student reads never need a join on the plan.
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='revision_tasks')
    goal = models.ForeignKey(StudyGoal, on_delete=models.PROTECT, null=True, blank=True, related_name='tasks')
    deadline = models.ForeignKey(Deadline, on_delete=models.PROTECT, null=True, blank=True, related_name='tasks')
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    description = models.TextField(max_length=1000, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.TODO)
    source = models.CharField(max_length=6, choices=Source.choices, default=Source.MANUAL)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['plan', 'starts_at']), models.Index(fields=['student', 'starts_at'])]
    @property
    def minutes(self):
        return int((self.ends_at - self.starts_at).total_seconds() // 60)
    def clean(self):
        errors = {}
        if blank(self.title): errors['title'] = 'Renseignez un titre non vide.'
        if self.goal_id and self.goal.student_id != self.student_id: errors['goal'] = 'Sélectionnez un de vos objectifs.'
        if self.deadline_id and self.deadline.student_id != self.student_id: errors['deadline'] = 'Sélectionnez une de vos échéances.'
        if self.starts_at and self.ends_at:
            start, end = self.starts_at.astimezone(LOCAL_TZ), self.ends_at.astimezone(LOCAL_TZ)
            if end <= start: errors['ends_at'] = 'La fin doit suivre le début.'
            elif start.date() != end.date(): errors['ends_at'] = 'Une tâche commence et se termine le même jour.'
            elif not 15 <= self.minutes <= 240: errors['ends_at'] = 'Une tâche dure entre 15 minutes et 4 heures.'
            elif self.plan_id and not self.plan.start_date <= start.date() <= self.plan.end_date:
                errors['starts_at'] = 'Placez la tâche entre les dates du planning.'
            elif self.plan_id:
                others = RevisionTask.objects.filter(plan_id=self.plan_id, starts_at__lt=self.ends_at, ends_at__gt=self.starts_at)
                if self.pk: others = others.exclude(pk=self.pk)
                if others.exists(): errors['starts_at'] = 'Cette tâche chevauche une autre tâche du planning.'
        if errors: raise ValidationError(errors)
