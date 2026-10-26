"""Illustrations of a sheet and the media library."""
from django.core.files.storage import default_storage
from django.http import FileResponse
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from accounts.views import validated
from classrooms.services import mutation, paginated, get_object
from django.db.models import Q
from ..models import Illustration, MAX_ILLUSTRATIONS
from ..serializers import (LibraryIllustrationSerializer, IllustrationReadSerializer, IllustrationUploadSerializer,
    IllustrationUpdateSerializer, ReorderSerializer)
from ..services import (editable_sheets, readable_sheet, editable_sheet, not_archived, normalized_image, store_image,
    next_position, remove_files)
from .base import SheetView


class IllustrationsView(SheetView):
    parser_classes = [JSONParser, MultiPartParser]

    def get(self, request, uid):
        sheet = readable_sheet(request.user, uid)
        return Response({'results': IllustrationReadSerializer(Illustration.objects.filter(sheet=sheet), many=True).data})

    def post(self, request, uid):
        sheet = editable_sheet(request.user, uid); not_archived(sheet)
        data = validated(IllustrationUploadSerializer, request)
        content, width, height = normalized_image(data['image'].read())
        return store_and_create(self, request, uid, content, width, height, caption=data['caption'], source='UPLOAD')




def store_and_create(view, request, uid, content, width, height, **fields):
    name = store_image(content)
    try:
        return create_illustration(view, request, uid, name, width, height, fields)
    except Exception:
        default_storage.delete(name)
        raise




@mutation
def create_illustration(view, request, uid, name, width, height, fields):
    sheet = editable_sheet(request.user, uid); not_archived(sheet)
    if Illustration.objects.filter(sheet=sheet).count() >= MAX_ILLUSTRATIONS:
        raise ValidationError({'image': [f'Une fiche contient au plus {MAX_ILLUSTRATIONS} illustrations.']})
    illustration = Illustration.objects.create(sheet=sheet, image=name, width=width, height=height, position=next_position(sheet), **fields)
    sheet.save(update_fields=['updated_at'])
    return Response(IllustrationReadSerializer(illustration).data, status=201)




def illustration_for(sheet, uid):
    illustration = get_object(Illustration, uid)
    if illustration.sheet_id != sheet.pk: raise NotFound('Illustration introuvable dans cette fiche.')
    return illustration




class IllustrationDetailView(SheetView):
    @mutation
    def patch(self, request, uid, illustration_id):
        sheet = editable_sheet(request.user, uid); not_archived(sheet)
        illustration = illustration_for(sheet, illustration_id)
        illustration.caption = validated(IllustrationUpdateSerializer, request)['caption']
        illustration.save(update_fields=['caption'])
        sheet.save(update_fields=['updated_at'])
        return Response(IllustrationReadSerializer(illustration).data)

    @mutation
    def delete(self, request, uid, illustration_id):
        sheet = editable_sheet(request.user, uid); not_archived(sheet)
        illustration = illustration_for(sheet, illustration_id)
        name = illustration.image.name
        illustration.delete()
        sheet.save(update_fields=['updated_at'])
        remove_files([name])
        return Response(status=204)




class IllustrationImageView(SheetView):
    def get(self, request, uid, illustration_id):
        illustration = illustration_for(readable_sheet(request.user, uid), illustration_id)
        try: handle = illustration.image.open('rb')
        except (FileNotFoundError, OSError): raise NotFound('Image introuvable.')
        return FileResponse(handle, content_type='image/webp')

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # Each file name is unique and immutable; access is still checked on every request.
        if response.status_code == 200: response['Cache-Control'] = 'private, max-age=86400'
        return response




class ReorderIllustrationsView(SheetView):
    @mutation
    def post(self, request, uid):
        sheet = editable_sheet(request.user, uid); not_archived(sheet)
        ids = validated(ReorderSerializer, request)['illustration_ids']
        items = list(Illustration.objects.filter(sheet=sheet))
        if len(ids) != len(set(ids)) or set(ids) != {str(i.pk) for i in items}:
            raise ValidationError({'illustration_ids': ['Envoyez exactement les illustrations de cette fiche, sans doublon.']})
        by_id = {str(i.pk): i for i in items}
        for position, illustration_id in enumerate(ids, 1):
            item = by_id[illustration_id]; item.position = position; item.save(update_fields=['position'])
        sheet.save(update_fields=['updated_at'])
        return Response({'results': IllustrationReadSerializer(Illustration.objects.filter(sheet=sheet), many=True).data})




class IllustrationLibraryView(SheetView):
    """Every illustration of the sheets the user manages, for the media library."""
    def get(self, request):
        mine = Illustration.objects.filter(sheet__in=editable_sheets(request.user))
        qs = mine.select_related('sheet').order_by('-created_at', 'id')
        source = request.query_params.get('source')
        if source in ('AI', 'UPLOAD'): qs = qs.filter(source=source)
        elif source: raise ValidationError({'source': ['Origine invalide.']})
        q = request.query_params.get('q', '')[:150].strip()
        if q: qs = qs.filter(Q(caption__icontains=q) | Q(sheet__title__icontains=q))
        stats = {'total': 0, 'AI': 0, 'UPLOAD': 0}
        for origin in mine.values_list('source', flat=True):
            stats['total'] += 1; stats[origin] += 1
        data = paginated(request, qs, lambda i: LibraryIllustrationSerializer(i).data)
        data['stats'] = stats
        return Response(data)
