from rest_framework import serializers
from accounts.serializers import StrictSerializer
from accounts.models import User
from .models import LearningGroup, Enrollment
from .services import get_object, interval_query

class GroupSerializer(StrictSerializer):
    name = serializers.CharField(max_length=120)
    code = serializers.RegexField(r'^[A-Za-z0-9_-]+$', max_length=30)
    description = serializers.CharField(required=False, allow_blank=True)
    level = serializers.CharField(max_length=80)
    academic_year = serializers.CharField(max_length=30)
    teacher_id = serializers.CharField()
    archived = serializers.BooleanField(required=False)
    def validate(self, data):
        teacher = get_object(User, data.pop('teacher_id'))
        if teacher.role != 'TEACHER' or not teacher.is_active:
            raise serializers.ValidationError({'teacher_id': ['Sélectionnez un enseignant actif.']})
        data['teacher'] = teacher
        data['code'] = data['code'].upper()
        duplicate = LearningGroup.objects.filter(code=data['code'])
        if self.context.get('instance'):
            duplicate = duplicate.exclude(pk=self.context['instance'].pk)
        if duplicate.exists():
            raise serializers.ValidationError({'code': ['Code déjà utilisé.']})
        return data

class EnrollmentSerializer(StrictSerializer):
    student_id = serializers.CharField()
    group_id = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    def validate(self, data):
        student = get_object(User, data.pop('student_id'))
        group = get_object(LearningGroup, data.pop('group_id'))
        if student.role != 'STUDENT' or not student.is_active or group.archived:
            raise serializers.ValidationError('Étudiant inactif, rôle incorrect ou groupe archivé.')
        end = data.get('ends_at')
        if end and end <= data['starts_at']:
            raise serializers.ValidationError({'ends_at': ['La sortie doit suivre l’entrée.']})
        if Enrollment.objects.filter(student=student, group=group).filter(interval_query(data['starts_at'], end)).exists():
            raise serializers.ValidationError('Cette période chevauche une inscription existante.')
        return dict(data, student=student, group=group)

class EndEnrollmentSerializer(StrictSerializer):
    ends_at = serializers.DateTimeField()

def group_data(group):
    return {'id': str(group.pk), 'name': group.name, 'code': group.code, 'description': group.description,
            'level': group.level, 'academic_year': group.academic_year, 'teacher_id': str(group.teacher_id),
            'teacher_name': f'{group.teacher.first_name} {group.teacher.last_name}', 'archived': group.archived,
            'created_at': group.created_at, 'updated_at': group.updated_at}

def enrollment_data(e):
    return {'id': str(e.pk), 'student_id': str(e.student_id), 'student_name': f'{e.student.first_name} {e.student.last_name}',
            'group_id': str(e.group_id), 'group_name': e.group.name, 'starts_at': e.starts_at, 'ends_at': e.ends_at}
