"""Revision sheets: list, create, read, update, delete, lifecycle, bulk actions and export."""
import re
import unicodedata
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.response import Response
from accounts.views import validated
from classrooms.services import mutation, paginated
from django.db.transaction import on_commit
from ..models import RevisionSheet, copy_title
from ..serializers import BulkActionSerializer, EmptyActionSerializer, sheet_list
from ..services import (readable_sheets, readable_sheet, editable_sheet, not_archived, sheet_values, publication_blockers,
    filtered_sheets, facets, delete_sheet_files, remove_files, copy_illustrations, markdown_export,
    model_errors)
from .base import detail, SheetView


class SheetsView(SheetView):
    def get(self, request):
        qs = filtered_sheets(request, readable_sheets(request.user)).select_related('owner', 'learning_group')
        page = paginated(request, qs, lambda sheet: sheet)
        page['results'] = sheet_list(page['results'], request.user)
        return Response(page)

    @mutation
    def post(self, request):
        sheet = RevisionSheet.objects.create(**sheet_values(request, request.data))
        return detail(sheet, request, 201)




class FacetsView(SheetView):
    def get(self, request):
        return Response(facets(readable_sheets(request.user)))




class SheetDetailView(SheetView):
    def get(self, request, uid):
        return detail(readable_sheet(request.user, uid), request)

    @mutation
    def patch(self, request, uid):
        sheet = editable_sheet(request.user, uid)
        values = sheet_values(request, request.data, sheet)
        # Pinning stays possible on an archived sheet; any content change is refused.
        if set(values) - {'pinned', 'owner', 'learning_group'}: not_archived(sheet)
        if sheet.status == 'PUBLISHED' and (values['learning_group'] != sheet.learning_group or values['owner'] != sheet.owner):
            raise ValidationError({'learning_group_id': ['Repassez la fiche en brouillon avant de changer son groupe ou son enseignant.']})
        for field, value in values.items(): setattr(sheet, field, value)
        sheet.save()
        return detail(sheet, request)

    @mutation
    def delete(self, request, uid):
        sheet = editable_sheet(request.user, uid)
        if sheet.status == 'PUBLISHED': raise ValidationError({'status': ['Retirez la fiche de la publication avant de la supprimer.']})
        names = delete_sheet_files(sheet)
        sheet.delete()
        remove_files(names)
        return Response(status=204)




def change_status(sheet, target):
    """Apply one lifecycle transition (draft, published, archived) after checking it is allowed."""
    if target == 'PUBLISHED':
        if sheet.status != 'DRAFT': raise ValidationError({'status': ['Seule une fiche en brouillon peut être publiée.']})
        reasons = publication_blockers(sheet)
        if reasons: raise ValidationError({'publication': reasons})
        sheet.published_at = timezone.now()
    elif target == 'DRAFT':
        if sheet.status == 'DRAFT': raise ValidationError({'status': ['La fiche est déjà en brouillon.']})
        if sheet.status == 'ARCHIVED': model_errors(sheet)
        sheet.published_at = None
    elif sheet.status == 'ARCHIVED':
        raise ValidationError({'status': ['La fiche est déjà archivée.']})
    sheet.status = target
    sheet.save(update_fields=['status', 'published_at', 'updated_at'])




class StatusView(SheetView):
    target = None

    @mutation
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        sheet = editable_sheet(request.user, uid)
        change_status(sheet, self.target)
        return detail(sheet, request)




def first_error(exc):
    message = exc.detail
    while isinstance(message, (dict, list)) and message:
        message = next(iter(message.values())) if isinstance(message, dict) else message[0]
    return str(message)




class BulkView(SheetView):
    """Apply one action to several sheets; each sheet succeeds or fails on its own."""
    TARGETS = {'publish': 'PUBLISHED', 'unpublish': 'DRAFT', 'archive': 'ARCHIVED'}

    @mutation
    def post(self, request):
        data = validated(BulkActionSerializer, request)
        done, failed, removed = [], [], []
        for uid in dict.fromkeys(data['ids']):
            sheet = None
            try:
                sheet = editable_sheet(request.user, uid)
                if data['action'] == 'delete':
                    if sheet.status == 'PUBLISHED':
                        raise ValidationError({'status': ['Retirez-la de la publication avant de la supprimer.']})
                    removed += delete_sheet_files(sheet)
                    sheet.delete()
                else:
                    change_status(sheet, self.TARGETS[data['action']])
                done.append(uid)
            except (ValidationError, NotFound) as exc:
                failed.append({'id': uid, 'title': sheet.title if sheet else '', 'reason': first_error(exc)})
        # Image files are removed only once the database changes are committed.
        on_commit(lambda: remove_files(removed))
        return Response({'done': done, 'failed': failed})




class DuplicateView(SheetView):
    @mutation
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        source = readable_sheet(request.user, uid)
        user = request.user
        copy = RevisionSheet(
            title=copy_title(source.title), course_label=source.course_label, summary=source.summary,
            key_points=list(source.key_points), glossary=list(source.glossary), tags=list(source.tags), color=source.color,
            ai_generated=source.ai_generated, ai_reviewed=source.ai_reviewed, ai_model=source.ai_model,
            generated_at=source.generated_at, source_name=source.source_name, illustration_prompt=source.illustration_prompt,
            # A student keeps a personal copy; teachers and the administrator keep the original group and owner.
            owner=user if user.role == 'STUDENT' else source.owner,
            learning_group=None if user.role == 'STUDENT' else source.learning_group)
        model_errors(copy)
        copy.save()
        copy_illustrations(source, copy)
        return detail(copy, request, 201)




class ExportView(SheetView):
    def get(self, request, uid):
        sheet = readable_sheet(request.user, uid)
        slug = unicodedata.normalize('NFKD', sheet.title).encode('ascii', 'ignore').decode()
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', slug).strip('-').lower()[:60] or 'fiche'
        response = HttpResponse(markdown_export(sheet), content_type='text/markdown; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="fiche-{slug}.md"'
        return response
