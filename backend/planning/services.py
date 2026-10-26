from datetime import datetime, timedelta
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import DatabaseError
from django.db.models import Q, ProtectedError
from django.utils import timezone
from django_mongodb_backend import transaction
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.fields import ChoiceField
from accounts.models import User
from classrooms.models import Enrollment, LearningGroup
from classrooms.services import Conflict, get_object
from quizzes.models import Attempt
from .models import StudyGoal, Deadline, Availability, StudyPlan, RevisionTask, LOCAL_TZ, MAX_SLOTS
from .serializers import (GoalSerializer, GoalUpdateSerializer, DeadlineSerializer, SlotSerializer,
    TaskSerializer, TaskUpdateSerializer, deadlines_data, tasks_data, plan_item, plan_detail)

WEAK_PERCENT = 60
QUARTER = timedelta(minutes=15)
FIELD_NAMES = {'learning_group': 'learning_group_id', 'goal': 'goal_id', 'deadline': 'deadline_id', '__all__': 'non_field_errors'}


def mongo_now():
    now = timezone.now()
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def local(moment):
    return moment.astimezone(LOCAL_TZ)


def local_today(now=None):
    return local(now or timezone.now()).date()


def model_errors(instance):
    try: instance.full_clean(validate_unique=False, validate_constraints=False)
    except ModelValidationError as exc:
        errors = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
        raise ValidationError({FIELD_NAMES.get(k, k): v for k, v in errors.items()})


def own(model, student, uid, message):
    obj = get_object(model, uid)
    if obj.student_id != student.pk: raise NotFound(message)
    return obj


def atomic(function, *args):
    """Short multi-document write; a write conflict becomes a 409 instead of a 500."""
    try:
        with transaction.atomic():
            return function(*args)
    except DatabaseError:
        raise Conflict()


