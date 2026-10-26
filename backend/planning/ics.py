"""iCalendar (RFC 5545) export of a plan."""
from datetime import timezone as dt_timezone
from django.utils import timezone


def escape(text):
    text = str(text).replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,')
    return text.replace('\r\n', '\\n').replace('\r', '\\n').replace('\n', '\\n')


def fold(line):
    """Lines of at most 75 octets; continuation lines start with one space and never split a UTF-8 character."""
    chunks, current, size = [], '', 0
    for char in line:
        length = len(char.encode('utf-8'))
        if size + length > (74 if chunks else 75):
            chunks.append(current)
            current, size = '', 0
        current += char
        size += length
    chunks.append(current)
    return '\r\n '.join(chunks)


def utc(moment):
    return moment.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def calendar(plan, tasks, goals, deadlines):
    stamp = utc(timezone.now())
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Nexora//Hub Educatif//FR', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
        f'X-WR-CALNAME:{escape(plan.title)}']
    for task in tasks:
        details = [task.description] if task.description else []
        if task.goal_id in goals: details.append(f'Objectif : {goals[task.goal_id].title}')
        if task.deadline_id in deadlines: details.append(f'Échéance : {deadlines[task.deadline_id].title}')
        lines += ['BEGIN:VEVENT', f'UID:{task.pk}@nexora', f'DTSTAMP:{stamp}', f'DTSTART:{utc(task.starts_at)}', f'DTEND:{utc(task.ends_at)}',
            f'SUMMARY:{escape(task.title)}', f'DESCRIPTION:{escape(chr(10).join(details))}',
            f'STATUS:{"CANCELLED" if task.status == "SKIPPED" else "CONFIRMED"}', 'END:VEVENT']
    lines.append('END:VCALENDAR')
    return ''.join(fold(line) + '\r\n' for line in lines)
