from rest_framework import serializers
from accounts.serializers import StrictSerializer
from classrooms.models import LearningGroup
from classrooms.services import get_object, group_access
from .models import LearningSession, AttendanceSheet

STATUSES = ('UNSET', 'PRESENT', 'ABSENT', 'LATE', 'EXCUSED')
class SessionSerializer(StrictSerializer):
    group_id = serializers.CharField()
    title = serializers.CharField(max_length=180)
    description = serializers.CharField(required=False, allow_blank=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    location = serializers.CharField(max_length=300, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=['PLANNED','COMPLETED','CANCELLED'], required=False)
    def validate(self, data):
        group = get_object(LearningGroup, data.pop('group_id'))
        user = self.context['user']
        if user.role == 'STUDENT':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('La création des séances est réservée aux enseignants et administrateurs.')
        group_access(user, group)
        instance = self.context.get('instance')
        if group.archived and (not instance or instance.group_id != group.pk):
            raise serializers.ValidationError('Ce groupe est archivé.')
        if data['ends_at'] <= data['starts_at']:
            raise serializers.ValidationError({'ends_at': ['La fin doit suivre le début.']})
        if instance and AttendanceSheet.objects.filter(session=instance).exists():
            if group.pk != instance.group_id or data['starts_at'] != instance.starts_at or data['ends_at'] != instance.ends_at:
                raise serializers.ValidationError('Cette séance possède une feuille d’appel ; le groupe et les horaires sont conservés.')
        if data.get('status', instance.status if instance else 'PLANNED') != 'CANCELLED':
            overlap = LearningSession.objects.filter(group=group, starts_at__lt=data['ends_at'], ends_at__gt=data['starts_at']).exclude(status='CANCELLED')
            if instance:
                overlap = overlap.exclude(pk=instance.pk)
            if overlap.exists():
                raise serializers.ValidationError('Une séance de ce groupe occupe déjà ce créneau.')
        return dict(data, group=group)

class EntrySerializer(StrictSerializer):
    student_id = serializers.CharField(max_length=24)
    status = serializers.ChoiceField(choices=STATUSES)
    comment = serializers.CharField(max_length=500, allow_blank=True, required=False, default='')
class SheetSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=0)
    entries = EntrySerializer(many=True)
    validate_sheet = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=500, allow_blank=True, required=False, default='')

def session_data(s):
    return {'id': str(s.pk), 'group_id': str(s.group_id), 'group_name': s.group.name,
            'title': s.title, 'description': s.description, 'starts_at': s.starts_at, 'ends_at': s.ends_at,
            'location': s.location, 'status': s.status, 'creator_id': str(s.creator_id)}

def sheet_data(sheet):
    return {'id': str(sheet.pk), 'session_id': str(sheet.session_id), 'version': sheet.version,
            'validated': sheet.validated, 'entries': [{'student_id': e.student_id, 'student_name': e.student_name,
            'status': e.status, 'comment': e.comment, 'author_id': e.author_id, 'updated_at': e.updated_at} for e in sheet.entries],
            'history': sheet.history}
