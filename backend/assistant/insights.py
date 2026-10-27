"""Teacher analytics per scope and administrator usage, computed in Python over the scope's messages."""
import csv
import math
import re
from collections import Counter
from datetime import datetime, timedelta
from io import StringIO
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateField
from accounts.models import User
from ai.transcription import provider_status as transcription_status
from .llm import provider_status
from .models import AnswerFeedback, AssistantSettings, Message
from .retrieval import normalize
from .services import global_quota

DEFAULT_DAYS = 30
MAX_DAYS = 180
TOP_SOURCES = 10
TOP_UNANSWERED = 20


def date_param(request, name):
    value = request.query_params.get(name)
    if not value: return None
    try: return DateField().run_validation(value)
    except ValidationError: raise ValidationError({name: ['Saisissez une date au format AAAA-MM-JJ.']})


def period(request):
    today = timezone.localdate()
    end = date_param(request, 'to') or today
    start = date_param(request, 'from') or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end: raise ValidationError({'from': ['La date de début doit précéder la date de fin.']})
    if (end - start).days + 1 > MAX_DAYS: raise ValidationError({'to': [f'Choisissez une période de {MAX_DAYS} jours au plus.']})
    return start, end


def bounds(start, end):
    zone = timezone.get_current_timezone()
    return datetime.combine(start, datetime.min.time(), zone), datetime.combine(end + timedelta(days=1), datetime.min.time(), zone)


def percentile(values, rank):
    if not values: return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(rank / 100 * len(ordered)) - 1)]


def ratio(part, whole):
    return round(part / whole, 3) if whole else None


def anonymised(text):
    text = re.sub(r'[\w.+-]+@[\w-]+(\.[\w-]+)+', '[adresse]', text)
    return re.sub(r'\+?\d[\d .-]{6,}\d', '[numéro]', text)


def question_key(text):
    return ' '.join(re.findall(r'[a-z0-9]+', normalize(text)))


def days(start, end):
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def scope_insights(scope, start, end):
    lower, upper = bounds(start, end)
    # Texts stay in the database, except those of the questions listed as unanswered, read below.
    messages = list(Message.objects.filter(source_type=scope.source_type, scope_id=scope.scope_id, created_at__gte=lower,
        created_at__lt=upper).defer('content', 'follow_ups'))
    owners = {m.owner_id for m in messages}
    # Teachers trying the assistant on their own scope are not students.
    students = set(User.objects.filter(pk__in=list(owners), role='STUDENT').values_list('id', flat=True)) if owners else set()
    messages = [m for m in messages if m.owner_id in students]
    questions = [m for m in messages if m.role == Message.Role.USER]
    answers = [m for m in messages if m.role == Message.Role.ASSISTANT]
    answer_for = {a.reply_to_id: a for a in answers}
    statuses = Counter(a.status for a in answers)
    feedback = list(AnswerFeedback.objects.filter(source_type=scope.source_type, scope_id=scope.scope_id, created_at__gte=lower,
        created_at__lt=upper, student_id__in=list(students))) if students else []
    up = sum(1 for f in feedback if f.rating == AnswerFeedback.Rating.UP)
    down = len(feedback) - up
    complete = [a for a in answers if a.status == Message.Status.COMPLETE]
    latencies = [a.latency_ms for a in complete if a.latency_ms is not None]
    per_day = Counter(timezone.localtime(q.created_at).date() for q in questions)
    sources, titles = Counter(), {}
    for answer in complete:
        for citation in {(c.source_kind, c.source_id): c for c in answer.citations or []}.values():
            sources[(citation.source_kind, citation.source_id)] += 1; titles[(citation.source_kind, citation.source_id)] = citation.source_title
    unanswered, samples = Counter(), {}
    refused = [q for q in questions if q.pk in answer_for and answer_for[q.pk].status == Message.Status.OUT_OF_SCOPE]
    texts = dict(Message.objects.filter(pk__in=[q.pk for q in refused]).values_list('id', 'content')) if refused else {}
    for question in sorted(refused, key=lambda m: m.created_at, reverse=True):
        text = texts.get(question.pk, '')
        key = question_key(text)
        if not key: continue
        unanswered[key] += 1
        if key not in samples: samples[key] = anonymised(' '.join(text.split()))[:300]
    return {
        'scope': {'source_type': scope.source_type, 'scope_id': scope.scope_id, 'key': scope.key, 'title': scope.title},
        'period': {'from': start.isoformat(), 'to': end.isoformat()},
        'questions': len(questions),
        'active_students': len({q.owner_id for q in questions}),
        'voice_questions': sum(1 for q in questions if q.input_mode == Message.InputMode.VOICE),
        'voice_share': ratio(sum(1 for q in questions if q.input_mode == Message.InputMode.VOICE), len(questions)),
        'answers_by_status': {status: statuses.get(status, 0) for status in Message.Status.values},
        'satisfaction': ratio(up, up + down),
        'feedback': {'up': up, 'down': down, 'shared': sum(1 for f in feedback if f.shared_with_teacher)},
        'out_of_scope_rate': ratio(statuses.get(Message.Status.OUT_OF_SCOPE, 0), len(answers)),
        'latency_ms': {'p50': percentile(latencies, 50), 'p95': percentile(latencies, 95)},
        'questions_per_day': [{'date': day.isoformat(), 'questions': per_day.get(day, 0)} for day in days(start, end)],
        'top_sources': [{'source_kind': kind, 'source_id': uid, 'title': titles[(kind, uid)], 'count': count}
            for (kind, uid), count in sorted(sources.items(), key=lambda item: (-item[1], titles[item[0]]))[:TOP_SOURCES]],
        'unanswered_questions': [{'question': samples[key], 'count': count}
            for key, count in sorted(unanswered.items(), key=lambda item: (-item[1], item[0]))[:TOP_UNANSWERED]],
        'low_rated_answers': down,
    }


