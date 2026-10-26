from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from classrooms.models import Enrollment
from classrooms.services import groups_for, group_access
from .models import LearningSession, AttendanceSheet

def sessions_for(user):
    sessions = LearningSession.objects.filter(group_id__in=list(groups_for(user).values_list('id',flat=True)))
    if user.role != 'STUDENT':
        return sessions
    allowed = Q(pk__in=[])
    for period in Enrollment.objects.filter(student=user):
        clause = Q(group_id=period.group_id, starts_at__gte=period.starts_at)
        if period.ends_at:
            clause &= Q(starts_at__lt=period.ends_at)
        allowed |= clause
    # Validated/draft participants remain entitled to their own historical session.
    snapshots = [s.session_id for s in AttendanceSheet.objects.all() if any(e.student_id == str(user.pk) for e in s.entries)]
    return sessions.filter(allowed | Q(pk__in=snapshots))

def session_access(user, session, write=False):
    group_access(user, session.group)
    if user.role == 'STUDENT':
        if write or not sessions_for(user).filter(pk=session.pk).exists():
            raise PermissionDenied('Accès à cette séance refusé.')

def editable(user, session):
    session_access(user, session, write=True)
    if session.status == 'CANCELLED' or session.starts_at > timezone.now():
        raise ValidationError('La saisie est ouverte après le début d’une séance non annulée.')

def filtered_sessions(request):
    from classrooms.models import LearningGroup
    from classrooms.services import get_object
    from rest_framework.fields import DateTimeField
    qs = sessions_for(request.user)
    if request.query_params.get('group'):
        group = get_object(LearningGroup, request.query_params['group'])
        group_access(request.user, group)
        qs = qs.filter(group=group)
    if request.query_params.get('status'):
        qs = qs.filter(status=request.query_params['status'])
    for parameter, lookup in [('from', 'starts_at__gte'), ('to', 'starts_at__lt')]:
        if request.query_params.get(parameter):
            value = DateTimeField().run_validation(request.query_params[parameter])
            qs = qs.filter(**{lookup:value})
    return qs

def statistics(request):
    sessions = filtered_sessions(request).filter(ends_at__lt=timezone.now()).exclude(status='CANCELLED')
    rows = []
    totals = dict(PRESENT=0, LATE=0, ABSENT=0, EXCUSED=0)
    for session in sessions:
        sheet = AttendanceSheet.objects.filter(session=session, validated=True).first()
        if not sheet:
            continue
        for entry in sheet.entries:
            if request.user.role == 'STUDENT' and entry.student_id != str(request.user.pk):
                continue
            if entry.status not in totals:
                continue
            totals[entry.status] += 1
            rows.append({'session_id': str(session.pk), 'session_title': session.title,
                'group_id': str(session.group_id), 'group_name': session.group.name,
                'starts_at': session.starts_at, 'student_id': entry.student_id,
                'student_name': entry.student_name, 'status': entry.status})
    denominator = totals['PRESENT'] + totals['LATE'] + totals['ABSENT']
    rate = round((totals['PRESENT']+totals['LATE']) / denominator * 100, 1) if denominator else None
    by_student, by_session = {}, {}
    for row in rows:
        for grouping, key, label in [(by_student,row['student_id'],row['student_name']), (by_session,row['session_id'],row['session_title'])]:
            summary = grouping.setdefault(key, {'id':key,'label':label,'PRESENT':0,'LATE':0,'ABSENT':0,'EXCUSED':0})
            summary[row['status']] += 1
    return {'totals':totals, 'rate':rate, 'rows':rows, 'by_student':list(by_student.values()), 'by_session':list(by_session.values())}
