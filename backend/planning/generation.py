import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as clock
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError
from accounts.models import RateBucket
from accounts.services import limit
from ai.gemini import GeminiError, generate_json, object_schema, array_schema, string_schema
from classrooms.models import LearningGroup
from . import scheduler
from .models import StudyGoal, Deadline, StudyPlan, RevisionTask, LOCAL_TZ, TITLE_MAX_LENGTH
from .services import (active_plan, atomic, availability_windows, closed_attempts, local, local_today, model_errors,
    plan_tasks, quiz_results, task_minutes_by_goal, upcoming_deadlines, weak_group_ids, weekly_minutes)

DAY_SECONDS = 86400
MAX_AI_TASKS = 120
TIME_PATTERN = re.compile(r'([01]\d|2[0-3]):([0-5]\d)(?::00)?')
QUOTA_REASON = 'Quota IA atteint : planning calculé par règles.'
UNAVAILABLE_REASON = 'Service IA indisponible : planning calculé par règles.'
ERROR_REASONS = {
    'quota': QUOTA_REASON,
    'disabled': 'L’IA n’est pas configurée sur ce serveur : planning calculé par règles.',
    'blocked': 'Le service IA a bloqué la demande : planning calculé par règles.',
    'invalid_response': 'La réponse de l’IA était inexploitable : planning calculé par règles.',
}
OUT_OF_WINDOWS_REASON = 'La proposition de l’IA ne respectait pas vos disponibilités : planning calculé par règles.'

SYSTEM_INSTRUCTION = (
    'Tu es un coach de révision bienveillant qui accompagne un étudiant. '
    'À partir des données JSON fournies, propose un programme de révision personnalisé pour la période indiquée. '
    'Utilise UNIQUEMENT les créneaux de disponibilité fournis : chaque tâche tient entièrement dans un seul créneau, le même jour, '
    'et deux tâches ne se chevauchent jamais. '
    'Priorise les échéances proches, les objectifs de priorité haute et les groupes où les résultats de quiz sont faibles. '
    'Propose des tâches de 30 à 120 minutes et laisse des pauses entre les tâches. '
    'Quand une tâche sert un objectif ou une échéance fournis, renseigne goal_id ou deadline_id avec leur identifiant exact. '
    'Réponds uniquement en JSON conforme au schéma. '
    'Le champ advice contient des conseils concrets en français, 1 200 caractères au maximum.'
)

RESPONSE_SCHEMA = object_schema({
    'advice': string_schema('Conseils concrets en français, 1 200 caractères au maximum.'),
    'tasks': array_schema(object_schema({
        'goal_id': string_schema('Identifiant d’un objectif fourni (facultatif).'),
        'deadline_id': string_schema('Identifiant d’une échéance fournie (facultatif).'),
        'title': string_schema('Titre court de la tâche.'),
        'description': string_schema('Ce que l’étudiant fait pendant la séance.'),
        'date': string_schema('Date locale au format AAAA-MM-JJ.'),
        'start': string_schema('Heure locale de début au format HH:MM.'),
        'end': string_schema('Heure locale de fin au format HH:MM.'),
    }, required=['title', 'description', 'date', 'start', 'end']), max_items=MAX_AI_TASKS),
}, required=['advice', 'tasks'])


@dataclass
class PlannerInputs:
    goals: list
    deadlines: list
    done_minutes: dict
    weak_groups: set
    attempts: list
    windows: list
    start_date: date
    end_date: date
    now: datetime


@dataclass
class Outcome:
    generator: str
    tasks: list
    advice: str
    fallback_reason: str = ''
    metrics: dict = field(default_factory=dict)


def planner_inputs(student, start_date, end_date, now):
    done = {goal_id: minutes[1] for goal_id, minutes in task_minutes_by_goal(plan_tasks(active_plan(student))).items()}
    attempts = closed_attempts(student)
    return PlannerInputs(list(StudyGoal.objects.filter(student=student, status=StudyGoal.Status.ACTIVE).order_by('created_at', 'id')),
        list(upcoming_deadlines(student, now)), done, weak_group_ids(student, attempts), attempts,
        availability_windows(student, start_date, end_date, now), start_date, end_date, now)


def course_context(user):
    """Visible courses and their chapter titles, when the optional courses module is installed."""
    if not apps.is_installed('courses'): return False, []
    try:
        from courses.services import visible_courses, course_outline
        courses = [{'title': str(course.title), 'chapters': [str(chapter.get('title', '')) for chapter in course_outline(course.pk)]}
            for course in visible_courses(user)[:20]]
    except Exception:
        # The courses module is optional: its absence or failure must never block planning.
        return False, []
    return True, courses


