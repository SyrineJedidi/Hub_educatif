from collections.abc import Mapping
from datetime import date, time
import re
from rest_framework import serializers
from accounts.serializers import StrictSerializer
from classrooms.models import LearningGroup
from .models import StudyGoal, Deadline, RevisionTask, TITLE_MAX_LENGTH


class PlanningInputSerializer(StrictSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping): raise serializers.ValidationError({'non_field_errors': ['Envoyez un objet JSON.']})
        return super().to_internal_value(data)


class PlanningTextField(serializers.CharField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'blank': 'Ce champ est obligatoire et ne peut pas contenir uniquement des espaces.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez un texte valide.',
        'max_length': 'Limitez ce champ à {max_length} caractères.',
    }

    def to_internal_value(self, data):
        if not isinstance(data, str): self.fail('invalid')
        return super().to_internal_value(data)


class PlanningIntegerField(serializers.IntegerField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez un nombre entier, sans décimale ni notation scientifique.',
        'min_value': 'Saisissez un entier supérieur ou égal à {min_value}.',
        'max_value': 'Saisissez un entier inférieur ou égal à {max_value}.',
        'max_string_length': 'Ce nombre est trop grand.',
    }

    def to_internal_value(self, data):
        if type(data) is not int and not (isinstance(data, str) and re.fullmatch(r'[0-9]+', data.strip())):
            self.fail('invalid')
        return super().to_internal_value(data)


class PlanningChoiceField(serializers.ChoiceField):
    default_error_messages = {
        'required': 'Sélectionnez une valeur.',
        'null': 'Sélectionnez une valeur.',
        'invalid_choice': 'Sélectionnez une valeur autorisée.',
    }


class PlanningReferenceField(PlanningTextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(r'[0-9a-fA-F]{24}', value):
            raise serializers.ValidationError('Sélectionnez une valeur existante dans la liste.')
        return value


class PlanningDateField(serializers.Field):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez une date valide au format AAAA-MM-JJ.',
    }

    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', data): self.fail('invalid')
        try: return date.fromisoformat(data)
        except ValueError: self.fail('invalid')