def checked(cls, data, partial):
    serializer = cls(data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def current_group_ids(student, now=None):
    # Same current-period rule as the quizzes: start included, end excluded, archived groups ignored.
    now = now or timezone.now()
    ids = list(Enrollment.objects.filter(student=student, starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('group_id', flat=True))
    return list(LearningGroup.objects.filter(pk__in=ids, archived=False).values_list('id', flat=True))


def current_groups(student):
    return LearningGroup.objects.filter(pk__in=current_group_ids(student)).order_by('name', 'id')


def owned_reference(model, student, uid, field, message):
    if uid is None: return None
    try: return own(model, student, uid, message)
    except NotFound: raise ValidationError({field: [message]})


def goal_values(student, data, instance=None):
    attrs = checked(GoalUpdateSerializer if instance else GoalSerializer, data, bool(instance))
    goal = instance or StudyGoal(student=student)
    if 'learning_group_id' in attrs:
        group_id = attrs.pop('learning_group_id')
        if group_id is None: goal.learning_group = None
        elif not instance or group_id.lower() != str(instance.learning_group_id):
            message = 'Sélectionnez un groupe dans lequel vous êtes inscrit actuellement.'
            try: group = get_object(LearningGroup, group_id)
            except NotFound: raise ValidationError({'learning_group_id': [message]})
            if group.pk not in current_group_ids(student): raise ValidationError({'learning_group_id': [message]})
            goal.learning_group = group
    for field, value in attrs.items(): setattr(goal, field, value)
    model_errors(goal)
    return goal


def deadline_values(student, data, instance=None):
    attrs = checked(DeadlineSerializer, data, bool(instance))
    deadline = instance or Deadline(student=student)
    if 'goal_id' in attrs:
        deadline.goal = owned_reference(StudyGoal, student, attrs.pop('goal_id'), 'goal_id', 'Sélectionnez un de vos objectifs.')
    if 'due_at' in attrs and (not instance or attrs['due_at'] != instance.due_at) and attrs['due_at'] <= timezone.now():
        raise ValidationError({'due_at': ['Choisissez une échéance dans le futur.']})
    for field, value in attrs.items(): setattr(deadline, field, value)
    model_errors(deadline)
    return deadline


def slot_values(student, data, instance=None):
    attrs = checked(SlotSerializer, data, bool(instance))
    if not instance and Availability.objects.filter(student=student).count() >= MAX_SLOTS:
        raise ValidationError({'detail': f'Vous avez atteint la limite de {MAX_SLOTS} créneaux hebdomadaires.'})
    slot = instance or Availability(student=student)
    for field, value in attrs.items(): setattr(slot, field, value)
    model_errors(slot)
    return slot


def writable(plan):
    if plan.status == StudyPlan.Status.ARCHIVED: raise ValidationError({'status': ['Ce planning est archivé.']})


def task_values(student, plan, data, instance=None):
    writable(plan)
    attrs = checked(TaskUpdateSerializer if instance else TaskSerializer, data, bool(instance))
    task = instance or RevisionTask(plan=plan, student_id=plan.student_id, source=RevisionTask.Source.MANUAL)
    if 'goal_id' in attrs:
        task.goal = owned_reference(StudyGoal, student, attrs.pop('goal_id'), 'goal_id', 'Sélectionnez un de vos objectifs.')
    if 'deadline_id' in attrs:
        task.deadline = owned_reference(Deadline, student, attrs.pop('deadline_id'), 'deadline_id', 'Sélectionnez une de vos échéances.')
    if 'status' in attrs:
        if plan.status != StudyPlan.Status.ACTIVE: raise ValidationError({'status': ['Activez le planning pour suivre vos tâches.']})
        status = attrs.pop('status')
        if status != RevisionTask.Status.DONE: task.completed_at = None
        elif task.status != RevisionTask.Status.DONE or not task.completed_at: task.completed_at = mongo_now()
        task.status = status
    for field, value in attrs.items(): setattr(task, field, value)
    model_errors(task)
    return task


def active_plan(student):
    return StudyPlan.objects.filter(student=student, status=StudyPlan.Status.ACTIVE).first()


def plan_tasks(plan):
    return list(RevisionTask.objects.filter(plan=plan).order_by('starts_at', 'id')) if plan else []


def activate_plan(plan):
    if plan.status != StudyPlan.Status.DRAFT:
        writable(plan)
        raise ValidationError({'status': ['Ce planning est déjà actif.']})
    now = mongo_now()
    def write():
        # Archive first: the partial unique index allows one ACTIVE plan per student at every step.
        StudyPlan.objects.filter(student_id=plan.student_id, status=StudyPlan.Status.ACTIVE).exclude(pk=plan.pk).update(status=StudyPlan.Status.ARCHIVED, updated_at=now)
        if not StudyPlan.objects.filter(pk=plan.pk, status=StudyPlan.Status.DRAFT).update(status=StudyPlan.Status.ACTIVE, activated_at=now, updated_at=now):
            raise Conflict()
    atomic(write)
    plan.refresh_from_db()


def archive_plan(plan):
    writable(plan)
    if not StudyPlan.objects.filter(pk=plan.pk, status=plan.status).update(status=StudyPlan.Status.ARCHIVED, updated_at=mongo_now()):
        raise Conflict()
    plan.refresh_from_db()


def delete_plan(plan):
    if plan.status == StudyPlan.Status.ACTIVE: raise ValidationError({'detail': 'Archivez d’abord ce planning.'})
    def write():
        # Explicit single-collection deletes: the MongoDB backend does not support joined deletes.
        RevisionTask.objects.filter(plan=plan).delete()
        plan.delete()
    atomic(write)


def delete_goal(goal):
    message = 'Cet objectif est utilisé par des tâches : marquez-le « Abandonné » plutôt que de le supprimer.'
    if RevisionTask.objects.filter(goal=goal).exists(): raise ValidationError({'detail': message})
    def write():
        Deadline.objects.filter(goal=goal).update(goal=None, updated_at=mongo_now())
        # A task created meanwhile still protects the goal; raising rolls the deadline update back.
        try: goal.delete()
        except ProtectedError: raise ValidationError({'detail': message})
    atomic(write)


def delete_deadline(deadline):
    def write():
        RevisionTask.objects.filter(deadline=deadline).update(deadline=None, updated_at=mongo_now())
        deadline.delete()
    atomic(write)


def next_quarter(moment):
    moment = local(moment)
    hour = moment.replace(minute=0, second=0, microsecond=0)
    return hour + -((hour - moment) // QUARTER) * QUARTER


def availability_windows(student, start_date, end_date, now=None):
    """Concrete local windows for each date of the range, cut to the next quarter hour when already started."""
    now = now or timezone.now()
    slots = list(Availability.objects.filter(student=student).order_by('weekday', 'start_time', 'id'))
    windows, day = [], start_date
    while day <= end_date:
        for slot in slots:
            if slot.weekday != day.weekday(): continue
            start = datetime.combine(day, slot.start_time, tzinfo=LOCAL_TZ)
            end = datetime.combine(day, slot.end_time, tzinfo=LOCAL_TZ)
            if start < now: start = next_quarter(now)
            if end - start >= QUARTER: windows.append((start, end))
        day += timedelta(days=1)
    return sorted(windows)


def task_minutes_by_goal(tasks):
    totals = {}
    for task in tasks:
        if not task.goal_id: continue
        planned, done = totals.get(task.goal_id, (0, 0))
        totals[task.goal_id] = (planned + task.minutes, done + (task.minutes if task.status == RevisionTask.Status.DONE else 0))
    return totals


def goal_minutes(student):
    """Planned and done minutes per goal, counted in the student's ACTIVE plan."""
    return task_minutes_by_goal(plan_tasks(active_plan(student)))


def progress(tasks, now=None):
    now = now or timezone.now()
    counts = {'done': 0, 'skipped': 0, 'todo': 0, 'overdue': 0}
    planned = done_minutes = 0
    for task in tasks:
        planned += task.minutes
        if task.status == RevisionTask.Status.DONE: counts['done'] += 1; done_minutes += task.minutes
        elif task.status == RevisionTask.Status.SKIPPED: counts['skipped'] += 1
        elif task.ends_at < now: counts['overdue'] += 1
        else: counts['todo'] += 1
    closed = counts['done'] + counts['skipped'] + counts['overdue']
    return {**counts, 'planned_minutes': planned, 'done_minutes': done_minutes,
        'completion_rate': round(100 * counts['done'] / closed) if closed else None}


def streak_days(student, now=None):
    days = {local(start).date() for start in RevisionTask.objects.filter(student=student, status=RevisionTask.Status.DONE).values_list('starts_at', flat=True)}
    day = local_today(now)
    if day not in days: day -= timedelta(days=1)
    streak = 0
    while day in days: streak += 1; day -= timedelta(days=1)
    return streak


def upcoming_deadlines(student, now=None):
    return Deadline.objects.filter(student=student, due_at__gt=now or timezone.now()).order_by('due_at', 'id')


def dashboard_data(student, now=None):
    now = now or timezone.now()
    plan = active_plan(student)
    tasks = plan_tasks(plan)
    today = local_today(now)
    minutes = task_minutes_by_goal(tasks)
    shown = Q(status=StudyGoal.Status.ACTIVE) | Q(pk__in=list(minutes)) if minutes else Q(status=StudyGoal.Status.ACTIVE)
    goals = StudyGoal.objects.filter(student=student).filter(shown).order_by('created_at', 'id')
    return {'active_plan': plan_item(plan, tasks) if plan else None,
        'today': tasks_data([t for t in tasks if local(t.starts_at).date() == today]),
        'upcoming': tasks_data([t for t in tasks if today < local(t.starts_at).date() <= today + timedelta(days=7)]),
        'progress': progress(tasks, now), 'streak_days': streak_days(student, now),
        'next_deadlines': deadlines_data(list(upcoming_deadlines(student, now)[:3])),
        'goals': [{'id': str(g.pk), 'title': g.title, 'planned_minutes': minutes.get(g.pk, (0, 0))[0], 'done_minutes': minutes.get(g.pk, (0, 0))[1]} for g in goals]}


def attempt_percent(attempt):
    if attempt.points_earned is None or not attempt.total_points: return None
    return round(100 * attempt.points_earned / attempt.total_points, 1)


def closed_attempts(student):
    attempts = Attempt.objects.filter(student=student, status__in=[Attempt.Status.SUBMITTED, Attempt.Status.EXPIRED])
    return sorted(attempts, key=lambda a: (a.ended_at or a.started_at, str(a.pk)), reverse=True)


def quiz_results(student, attempts=None, size=20):
    attempts = closed_attempts(student) if attempts is None else attempts
    groups = {g.pk: g.name for g in LearningGroup.objects.filter(pk__in=list({a.learning_group_id for a in attempts[:size]}))}
    return [{'quiz_title': a.quiz_title, 'group_name': groups.get(a.learning_group_id, ''), 'percent': attempt_percent(a),
        'submitted_at': a.ended_at or a.started_at} for a in attempts[:size]]


def weak_group_ids(student, attempts=None):
    """Groups whose latest closed attempt scored under 60 %."""
    latest = {}
    for attempt in closed_attempts(student) if attempts is None else attempts:
        latest.setdefault(attempt.learning_group_id, attempt)
    return {gid for gid, a in latest.items() if a.total_points and a.points_earned is not None and 100 * a.points_earned < WEAK_PERCENT * a.total_points}


def weekly_minutes(student):
    return sum(slot.minutes for slot in Availability.objects.filter(student=student))


def coach_student_ids(user, group=None, now=None):
    """Students a coach may follow; None means every student (administrator without a group filter)."""
    if user.role == 'ADMIN' and group is None: return None
    now = now or timezone.now()
    groups = [group.pk] if group else list(LearningGroup.objects.filter(teacher=user, archived=False).values_list('id', flat=True))
    return set(Enrollment.objects.filter(group_id__in=groups, starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('student_id', flat=True))


def coach_group(user, uid):
    group = get_object(LearningGroup, uid)
    if user.role != 'ADMIN' and (group.teacher_id != user.pk or group.archived): raise NotFound('Groupe introuvable.')
    return group


def coached_student(user, uid):
    student = get_object(User, uid)
    ids = coach_student_ids(user)
    if student.role != 'STUDENT' or (ids is not None and student.pk not in ids): raise NotFound('Élève introuvable.')
    return student


def coach_students(request):
    group = coach_group(request.user, request.query_params['group']) if request.query_params.get('group') else None
    students = User.objects.filter(role='STUDENT')
    ids = coach_student_ids(request.user, group)
    if ids is not None: students = students.filter(pk__in=list(ids))
    search = request.query_params.get('q', '').strip()[:100]
    for word in search.split():
        students = students.filter(Q(first_name__icontains=word) | Q(last_name__icontains=word))
    return students.order_by('last_name', 'first_name', 'id')


def person_data(user):
    return {'id': str(user.pk), 'first_name': user.first_name, 'last_name': user.last_name}


def coach_groups_data(coach, student):
    groups = LearningGroup.objects.filter(pk__in=current_group_ids(student))
    if coach.role != 'ADMIN': groups = groups.filter(teacher=coach)
    return [{'id': str(g.pk), 'name': g.name} for g in groups.order_by('name', 'id')]


def coach_row(coach, student, now=None):
    now = now or timezone.now()
    plan = active_plan(student)
    last = RevisionTask.objects.filter(student=student, status=RevisionTask.Status.DONE, completed_at__isnull=False).order_by('-completed_at', 'id').first()
    deadline = upcoming_deadlines(student, now).first()
    return {'student': person_data(student), 'groups': coach_groups_data(coach, student),
        'active_plan': {'id': str(plan.pk), 'title': plan.title, 'start_date': plan.start_date.isoformat(), 'end_date': plan.end_date.isoformat()} if plan else None,
        'progress': progress(plan_tasks(plan), now), 'last_done_at': last.completed_at if last else None,
        'next_deadline': {'title': deadline.title, 'due_at': deadline.due_at} if deadline else None}


def coach_detail(coach, student, now=None):
    now = now or timezone.now()
    plan = active_plan(student)
    tasks = plan_tasks(plan)
    minutes = task_minutes_by_goal(tasks)
    goals = StudyGoal.objects.filter(student=student).order_by('created_at', 'id')
    return {'student': person_data(student), 'groups': coach_groups_data(coach, student),
        'progress': progress(tasks, now), 'streak_days': streak_days(student, now),
        'goals': [{'id': str(g.pk), 'title': g.title, 'priority': g.priority, 'priority_label': g.get_priority_display(),
            'status': g.status, 'status_label': g.get_status_display(),
            'planned_minutes': minutes.get(g.pk, (0, 0))[0], 'done_minutes': minutes.get(g.pk, (0, 0))[1]} for g in goals],
        'deadlines': [{'id': str(d.pk), 'title': d.title, 'kind_label': d.get_kind_display(), 'due_at': d.due_at} for d in upcoming_deadlines(student, now)],
        'active_plan': plan_detail(plan) if plan else None}


def filtered_plans(request):
    plans = StudyPlan.objects.filter(student=request.user)
    status = request.query_params.get('status')
    if status: plans = plans.filter(status=ChoiceField(choices=StudyPlan.Status.choices).run_validation(status))
    return plans.order_by('-created_at', 'id')


def student_goals(request):
    goals = StudyGoal.objects.filter(student=request.user)
    status = request.query_params.get('status')
    if status: goals = goals.filter(status=ChoiceField(choices=StudyGoal.Status.choices).run_validation(status))
    return list(goals.order_by('-created_at', 'id'))


def student_deadlines(request):
    deadlines = Deadline.objects.filter(student=request.user)
    upcoming = request.query_params.get('upcoming')
    if upcoming not in (None, '', 'true', 'false'): raise ValidationError({'upcoming': ['Utilisez true ou false.']})
    if upcoming == 'true': deadlines = deadlines.filter(due_at__gt=timezone.now())
    return list(deadlines.order_by('due_at', 'id'))