def csv_safe(value):
    # Spreadsheets would run a leading =, +, - or @ as a formula.
    value = '' if value is None else str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


def percent(value):
    return '' if value is None else f'{value * 100:.1f} %'.replace('.', ',')


def insights_csv(data):
    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    row = lambda *values: writer.writerow([csv_safe(v) for v in values])
    row('Assistant pédagogique', data['scope']['title'])
    row('Période', f"{data['period']['from']} au {data['period']['to']}")
    row()
    row('Indicateur', 'Valeur')
    for label, value in [('Questions', data['questions']), ('Étudiants actifs', data['active_students']),
            ('Questions vocales', data['voice_questions']), ('Part des questions vocales', percent(data['voice_share'])),
            ('Réponses sourcées', data['answers_by_status']['COMPLETE']), ('Hors cours', data['answers_by_status']['OUT_OF_SCOPE']),
            ('Échecs', data['answers_by_status']['FAILED']), ('Bloquées', data['answers_by_status']['BLOCKED']),
            ('Taux hors cours', percent(data['out_of_scope_rate'])), ('Satisfaction', percent(data['satisfaction'])),
            ('Retours « À améliorer »', data['low_rated_answers']), ('Latence médiane (ms)', data['latency_ms']['p50'] or ''),
            ('Latence p95 (ms)', data['latency_ms']['p95'] or '')]:
        row(label, value)
    row()
    row('Jour', 'Questions')
    for item in data['questions_per_day']: row(item['date'], item['questions'])
    row()
    row('Source la plus citée', 'Citations')
    for item in data['top_sources']: row(item['title'], item['count'])
    row()
    row('Question restée sans réponse', 'Occurrences')
    for item in data['unanswered_questions']: row(item['question'], item['count'])
    response = HttpResponse('﻿' + output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="assistant-{data["scope"]["source_type"]}-{data["scope"]["scope_id"]}.csv"'
    response['Cache-Control'] = 'private, no-store'
    return response


def admin_usage():
    today = timezone.localdate()
    start = today - timedelta(days=DEFAULT_DAYS - 1)
    lower, upper = bounds(start, today)
    rows = list(Message.objects.filter(created_at__gte=lower, created_at__lt=upper).values_list(
        'role', 'status', 'provider', 'error_code', 'prompt_tokens', 'output_tokens', 'created_at', 'source_type', 'scope_id'))
    per_day = {day: {'date': day.isoformat(), 'questions': 0, 'gemini_calls': 0, 'failures': 0, 'prompt_tokens': 0, 'output_tokens': 0} for day in days(start, today)}
    failures, scopes = Counter(), Counter()
    for role, status, provider, error_code, prompt_tokens, output_tokens, created_at, source_type, scope_id in rows:
        entry = per_day.get(timezone.localtime(created_at).date())
        if entry is None: continue
        if role == Message.Role.USER:
            entry['questions'] += 1; scopes[(source_type, scope_id)] += 1; continue
        if provider and provider != 'disabled': entry['gemini_calls'] += 1
        if status in (Message.Status.FAILED, Message.Status.BLOCKED):
            entry['failures'] += 1; failures[error_code or 'unknown'] += 1
        entry['prompt_tokens'] += prompt_tokens or 0; entry['output_tokens'] += output_tokens or 0
    titles = {}
    for source_type in {s for s, _ in scopes}:
        ids = [i for s, i in scopes if s == source_type]
        titles.update({(source_type, sid): title for sid, title in AssistantSettings.objects.filter(source_type=source_type, scope_id__in=ids).values_list('scope_id', 'scope_title')})
    series = list(per_day.values())
    return {
        'period': {'from': start.isoformat(), 'to': today.isoformat()},
        'days': series,
        'totals': {key: sum(day[key] for day in series) for key in ('questions', 'gemini_calls', 'failures', 'prompt_tokens', 'output_tokens')},
        'failures_by_code': dict(sorted(failures.items(), key=lambda item: (-item[1], item[0]))),
        'top_scopes': [{'scope_key': f'{s}:{i}', 'source_type': s, 'scope_id': i, 'title': titles.get((s, i), ''), 'questions': n}
            for (s, i), n in sorted(scopes.items(), key=lambda item: (-item[1], item[0]))[:10]],
        'providers': {'llm': provider_status(), 'transcription': transcription_status()},
        'limits': {'global_daily_budget': global_quota(), 'daily_questions_per_user': settings.ASSISTANT_DAILY_QUESTIONS,
            'voice_per_hour': settings.ASSISTANT_VOICE_PER_HOUR, 'max_audio_seconds': settings.ASSISTANT_MAX_AUDIO_SECONDS},
    }