def ai_context(student, inputs):
    groups = {g.pk: g.name for g in LearningGroup.objects.filter(pk__in=[g.learning_group_id for g in inputs.goals if g.learning_group_id])}
    return {
        'today': local_today(inputs.now).isoformat(),
        'plan': {'start_date': inputs.start_date.isoformat(), 'end_date': inputs.end_date.isoformat()},
        'windows': [{'date': start.date().isoformat(), 'start': start.strftime('%H:%M'), 'end': end.strftime('%H:%M')} for start, end in inputs.windows],
        'goals': [{'id': str(g.pk), 'title': g.title, 'description': g.description[:300], 'priority': g.priority,
            'estimated_hours': g.estimated_hours, 'remaining_minutes': max(0, g.estimated_hours * 60 - inputs.done_minutes.get(g.pk, 0)),
            'target_date': g.target_date.isoformat() if g.target_date else None, 'group': groups.get(g.learning_group_id)} for g in inputs.goals],
        'deadlines': [{'id': str(d.pk), 'title': d.title, 'kind': d.kind, 'due_at': local(d.due_at).isoformat(timespec='minutes'),
            'goal_id': str(d.goal_id) if d.goal_id else None} for d in inputs.deadlines],
        'quiz_results': [{'quiz_title': r['quiz_title'], 'group_name': r['group_name'], 'percent': r['percent'],
            'date': local(r['submitted_at']).date().isoformat()} for r in quiz_results(student, inputs.attempts)],
        'courses': [{'title': c['title'], 'chapters': c['chapters'][:30]} for c in course_context(student)[1]],
    }


def prompt_text(context):
    return ('Voici les données de planification de l’étudiant au format JSON. Les heures sont locales (Africa/Tunis). '
        f'Propose au plus {MAX_AI_TASKS} tâches.\n' + json.dumps(context, ensure_ascii=False))


def fake_response(tasks):
    """Plausible answer for the fake provider: the rule-based tasks expressed in the AI response format."""
    return {'advice': 'Proposition de démonstration (fournisseur IA simulé) : alternez vos objectifs et gardez une pause entre deux séances.',
        'tasks': [{'goal_id': str(t['goal_id'] or ''), 'deadline_id': str(t['deadline_id'] or ''), 'title': t['title'],
            'description': t['description'], 'date': local(t['starts_at']).date().isoformat(),
            'start': local(t['starts_at']).strftime('%H:%M'), 'end': local(t['ends_at']).strftime('%H:%M')} for t in tasks]}


def ai_task(item, windows, goal_ids, deadline_ids):
    if not isinstance(item, dict): return None
    day = item.get('date')
    times = [TIME_PATTERN.fullmatch(item.get(key)) if isinstance(item.get(key), str) else None for key in ('start', 'end')]
    if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) or not all(times): return None
    try: day = date.fromisoformat(day)
    except ValueError: return None
    starts_at, ends_at = (datetime.combine(day, clock(int(m[1]), int(m[2])), tzinfo=LOCAL_TZ) for m in times)
    if not 15 <= (ends_at - starts_at).total_seconds() / 60 <= 240: return None
    if not any(start <= starts_at and ends_at <= end for start, end in windows): return None
    title = scheduler.clip(' '.join(str(item.get('title') or '').split()), TITLE_MAX_LENGTH) or 'Révision'
    return {'title': title, 'description': scheduler.clip(str(item.get('description') or '').strip(), 1000),
        'goal_id': goal_ids.get(str(item.get('goal_id') or '').lower()), 'deadline_id': deadline_ids.get(str(item.get('deadline_id') or '').lower()),
        'starts_at': starts_at, 'ends_at': ends_at, 'source': 'AI'}


def ai_tasks(data, student, windows):
    """Keep the proposals that fit the student's windows; return them with the number dropped."""
    raw = data.get('tasks') if isinstance(data.get('tasks'), list) else []
    goal_ids = {str(pk): pk for pk in StudyGoal.objects.filter(student=student).values_list('id', flat=True)}
    deadline_ids = {str(pk): pk for pk in Deadline.objects.filter(student=student).values_list('id', flat=True)}
    accepted = []
    for item in raw[:MAX_AI_TASKS]:
        task = ai_task(item, windows, goal_ids, deadline_ids)
        # On overlap the first proposal wins.
        if task and not any(task['starts_at'] < t['ends_at'] and t['starts_at'] < task['ends_at'] for t in accepted): accepted.append(task)
    return sorted(accepted, key=lambda t: t['starts_at']), len(raw) - len(accepted)


def quota_hits(scope, identity):
    # Same key as accounts.services.limit, read without counting a hit.
    key = hashlib.sha256(f'{scope}:{identity}:{int(time.time()) // DAY_SECONDS}'.encode()).hexdigest()
    return RateBucket.objects.filter(key=key).values_list('hits', flat=True).first() or 0


