from django.conf import settings
from django.db import models
from django_mongodb_backend.models import EmbeddedModel
from django_mongodb_backend.fields import EmbeddedModelArrayField
from classrooms.models import LearningGroup

class LearningSession(models.Model):
    group = models.ForeignKey(LearningGroup, on_delete=models.PROTECT)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=12, choices=[('PLANNED', 'Planifi?e'), ('COMPLETED', 'Termin?e'), ('CANCELLED', 'Annul?e')], default='PLANNED')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['group', 'starts_at', 'ends_at'])]

class Attendance(EmbeddedModel):
    student_id = models.CharField(max_length=24)
    student_name = models.CharField(max_length=210)
    status = models.CharField(max_length=12, default='UNSET')
    comment = models.CharField(max_length=500, blank=True)
    author_id = models.CharField(max_length=24, blank=True)
    updated_at = models.DateTimeField(null=True)

class AttendanceSheet(models.Model):
    session = models.OneToOneField(LearningSession, on_delete=models.PROTECT)
    entries = EmbeddedModelArrayField(Attendance, default=list)
    validated = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    history = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
