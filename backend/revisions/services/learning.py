"""Revision with flashcards and follow-up of how students read the shared sheets."""
import hashlib
import unicodedata
from django.db.models import Q
from django.utils import timezone
from classrooms.models import Enrollment
from ..models import SheetProgress


def _key(text):
    text = unicodedata.normalize('NFKD', text.casefold())
    return ''.join(c for c in text if not unicodedata.combining(c)).strip()


def flashcards(sheet):
    """Cards built from the glossary (term → definition) and the key points.

    Identifiers come from the content itself, so a card keeps its mastery when the
    teacher reorders the sheet, and a rewritten card starts again from zero.
    """
    cards = [{'id': 'g:' + hashlib.sha1(_key(e['term']).encode()).hexdigest()[:12], 'kind': 'TERM',
              'front': e['term'], 'back': e['definition']} for e in sheet.glossary]
    cards += [{'id': 'k:' + hashlib.sha1(_key(p).encode()).hexdigest()[:12], 'kind': 'POINT',
               'front': f'À retenir n° {i}', 'back': p} for i, p in enumerate(sheet.key_points, 1)]
    return cards


def tracked(user, sheet):
    """Progress is recorded for students reading a sheet shared by their teacher."""
    return user.role == 'STUDENT' and sheet.owner_id != user.pk and sheet.learning_group_id is not None


def progress_data(progress, cards):
    ids = {c['id'] for c in cards}
    known = [k for k in (progress.known if progress else []) if k in ids]
    return {
        'views': progress.views if progress else 0,
        'last_viewed_at': progress.last_viewed_at if progress else None,
        'review_sessions': progress.review_sessions if progress else 0,
        'last_reviewed_at': progress.last_reviewed_at if progress else None,
        'known': known,
        'mastery': round(len(known) / len(ids), 3) if ids else None,
    }


def record_view(user, sheet):
    progress, _ = SheetProgress.objects.get_or_create(sheet=sheet, student=user)
    now = timezone.now()
    progress.views += 1
    progress.first_viewed_at = progress.first_viewed_at or now
    progress.last_viewed_at = now
    progress.save()
    return progress


def record_review(user, sheet, known):
    cards = flashcards(sheet)
    ids = {c['id'] for c in cards}
    progress, _ = SheetProgress.objects.get_or_create(sheet=sheet, student=user)
    now = timezone.now()
    progress.known = [k for k in dict.fromkeys(known) if k in ids]
    progress.review_sessions += 1
    progress.last_reviewed_at = now
    progress.first_viewed_at = progress.first_viewed_at or now
    progress.save()
    return progress_data(progress, cards)


def group_students(group_id):
    """Students currently enrolled in the group."""
    now = timezone.now()
    enrollments = Enrollment.objects.filter(group_id=group_id, starts_at__lte=now).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)).select_related('student')
    return [e.student for e in enrollments if e.student.is_active]


def engagement(sheets):
    """Readers and mastery of every published sheet, for its teacher."""
    rows = []
    for sheet in sheets.filter(status='PUBLISHED', learning_group__isnull=False).select_related('learning_group'):
        students = group_students(sheet.learning_group_id)
        cards = flashcards(sheet)
        by_student = {p.student_id: p for p in SheetProgress.objects.filter(sheet=sheet)}
        details = []
        for student in sorted(students, key=lambda s: (s.last_name.casefold(), s.first_name.casefold())):
            data = progress_data(by_student.get(student.pk), cards)
            details.append({'student_id': str(student.pk), 'name': f'{student.first_name} {student.last_name}'.strip(),
                            'views': data['views'], 'last_viewed_at': data['last_viewed_at'],
                            'review_sessions': data['review_sessions'], 'mastery': data['mastery']})
        readers = [d for d in details if d['views'] or d['review_sessions']]
        masteries = [d['mastery'] for d in readers if d['mastery'] is not None]
        last = max((d['last_viewed_at'] for d in details if d['last_viewed_at']), default=None)
        rows.append({
            'sheet_id': str(sheet.pk), 'title': sheet.title, 'course_label': sheet.course_label,
            'group_name': sheet.learning_group.name, 'published_at': sheet.published_at,
            'students': len(details), 'readers': len(readers), 'cards': len(cards),
            'average_mastery': round(sum(masteries) / len(masteries), 3) if masteries else None,
            'last_viewed_at': last, 'details': details,
        })
    return rows
