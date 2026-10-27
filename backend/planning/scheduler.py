"""Deterministic rule-based planner. It is also the fallback whenever an AI proposal cannot be kept."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import ceil
from .models import LOCAL_TZ, TITLE_MAX_LENGTH

PRIORITY_WEIGHT = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
BLOCK_MINUTES = 60
MIN_BLOCK_MINUTES = 30
DEADLINE_DEMAND_MINUTES = 120
ADVICE_MAX_LENGTH = 3000


def clip(text, size):
    return text if len(text) <= size else text[:size - 1].rstrip() + '…'


def duration(minutes):
    hours, rest = divmod(int(minutes), 60)
    if not hours: return f'{rest} min'
    return f'{hours} h {rest:02d}' if rest else f'{hours} h'


def plural(count, singular, several):
    return f'{count} {singular if count == 1 else several}'


def local_moment(moment):
    return moment.astimezone(LOCAL_TZ)


@dataclass
class Demand:
    name: str
    title: str
    weight: int
    minutes: int
    due: datetime | None
    due_day: date | None
    order: str
    goal_id: object = None
    deadline_id: object = None
    note: str = ''
    weak: bool = False
    planned: int = 0

    @property
    def left(self):
        return self.minutes - self.planned


def urgency(due_day, start_date, end_date):
    if due_day is None: return 0
    if (due_day - start_date).days <= 3: return 3
    return 2 if due_day <= end_date else 0


def deadline_note(deadline):
    moment = local_moment(deadline.due_at)
    return f'Échéance « {deadline.title} » ({deadline.get_kind_display().lower()}) le {moment:%d/%m} à {moment:%H} h {moment:%M}.'


def demands(goals, deadlines, done_minutes, weak_groups, start_date, end_date):
    """goals: ACTIVE goals; deadlines: upcoming deadlines sorted by due_at; done_minutes: per goal, in the ACTIVE plan."""
    first_deadline = {}
    for deadline in deadlines:
        if deadline.goal_id: first_deadline.setdefault(deadline.goal_id, deadline)
    items = []
    for goal in goals:
        deadline = first_deadline.get(goal.pk)
        cutoffs = []
        if deadline: cutoffs.append((deadline.due_at, local_moment(deadline.due_at).date()))
        if goal.target_date: cutoffs.append((datetime.combine(goal.target_date + timedelta(days=1), time(0), tzinfo=LOCAL_TZ), goal.target_date))
        due, due_day = min(cutoffs) if cutoffs else (None, None)
        weak = goal.learning_group_id in weak_groups
        notes = [deadline_note(deadline)] if deadline else []
        if goal.target_date: notes.append(f'Date cible de l’objectif : {goal.target_date:%d/%m}.')
        if weak: notes.append('Dernier résultat de quiz du groupe sous 60 % : reprenez en priorité les notions fragiles.')
        items.append(Demand(goal.title, clip(f'Réviser : {goal.title}', TITLE_MAX_LENGTH),
            PRIORITY_WEIGHT.get(goal.priority, 2) + (1 if weak else 0) + urgency(due_day, start_date, end_date),
            max(0, goal.estimated_hours * 60 - done_minutes.get(goal.pk, 0)), due, due_day, str(goal.pk),
            goal_id=goal.pk, deadline_id=deadline.pk if deadline else None, note=' '.join(notes), weak=weak))
    for deadline in deadlines:
        # A deadline linked to a goal is prepared through that goal.
        if deadline.goal_id: continue
        due_day = local_moment(deadline.due_at).date()
        items.append(Demand(deadline.title, clip(f'Préparer : {deadline.title}', TITLE_MAX_LENGTH),
            PRIORITY_WEIGHT['MEDIUM'] + urgency(due_day, start_date, end_date), DEADLINE_DEMAND_MINUTES,
            deadline.due_at, due_day, str(deadline.pk), deadline_id=deadline.pk, note=deadline_note(deadline)))
    return items


def fill(items, windows):
    """Fill windows chronologically, one block at a time, with the most urgent demand still open."""
    tasks = []
    for start, end in windows:
        cursor = start
        while end - cursor >= timedelta(minutes=MIN_BLOCK_MINUTES):
            minutes = min(BLOCK_MINUTES, int((end - cursor).total_seconds() // 60))
            block_end = cursor + timedelta(minutes=minutes)
            open_items = [i for i in items if i.left > 0 and (i.due is None or i.due >= block_end)]
            # Blocks only move forward in time, so nothing can become eligible again.
            if not open_items: return tasks
            item = min(open_items, key=lambda i: (-i.weight, i.due is None, i.due or block_end, i.name.casefold(), i.order))
            if item.left < minutes: minutes = max(MIN_BLOCK_MINUTES, ceil(item.left / 15) * 15)
            block_end = cursor + timedelta(minutes=minutes)
            tasks.append({'title': item.title, 'description': item.note, 'goal_id': item.goal_id, 'deadline_id': item.deadline_id,
                'starts_at': cursor, 'ends_at': block_end, 'source': 'RULES'})
            item.planned += minutes
            cursor = block_end
    return tasks


def overview(tasks):
    total = sum(int((t['ends_at'] - t['starts_at']).total_seconds() // 60) for t in tasks)
    return f'{plural(len(tasks), "séance de révision prévue", "séances de révision prévues")}, {duration(total)} au total.'


def advice(items, tasks, windows, end_date):
    if not windows:
        return 'Aucune disponibilité sur cette période : ajoutez des créneaux pour planifier vos révisions.'
    if tasks: lines = [overview(tasks)]
    elif not any(i.minutes for i in items): lines = ['Vos objectifs en cours sont déjà couverts par les séances réalisées : rien à planifier.']
    else: lines = ['Aucune séance n’a pu être placée avant vos échéances : ajoutez des créneaux plus tôt dans la période.']
    for item in sorted((i for i in items if i.planned), key=lambda i: (-i.planned, i.name.casefold(), i.order)):
        lines.append(f'• {item.name} — temps planifié : {duration(item.planned)}.')
    for item in items:
        if item.weak and item.planned: lines.append(f'Priorité renforcée pour « {item.name} » : votre dernier quiz du groupe est sous 60 %.')
    for item in items:
        if item.left > 0 and item.due_day and item.due_day <= end_date:
            lines.append(f'Temps disponible insuffisant pour « {item.name} » avant le {item.due_day:%d/%m} : il manque {ceil(item.left / 60)} h.')
    lines.append('Conseil : faites une courte pause entre deux séances et terminez chaque séance par un rappel actif de ce que vous avez revu.')
    return clip('\n'.join(lines), ADVICE_MAX_LENGTH)


def rule_plan(goals, deadlines, done_minutes, weak_groups, windows, start_date, end_date):
    items = demands(goals, deadlines, done_minutes, weak_groups, start_date, end_date)
    tasks = fill(items, windows)
    return tasks, advice(items, tasks, windows, end_date)
