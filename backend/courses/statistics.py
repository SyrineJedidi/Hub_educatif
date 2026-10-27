import csv
from io import StringIO
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from accounts.models import User
from classrooms.models import Enrollment
from .models import Chapter, Resource, ResourceView
from .serializers import course_groups


def csv_safe(value):
    # Spreadsheets execute cells starting with these characters as formulas.
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


def course_students(course):
    """Students with a current enrollment in one of the course's non-archived groups."""
    now = timezone.now()
    group_ids = [g.pk for g in course_groups(course) if not g.archived]
    ids = set(Enrollment.objects.filter(group_id__in=group_ids, starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('student_id', flat=True))
    return list(User.objects.filter(pk__in=list(ids), role='STUDENT').order_by('last_name', 'first_name', 'id'))


def course_statistics(course):
    students = course_students(course)
    chapters = {c.pk: c for c in Chapter.objects.filter(course=course)}
    resources = sorted(Resource.objects.filter(course=course), key=lambda r: (chapters[r.chapter_id].position, r.position, str(r.pk)))
    views = list(ResourceView.objects.filter(course=course, student_id__in=[s.pk for s in students]))
    total = len(resources)
    resource_rows = []
    for resource in resources:
        seen = [v for v in views if v.resource_id == resource.pk]
        resource_rows.append({'id': str(resource.pk), 'title': resource.title, 'kind': resource.kind,
            'chapter_title': chapters[resource.chapter_id].title, 'viewers': len(seen),
            'rate': round(100 * len(seen) / len(students), 1) if students else None,
            'total_views': sum(v.view_count for v in seen)})
    student_rows = []
    for student in students:
        own = [v for v in views if v.student_id == student.pk]
        student_rows.append({'id': str(student.pk), 'first_name': student.first_name, 'last_name': student.last_name,
            'viewed': len(own), 'total': total, 'percent': round(100 * len(own) / total) if total else 0,
            'last_viewed_at': max((v.last_viewed_at for v in own), default=None)})
    return {'course': {'id': str(course.pk), 'title': course.title},
        'summary': {'students': len(students), 'resources': total,
            'average_percent': round(sum(r['percent'] for r in student_rows) / len(student_rows), 1) if student_rows else None,
            'completed_students': sum(1 for r in student_rows if total and r['viewed'] >= total)},
        'resources': resource_rows, 'students': student_rows}


def statistics_csv(data):
    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Nom', 'Prénom', 'Ressources consultées', 'Total', 'Progression (%)', 'Dernière consultation'])
    for row in data['students']:
        last = timezone.localtime(row['last_viewed_at']).strftime('%d/%m/%Y %H:%M') if row['last_viewed_at'] else ''
        writer.writerow([csv_safe(v) for v in (row['last_name'], row['first_name'], row['viewed'], row['total'], row['percent'], last)])
    response = HttpResponse('﻿' + output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="cours-{data["course"]["id"]}-progression.csv"'
    response['Cache-Control'] = 'private, no-store'
    return response
