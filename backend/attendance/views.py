import csv
from io import StringIO
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from accounts.views import SecureView, validated
from classrooms.models import Enrollment
from classrooms.services import get_object, mutation, paginated, Conflict
from .models import LearningSession, AttendanceSheet, Attendance
from .serializers import SessionSerializer, SheetSerializer, session_data, sheet_data
from .services import filtered_sessions, session_access, editable, statistics

class SessionsView(SecureView):
    def get(self, request):
        return Response(paginated(request, filtered_sessions(request).order_by('starts_at','id'), session_data))
    @mutation
    def post(self, request):
        data = validated(SessionSerializer, request, user=request.user)
        return Response(session_data(LearningSession.objects.create(creator=request.user, **data)), status=201)

class SessionDetailView(SecureView):
    def get(self, request, uid):
        session = get_object(LearningSession, uid)
        session_access(request.user, session)
        return Response(session_data(session))
    @mutation
    def patch(self, request, uid):
        session = get_object(LearningSession, uid)
        session_access(request.user, session, write=True)
        data = validated(SessionSerializer, request, user=request.user, instance=session)
        for key,value in data.items():
            setattr(session,key,value)
        session.save()
        return Response(session_data(session))

class SheetView(SecureView):
    def get(self, request, uid):
        session = get_object(LearningSession,uid)
        session_access(request.user,session,write=True)
        sheet = AttendanceSheet.objects.filter(session=session).first()
        if not sheet:
            raise NotFound('La feuille n’est pas encore ouverte.')
        return Response(sheet_data(sheet))
    @mutation
    def post(self, request, uid):
        session = get_object(LearningSession,uid)
        editable(request.user,session)
        sheet = AttendanceSheet.objects.filter(session=session).first()
        if not sheet:
            periods = Enrollment.objects.filter(group=session.group, starts_at__lte=session.starts_at).filter(Q(ends_at__isnull=True)|Q(ends_at__gt=session.starts_at))
            participants = {}
            for e in periods:
                student = e.student
                participants[str(student.pk)] = Attendance(student_id=str(student.pk), student_name=f'{student.first_name} {student.last_name}')
            sheet = AttendanceSheet.objects.create(session=session, entries=list(participants.values()))
        return Response(sheet_data(sheet))
    @mutation
    def put(self, request, uid):
        session = get_object(LearningSession,uid)
        editable(request.user,session)
        sheet = AttendanceSheet.objects.filter(session=session).first()
        if not sheet:
            raise ValidationError('Ouvrez d’abord la feuille.')
        data = validated(SheetSerializer,request)
        if data['version'] != sheet.version:
            raise Conflict()
        entries = data['entries']
        ids = [e['student_id'] for e in entries]
        if len(set(ids)) != len(ids) or set(ids) != {e.student_id for e in sheet.entries}:
            raise ValidationError('La liste des participants doit correspondre à la feuille historique, sans doublon.')
        if data['validate_sheet'] and (not entries or any(e['status']=='UNSET' for e in entries)):
            raise ValidationError('Renseignez tous les statuts avant de valider la feuille.')
        if sheet.validated and not data['reason'].strip():
            raise ValidationError({'reason':['Un motif est obligatoire après validation.']})
        now = timezone.now()
        updates = {e['student_id']: e for e in entries}
        for old in sheet.entries:
            new = updates[old.student_id]
            if old.status != new['status'] or old.comment != new['comment']:
                sheet.history.append({'student_id': old.student_id, 'old_status':old.status, 'new_status':new['status'],
                    'old_comment':old.comment, 'new_comment':new['comment'], 'author_id':str(request.user.pk),
                    'author_name':f'{request.user.first_name} {request.user.last_name}', 'at':now.isoformat(), 'reason':data['reason'], 'was_validated':sheet.validated})
                old.status,old.comment = new['status'],new['comment']
                old.author_id,old.updated_at = str(request.user.pk), now
        # A validated sheet stays validated; corrections cannot introduce UNSET.
        if sheet.validated and any(e.status=='UNSET' for e in sheet.entries):
            raise ValidationError('Une feuille validée ne peut contenir de statut non renseigné.')
        sheet.validated = sheet.validated or data['validate_sheet']
        sheet.version += 1
        sheet.save()
        return Response(sheet_data(sheet))

class StatisticsView(SecureView):
    def get(self,request):
        data = statistics(request)
        page_data = data.pop('rows')
        try:
            page = max(1,int(request.query_params.get('page',1)))
        except ValueError:
            raise ValidationError({'page':['Page invalide.']})
        data.update(count=len(page_data), page=page, page_size=20, results=page_data[(page-1)*20:page*20])
        return Response(data)

class ExportView(SecureView):
    def get(self,request):
        if request.user.role == 'STUDENT':
            raise PermissionDenied('Export réservé aux enseignants concernés et administrateurs.')
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value
        output = StringIO()
        writer = csv.writer(output,delimiter=';')
        writer.writerow(['Groupe','Séance','Début','Étudiant','Statut'])
        for row in statistics(request)['rows']:
            writer.writerow([safe(row[k]) for k in ['group_name','session_title','starts_at','student_name','status']])
        response = HttpResponse('﻿'+output.getvalue(),content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="assiduite.csv"'
        response['Cache-Control'] = 'private, no-store'
        return response
