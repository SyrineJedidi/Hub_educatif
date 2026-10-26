from django.conf import settings
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from accounts.permissions import Administrator
from accounts.views import SecureView, validated
from classrooms.services import mutation, paginated
from .insights import admin_usage, insights_csv, period, scope_insights
from .models import TeacherNote
from .permissions import AssistantManager
from .serializers import (NoteCreateSerializer, NoteUpdateSerializer, ReviewActionSerializer, SettingsSerializer, note_data,
    review_data, settings_data)
from .services import (apply_fixed_mode, apply_review, filtered_notes, filtered_reviews, managed_note, managed_review, managed_scope, managed_scopes,
    note_errors, note_group, review_parts, settings_for, settings_rows, teachers_by_id)


class ManagerView(SecureView):
    permission_classes = [AssistantManager]


class NotesView(ManagerView):
    def get(self, request):
        return Response(paginated(request, filtered_notes(request), note_data))

    @mutation
    def post(self, request):
        data = validated(NoteCreateSerializer, request)
        group = note_group(request.user, data['group_id'])
        note = TeacherNote(group=group, teacher=group.teacher, title=data['title'], body=data['body'])
        note_errors(note); note.save()
        return Response(note_data(note), status=201)


class NoteDetailView(ManagerView):
    def get(self, request, uid):
        return Response(note_data(managed_note(request.user, uid)))

    @mutation
    def patch(self, request, uid):
        note = managed_note(request.user, uid)
        data = validated(NoteUpdateSerializer, request)
        changed = any(getattr(note, field) != value for field, value in data.items())
        for field, value in data.items(): setattr(note, field, value)
        # A reassigned group hands its notes to the new teacher.
        note.teacher = note.group.teacher
        note_errors(note)
        if changed: note.version += 1
        note.save()
        return Response(note_data(note))

    @mutation
    def delete(self, request, uid):
        managed_note(request.user, uid).delete()
        return Response(status=204)


def scope_settings(scope, row, teachers):
    return settings_data(scope, row, teachers.get(scope.teacher_id), settings.ASSISTANT_DAILY_QUESTIONS)


class SettingsListView(ManagerView):
    def get(self, request):
        scopes = managed_scopes(request.user)
        rows, teachers = settings_rows(scopes), teachers_by_id(scopes)
        return Response({'results': [scope_settings(s, rows[s.key], teachers) for s in scopes]})


class SettingsDetailView(ManagerView):
    def get(self, request, source_type, scope_id):
        _, scope = managed_scope(request.user, source_type, scope_id)
        return Response(scope_settings(scope, settings_for(scope), teachers_by_id([scope])))

    @mutation
    def put(self, request, source_type, scope_id):
        _, scope = managed_scope(request.user, source_type, scope_id)
        data = validated(SettingsSerializer, request)
        row = settings_for(scope)
        for field, value in data.items(): setattr(row, field, value)
        row.updated_by = request.user
        row.save()
        apply_fixed_mode(scope, row)
        return Response(scope_settings(scope, row, teachers_by_id([scope])))


class InsightsView(ManagerView):
    def perform_content_negotiation(self, request, force=False):
        # `format=csv` is this view's own parameter, not a renderer choice.
        return super().perform_content_negotiation(request, force=True)

    def get(self, request, source_type, scope_id):
        _, scope = managed_scope(request.user, source_type, scope_id)
        output = request.query_params.get('format', 'json')
        if output not in ('json', 'csv'): raise ValidationError({'format': ['Choisissez json ou csv.']})
        start, end = period(request)
        data = scope_insights(scope, start, end)
        return insights_csv(data) if output == 'csv' else Response(data)


def review_payload(feedback):
    question, answer, scope_title = review_parts(feedback)
    return review_data(feedback, question, answer, scope_title) if answer else None


class ReviewsView(ManagerView):
    def get(self, request):
        data = paginated(request, filtered_reviews(request), review_payload)
        data['results'] = [item for item in data['results'] if item]
        return Response(data)


class ReviewDetailView(ManagerView):
    def get(self, request, uid):
        payload = review_payload(managed_review(request.user, uid))
        if not payload: raise NotFound('Retour introuvable.')
        return Response(payload)

    @mutation
    def patch(self, request, uid):
        feedback = managed_review(request.user, uid)
        data = validated(ReviewActionSerializer, request)
        payload = review_payload(apply_review(request.user, feedback, data))
        if not payload: raise NotFound('Retour introuvable.')
        return Response(payload)


class AdminUsageView(SecureView):
    permission_classes = [Administrator]

    def get(self, request):
        return Response(admin_usage())