class PlanningDateTimeField(serializers.DateTimeField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez une date et une heure valides (AAAA-MM-JJTHH:MM).',
        'make_aware': 'Cette date et cette heure n’existent pas dans le fuseau horaire.',
        'overflow': 'Cette date et cette heure sont hors limites.',
        'date': 'Saisissez une date et une heure, pas seulement une date.',
    }

    def to_internal_value(self, value):
        if not isinstance(value, str) or not re.match(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', value): self.fail('invalid')
        value = super().to_internal_value(value)
        # MongoDB keeps milliseconds only.
        return value.replace(microsecond=value.microsecond // 1000 * 1000)


class PlanningTimeField(serializers.Field):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez une heure valide au format HH:MM.',
    }

    def to_internal_value(self, data):
        match = re.fullmatch(r'([01]\d|2[0-3]):([0-5]\d)(?::00)?', data) if isinstance(data, str) else None
        if not match: self.fail('invalid')
        return time(int(match[1]), int(match[2]))


class GoalSerializer(PlanningInputSerializer):
    title = PlanningTextField(max_length=TITLE_MAX_LENGTH)
    description = PlanningTextField(max_length=1000, required=False, allow_blank=True)
    learning_group_id = PlanningReferenceField(required=False, allow_null=True)
    target_date = PlanningDateField(required=False, allow_null=True)
    priority = PlanningChoiceField(choices=StudyGoal.Priority.choices, required=False)
    estimated_hours = PlanningIntegerField(min_value=1, max_value=200, required=False)

class GoalUpdateSerializer(GoalSerializer):
    status = PlanningChoiceField(choices=StudyGoal.Status.choices)

class DeadlineSerializer(PlanningInputSerializer):
    title = PlanningTextField(max_length=TITLE_MAX_LENGTH)
    kind = PlanningChoiceField(choices=Deadline.Kind.choices)
    due_at = PlanningDateTimeField()
    goal_id = PlanningReferenceField(required=False, allow_null=True)
    notes = PlanningTextField(max_length=500, required=False, allow_blank=True)

class SlotSerializer(PlanningInputSerializer):
    weekday = PlanningIntegerField(min_value=0, max_value=6)
    start_time = PlanningTimeField()
    end_time = PlanningTimeField()

class GenerateSerializer(PlanningInputSerializer):
    title = PlanningTextField(max_length=TITLE_MAX_LENGTH, required=False)
    start_date = PlanningDateField()
    end_date = PlanningDateField()
    mode = PlanningChoiceField(choices=[('ai', 'IA (Gemini)'), ('rules', 'Règles')])

class PlanUpdateSerializer(PlanningInputSerializer):
    title = PlanningTextField(max_length=TITLE_MAX_LENGTH)

class TaskSerializer(PlanningInputSerializer):
    title = PlanningTextField(max_length=TITLE_MAX_LENGTH)
    description = PlanningTextField(max_length=1000, required=False, allow_blank=True)
    goal_id = PlanningReferenceField(required=False, allow_null=True)
    deadline_id = PlanningReferenceField(required=False, allow_null=True)
    starts_at = PlanningDateTimeField()
    ends_at = PlanningDateTimeField()

class TaskUpdateSerializer(TaskSerializer):
    status = PlanningChoiceField(choices=RevisionTask.Status.choices)

class EmptyActionSerializer(PlanningInputSerializer):
    pass


def reference(obj):
    return {'id': str(obj.pk), 'title': obj.title} if obj else None


def objects_by_id(model, ids):
    ids = [i for i in set(ids) if i]
    return {o.pk: o for o in model.objects.filter(pk__in=ids)} if ids else {}


def goal_data(goal, minutes=(0, 0), group=None):
    return {'id': str(goal.pk), 'title': goal.title, 'description': goal.description,
        'learning_group': {'id': str(group.pk), 'name': group.name, 'code': group.code} if group else None,
        'target_date': goal.target_date.isoformat() if goal.target_date else None,
        'priority': goal.priority, 'priority_label': goal.get_priority_display(), 'estimated_hours': goal.estimated_hours,
        'status': goal.status, 'status_label': goal.get_status_display(),
        'planned_minutes': minutes[0], 'done_minutes': minutes[1], 'created_at': goal.created_at, 'updated_at': goal.updated_at}


def goals_data(goals, minutes):
    groups = objects_by_id(LearningGroup, [g.learning_group_id for g in goals])
    return [goal_data(g, minutes.get(g.pk, (0, 0)), groups.get(g.learning_group_id)) for g in goals]


def deadline_data(deadline, goal=None):
    return {'id': str(deadline.pk), 'title': deadline.title, 'kind': deadline.kind, 'kind_label': deadline.get_kind_display(),
        'due_at': deadline.due_at, 'goal': reference(goal), 'notes': deadline.notes,
        'created_at': deadline.created_at, 'updated_at': deadline.updated_at}


def deadlines_data(deadlines):
    goals = objects_by_id(StudyGoal, [d.goal_id for d in deadlines])
    return [deadline_data(d, goals.get(d.goal_id)) for d in deadlines]


def slot_data(slot):
    return {'id': str(slot.pk), 'weekday': slot.weekday, 'weekday_label': slot.get_weekday_display(),
        'start_time': slot.start_time.strftime('%H:%M'), 'end_time': slot.end_time.strftime('%H:%M'), 'minutes': slot.minutes}


def task_data(task, goal=None, deadline=None):
    return {'id': str(task.pk), 'plan_id': str(task.plan_id), 'title': task.title, 'description': task.description,
        'goal': reference(goal), 'deadline': reference(deadline), 'starts_at': task.starts_at, 'ends_at': task.ends_at,
        'minutes': task.minutes, 'status': task.status, 'status_label': task.get_status_display(),
        'source': task.source, 'completed_at': task.completed_at}


def tasks_data(tasks):
    goals = objects_by_id(StudyGoal, [t.goal_id for t in tasks])
    deadlines = objects_by_id(Deadline, [t.deadline_id for t in tasks])
    return [task_data(t, goals.get(t.goal_id), deadlines.get(t.deadline_id)) for t in tasks]


def plan_item(plan, tasks=None):
    tasks = list(RevisionTask.objects.filter(plan=plan)) if tasks is None else tasks
    return {'id': str(plan.pk), 'title': plan.title, 'start_date': plan.start_date.isoformat(), 'end_date': plan.end_date.isoformat(),
        'status': plan.status, 'status_label': plan.get_status_display(),
        'generator': plan.generator, 'generator_label': plan.get_generator_display(), 'fallback_reason': plan.fallback_reason,
        'provider': plan.provider, 'model_name': plan.model_name, 'latency_ms': plan.latency_ms,
        'prompt_tokens': plan.prompt_tokens, 'output_tokens': plan.output_tokens,
        'tasks_count': len(tasks), 'done_count': sum(1 for t in tasks if t.status == 'DONE'),
        'planned_minutes': sum(t.minutes for t in tasks), 'activated_at': plan.activated_at,
        'created_at': plan.created_at, 'updated_at': plan.updated_at}


def plan_detail(plan):
    tasks = list(RevisionTask.objects.filter(plan=plan).order_by('starts_at', 'id'))
    return {**plan_item(plan, tasks), 'advice': plan.advice, 'tasks': tasks_data(tasks)}
