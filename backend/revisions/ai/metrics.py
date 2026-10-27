"""Measurements of AI generations: per-job quality checks and dashboard aggregates.

Summaries are generative output with no ground truth, so quality is estimated with
transparent, reproducible proxies (keyword coverage, compression, structure and length
conformity) combined with the human signals of the application (review, rating).
"""
import re
import unicodedata
from collections import Counter
from datetime import timedelta
from django.utils import timezone

STOPWORDS = set('''
alors aussi autre avant avec avoir bien cela celle celles celui ceux cette chaque comme comment dans depuis
donc elle elles encore entre est etaient etait etre ensuite fait font hors leur leurs mais meme moins notre nous
plus pour pourquoi quand quel quelle quelles quels sans selon sera sont sous tous tout toute toutes tres une
vers votre vous ainsi apres chez dont ceci elles lorsque lors parce peut peuvent plusieurs premier premiere
deux trois grand grande grandes grands ensemble partie cours chapitre exemple notamment egalement cependant
'''.split())
LENGTH_TARGETS = {'SHORT': (150, 250, 4, 6), 'STANDARD': (350, 550, 6, 9), 'DETAILED': (700, 1000, 8, 12)}


def target_words(length, source_words):
    """Requested summary length in words, shrunk for short sources (about 30–60 % of them)."""
    low, high = LENGTH_TARGETS[length][:2]
    if source_words and source_words < low * 2:
        low, high = max(40, int(source_words * 0.3)), max(60, int(source_words * 0.6))
    return low, high


def _norm(text):
    text = unicodedata.normalize('NFKD', text.casefold())
    return ''.join(c for c in text if not unicodedata.combining(c))


def _words(text):
    return re.findall(r"[a-z0-9]+", _norm(text))


def keywords(text, limit=15):
    counts = Counter(w for w in _words(text) if len(w) >= 5 and w not in STOPWORDS and not w.isdigit())
    return [w for w, _ in counts.most_common(limit)]


def summary_quality(source, result, length):
    """Return reproducible quality indicators for one generated summary."""
    produced = ' '.join([result['summary'], *result['key_points'], *(f"{g['term']} {g['definition']}" for g in result['glossary'])])
    produced_words = set(_words(produced))
    # A source keyword counts as covered when a produced word shares its first 6 letters
    # (tolerates French inflections: « mitochondrie » / « mitochondries »).
    stems = {w[:6] for w in produced_words}
    terms = keywords(source)
    covered = [t for t in terms if t in produced_words or t[:6] in stems]
    source_words, summary_words = len(_words(source)), len(_words(result['summary']))
    low, high = target_words(length, len(_words(source)))
    points_low, points_high = LENGTH_TARGETS[length][2:]
    checks = {
        'has_sections': bool(re.search(r'^#{1,4}\s', result['summary'], re.M)),
        'key_points_in_range': points_low <= len(result['key_points']) <= points_high,
        'has_glossary': bool(result['glossary']),
        # ±25 % tolerance around the requested length.
        'length_in_range': low * 0.75 <= summary_words <= high * 1.25,
        'has_illustration_idea': bool(result.get('illustration_prompt')),
    }
    return {
        'source_words': source_words,
        'summary_words': summary_words,
        'compression': round(summary_words / source_words, 3) if source_words else None,
        'keyword_coverage': round(len(covered) / len(terms), 3) if terms else None,
        'keywords_missing': [t for t in terms if t not in covered][:8],
        'key_points': len(result['key_points']),
        'glossary_terms': len(result['glossary']),
        'checks': checks,
        'structure_score': round(sum(checks.values()) / len(checks), 3),
    }


def _percentile(values, ratio):
    if not values: return None
    values = sorted(values)
    return values[min(len(values) - 1, int(round(ratio * (len(values) - 1))))]


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def dashboard(jobs, sheets, days=30):
    """Aggregate AI jobs (already scoped by the caller) for the monitoring page."""
    since = timezone.now() - timedelta(days=days)
    jobs = list(jobs.filter(created_at__gte=since))
    finished = [j for j in jobs if j.status in ('SUCCEEDED', 'FAILED')]
    succeeded = [j for j in finished if j.status == 'SUCCEEDED']
    summaries = [j for j in succeeded if j.kind == 'SUMMARY']
    engines = {}
    for job in succeeded:
        engines.setdefault(job.engine or 'inconnu', []).append(job.duration_ms or 0)
    ratings = [j.rating for j in jobs if j.rating]
    today = timezone.localdate()
    per_day = Counter(timezone.localtime(j.created_at).date() for j in jobs)
    ai_sheets = sheets.filter(ai_generated=True)
    generated = ai_sheets.count()
    return {
        'period_days': days,
        'totals': {
            'jobs': len(jobs), 'summaries': sum(j.kind == 'SUMMARY' for j in jobs),
            'illustrations': sum(j.kind == 'ILLUSTRATION' for j in jobs),
            'running': sum(j.status in ('QUEUED', 'RUNNING') for j in jobs),
            'succeeded': len(succeeded), 'failed': len(finished) - len(succeeded),
        },
        'success_rate': round(len(succeeded) / len(finished), 3) if finished else None,
        'fallback_rate': round(sum(j.fallback for j in summaries) / len(summaries), 3) if summaries else None,
        'latency': [{'engine': engine, 'count': len(values), 'mean_ms': int(sum(values) / len(values)),
                     'p50_ms': _percentile(values, 0.5), 'p95_ms': _percentile(values, 0.95)}
                    for engine, values in sorted(engines.items())],
        'queue_mean_ms': int(_mean([j.queue_ms for j in finished]) or 0) if finished else None,
        'quality': {
            'keyword_coverage': _mean([j.metrics.get('keyword_coverage') for j in summaries]),
            'compression': _mean([j.metrics.get('compression') for j in summaries]),
            'structure_score': _mean([j.metrics.get('structure_score') for j in summaries]),
        },
        'rating': {'mean': _mean(ratings), 'count': len(ratings),
                   'distribution': [sum(r == value for r in ratings) for value in range(1, 6)]},
        'review_rate': round(ai_sheets.filter(ai_reviewed=True).count() / generated, 3) if generated else None,
        'per_day': [{'date': (today - timedelta(days=offset)).isoformat(), 'count': per_day.get(today - timedelta(days=offset), 0)}
                    for offset in range(13, -1, -1)],
        'errors': Counter(j.error for j in finished if j.status == 'FAILED' and j.error).most_common(5),
    }
