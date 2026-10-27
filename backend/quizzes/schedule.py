from datetime import timedelta
from django.utils import timezone


def attempt_deadline(quiz, started_at):
    limits = [date for date in (started_at + timedelta(minutes=quiz.duration_minutes) if quiz.duration_minutes else None,
                               quiz.closes_at) if date is not None]
    return min(limits) if limits else None


def availability(quiz, now=None):
    now = now or timezone.now()
    state = 'UPCOMING' if quiz.opens_at and now < quiz.opens_at else 'CLOSED' if quiz.closes_at and now >= quiz.closes_at else 'OPEN'
    deadline = attempt_deadline(quiz, now)
    allowed = quiz.status == 'PUBLISHED' and state == 'OPEN'
    return {'state': state, 'can_start': allowed, 'opens_at': quiz.opens_at, 'closes_at': quiz.closes_at,
            'available_seconds': max(0, int((deadline-now).total_seconds())) if deadline and allowed else None,
            'server_time': now, 'time_zone': 'Africa/Tunis'}