def ai_status(user):
    provider = settings.GEMINI_PROVIDER
    configured = provider == 'fake' or (provider == 'gemini' and bool(settings.GEMINI_API_KEY))
    remaining = min(settings.PLANNING_AI_DAILY_LIMIT - quota_hits('planning-ai', str(user.pk)),
        settings.PLANNING_AI_DAILY_BUDGET - quota_hits('planning-ai-global', 'global'))
    return {'provider': provider, 'configured': configured,
        'model': settings.GEMINI_MODEL if provider == 'gemini' else 'fake' if provider == 'fake' else None,
        'remaining_today': max(0, remaining) if configured else 0}


def ai_outcome(request, inputs, rules):
    def fallback(reason, metrics=None):
        return Outcome(StudyPlan.Generator.RULES, rules.tasks, rules.advice, reason, metrics or {})
    try:
        # Per-student quota first, so a throttled student does not spend the shared budget.
        limit(request, 'planning-ai', maximum=settings.PLANNING_AI_DAILY_LIMIT, seconds=DAY_SECONDS, identity=str(request.user.pk))
        limit(request, 'planning-ai-global', maximum=settings.PLANNING_AI_DAILY_BUDGET, seconds=DAY_SECONDS, identity='global')
    except Throttled:
        return fallback(QUOTA_REASON)
    try:
        result = generate_json(SYSTEM_INSTRUCTION, prompt_text(ai_context(request.user, inputs)), RESPONSE_SCHEMA,
            fake=lambda: fake_response(rules.tasks))
    except GeminiError as exc:
        return fallback(ERROR_REASONS.get(exc.code, UNAVAILABLE_REASON), {'provider': settings.GEMINI_PROVIDER[:30]})
    metrics = {'provider': result.provider[:30], 'model_name': result.model[:80], 'latency_ms': result.latency_ms,
        'prompt_tokens': result.prompt_tokens, 'output_tokens': result.output_tokens}
    tasks, dropped = ai_tasks(result.data, request.user, inputs.windows)
    if not tasks: return fallback(OUT_OF_WINDOWS_REASON, metrics)
    reason = '' if not dropped else '1 proposition hors créneaux a été ignorée.' if dropped == 1 else f'{dropped} propositions hors créneaux ont été ignorées.'
    advice = scheduler.clip(str(result.data.get('advice') or '').strip(), scheduler.ADVICE_MAX_LENGTH) or scheduler.overview(tasks)
    return Outcome(StudyPlan.Generator.AI, tasks, advice, reason, metrics)


def default_title(start_date, end_date):
    return f'Planning du {start_date:%d/%m} au {end_date:%d/%m}'


def generate_plan(request, data):
    """Validate, compute (rules or AI with fallback) outside any transaction, then save plan and tasks together."""
    student, now = request.user, timezone.now()
    start_date, end_date = data['start_date'], data['end_date']
    if start_date < local_today(now): raise ValidationError({'start_date': ['Choisissez une date de début à partir d’aujourd’hui.']})
    plan = StudyPlan(student=student, title=data.get('title') or default_title(start_date, end_date), start_date=start_date, end_date=end_date)
    model_errors(plan)
    inputs = planner_inputs(student, start_date, end_date, now)
    if not inputs.goals and not inputs.deadlines:
        raise ValidationError({'detail': 'Ajoutez au moins un objectif en cours ou une échéance avant de générer un planning.'})
    if not inputs.windows: raise ValidationError({'detail': 'Aucune disponibilité sur cette période : ajoutez des créneaux.'})
    tasks, advice = scheduler.rule_plan(inputs.goals, inputs.deadlines, inputs.done_minutes, inputs.weak_groups, inputs.windows, start_date, end_date)
    outcome = Outcome(StudyPlan.Generator.RULES, tasks, advice)
    if data['mode'] == 'ai': outcome = ai_outcome(request, inputs, outcome)
    plan.generator, plan.advice, plan.fallback_reason = outcome.generator, outcome.advice, outcome.fallback_reason[:300]
    for name, value in outcome.metrics.items(): setattr(plan, name, value)
    def write():
        plan.save()
        RevisionTask.objects.bulk_create([RevisionTask(plan=plan, student=student, **task) for task in outcome.tasks])
    atomic(write)
    return plan


def planning_context(user):
    now = timezone.now()
    attempts = closed_attempts(user)
    available, courses = course_context(user)
    return {'goals': StudyGoal.objects.filter(student=user, status=StudyGoal.Status.ACTIVE).count(),
        'deadlines': upcoming_deadlines(user, now).count(), 'weekly_minutes': weekly_minutes(user),
        'quiz_results': quiz_results(user, attempts),
        'weak_groups': sorted(LearningGroup.objects.filter(pk__in=list(weak_group_ids(user, attempts))).values_list('name', flat=True)),
        'courses_available': available, 'courses': [{'title': c['title'], 'chapters': len(c['chapters'])} for c in courses],
        'ai': ai_status(user)}
