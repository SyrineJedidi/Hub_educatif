from collections.abc import Mapping
import re
from rest_framework import serializers
from accounts.serializers import StrictSerializer
from .models import (AIJob, RevisionSheet, Illustration, TITLE_MAX_LENGTH, SUMMARY_MAX_LENGTH,
    MAX_KEY_POINTS, MAX_GLOSSARY, MAX_TAGS)


def collapse(value):
    return ' '.join(value.split())


class SheetInputSerializer(StrictSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping): raise serializers.ValidationError({'non_field_errors': ['Envoyez un objet JSON.']})
        return super().to_internal_value(data)


class TextField(serializers.CharField):
    default_error_messages = {
        'required': 'Ce champ est obligatoire.',
        'blank': 'Ce champ est obligatoire et ne peut pas contenir uniquement des espaces.',
        'null': 'Ce champ ne peut pas être vide.',
        'invalid': 'Saisissez un texte valide.',
        'max_length': 'Limitez ce champ à {max_length} caractères.',
    }

    def to_internal_value(self, data):
        if not isinstance(data, str): self.fail('invalid')
        return super().to_internal_value(data)


class ReferenceField(TextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not re.fullmatch(r'[0-9a-fA-F]{24}', value):
            raise serializers.ValidationError('Sélectionnez une valeur existante dans la liste.')
        return value


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if not isinstance(data, bool): self.fail('invalid')
        return data


class KeyPointsField(serializers.ListField):
    def __init__(self, **kwargs):
        super().__init__(child=TextField(max_length=300), max_length=MAX_KEY_POINTS, **kwargs)
        self.error_messages['max_length'] = f'Limitez la fiche à {MAX_KEY_POINTS} points clés.'

    def to_internal_value(self, data):
        return [point for point in (collapse(p) for p in super().to_internal_value(data)) if point]


class GlossaryEntrySerializer(StrictSerializer):
    term = TextField(max_length=80)
    definition = TextField(max_length=400)


class GlossaryField(serializers.ListField):
    def __init__(self, **kwargs):
        super().__init__(child=GlossaryEntrySerializer(), max_length=MAX_GLOSSARY, **kwargs)
        self.error_messages['max_length'] = f'Limitez le glossaire à {MAX_GLOSSARY} définitions.'

    def to_internal_value(self, data):
        entries, seen = [], set()
        for entry in super().to_internal_value(data):
            term = collapse(entry['term'])
            if term.casefold() in seen:
                raise serializers.ValidationError(f'Le terme « {term} » est défini plusieurs fois.')
            seen.add(term.casefold())
            entries.append({'term': term, 'definition': entry['definition'].strip()})
        return entries


class TagsField(serializers.ListField):
    def __init__(self, **kwargs):
        super().__init__(child=TextField(max_length=30), max_length=MAX_TAGS, **kwargs)
        self.error_messages['max_length'] = f'Utilisez au plus {MAX_TAGS} étiquettes.'

    def to_internal_value(self, data):
        tags, seen = [], set()
        for tag in super().to_internal_value(data):
            tag = collapse(tag).lstrip('#').lower()
            if tag and tag not in seen:
                seen.add(tag); tags.append(tag)
        return tags


class SheetWriteSerializer(SheetInputSerializer):
    title = TextField(max_length=TITLE_MAX_LENGTH)
    course_label = TextField(max_length=120)
    summary = TextField(max_length=SUMMARY_MAX_LENGTH, allow_blank=True, trim_whitespace=False, required=False)
    key_points = KeyPointsField(required=False)
    glossary = GlossaryField(required=False)
    tags = TagsField(required=False)
    color = serializers.ChoiceField(choices=RevisionSheet.Color.choices, required=False,
        error_messages={'invalid_choice': 'Sélectionnez une couleur proposée.'})
    pinned = StrictBooleanField(required=False)
    ai_reviewed = StrictBooleanField(required=False)


class TeacherSheetWriteSerializer(SheetWriteSerializer):
    learning_group_id = ReferenceField()


class AdminSheetWriteSerializer(TeacherSheetWriteSerializer):
    teacher_id = ReferenceField()


class GenerateSummarySerializer(SheetInputSerializer):
    LENGTHS = [('SHORT', 'Synthétique'), ('STANDARD', 'Standard'), ('DETAILED', 'Détaillée')]
    source_text = TextField(max_length=60000, required=False, allow_blank=True)
    file = serializers.FileField(required=False)
    length = serializers.ChoiceField(choices=LENGTHS, default='STANDARD')

    def to_internal_value(self, data):
        # Multipart bodies are QueryDicts: read single values so lists do not leak into fields.
        if hasattr(data, 'getlist'):
            data = {key: data.get(key) for key in data}
        return super().to_internal_value(data)

    def validate_file(self, upload):
        name = upload.name.lower()
        if not name.endswith(('.pdf', '.txt', '.md')):
            raise serializers.ValidationError('Importez un fichier PDF, TXT ou Markdown.')
        if upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('La taille maximale est de 10 Mo.')
        return upload

    def validate(self, attrs):
        if not attrs.get('file') and not (attrs.get('source_text') or '').strip():
            raise serializers.ValidationError({'source_text': ['Collez le contenu du cours ou importez un fichier.']})
        return attrs


class IllustrationUploadSerializer(SheetInputSerializer):
    image = serializers.FileField()
    caption = TextField(max_length=300)

    def to_internal_value(self, data):
        if hasattr(data, 'getlist'):
            data = {key: data.get(key) for key in data}
        return super().to_internal_value(data)


class IllustrationGenerateSerializer(SheetInputSerializer):
    STYLES = [('SCHEMA', 'Schéma pédagogique'), ('FLAT', 'Illustration flat design'),
              ('REALISTIC', 'Rendu réaliste'), ('WATERCOLOR', 'Aquarelle')]
    prompt = TextField(max_length=600)
    caption = TextField(max_length=300)
    style = serializers.ChoiceField(choices=STYLES, default='SCHEMA')


class IllustrationUpdateSerializer(SheetInputSerializer):
    caption = TextField(max_length=300)


class ReorderSerializer(SheetInputSerializer):
    illustration_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class EmptyActionSerializer(SheetInputSerializer):
    pass


def illustration_url(illustration):
    return f'/api/sheets/{illustration.sheet_id}/illustrations/{illustration.pk}/image/'


class IllustrationReadSerializer(serializers.Serializer):
    id = serializers.CharField()
    sheet_id = serializers.CharField()
    url = serializers.SerializerMethodField()
    caption = serializers.CharField()
    prompt = serializers.CharField()
    source = serializers.CharField()
    ai_model = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    position = serializers.IntegerField()
    created_at = serializers.DateTimeField()

    def get_url(self, illustration): return illustration_url(illustration)


def illustration_summary(sheets):
    """{sheet id: (illustration count, cover url)} for several sheets in a single query."""
    summary = {}
    rows = Illustration.objects.filter(sheet_id__in=[s.pk for s in sheets]).order_by('sheet_id', 'position', 'id')
    for sheet_id, pk in rows.values_list('sheet_id', 'pk'):
        count, cover = summary.get(sheet_id, (0, None))
        summary[sheet_id] = (count + 1, cover or f'/api/sheets/{sheet_id}/illustrations/{pk}/image/')
    return summary


def sheet_list(sheets, user):
    """Serialize a page of sheets with their owner, group and illustrations loaded in bulk."""
    sheets = list(sheets)
    context = {'user': user, 'covers': illustration_summary(sheets)}
    return [SheetListSerializer(sheet, context=context).data for sheet in sheets]


class LibraryIllustrationSerializer(IllustrationReadSerializer):
    sheet_title = serializers.CharField(source='sheet.title')
    sheet_status = serializers.CharField(source='sheet.status')
    course_label = serializers.CharField(source='sheet.course_label')


class SheetListSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    course_label = serializers.CharField()
    excerpt = serializers.SerializerMethodField()
    tags = serializers.ListField()
    color = serializers.CharField()
    status = serializers.CharField()
    pinned = serializers.BooleanField()
    personal = serializers.BooleanField()
    ai_generated = serializers.BooleanField()
    ai_reviewed = serializers.BooleanField()
    owner_id = serializers.CharField()
    owner_name = serializers.SerializerMethodField()
    learning_group_id = serializers.CharField(allow_null=True)
    learning_group_name = serializers.SerializerMethodField()
    key_point_count = serializers.SerializerMethodField()
    illustration_count = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    published_at = serializers.DateTimeField(allow_null=True)

    def get_excerpt(self, sheet):
        text = re.sub(r'[#*_>`-]+', ' ', sheet.summary)
        text = collapse(text)
        return text[:220] + ('…' if len(text) > 220 else '')
    def get_owner_name(self, sheet): return f'{sheet.owner.first_name} {sheet.owner.last_name}'.strip()
    def get_learning_group_name(self, sheet): return sheet.learning_group.name if sheet.learning_group_id else None
    def get_key_point_count(self, sheet): return len(sheet.key_points)
    def _covers(self, sheet):
        # Precomputed for a whole page by sheet_list(); computed alone for a single sheet.
        covers = self.context.get('covers')
        return covers.get(sheet.pk, (0, None)) if covers is not None else illustration_summary([sheet]).get(sheet.pk, (0, None))
    def get_illustration_count(self, sheet): return self._covers(sheet)[0]
    def get_cover_url(self, sheet): return self._covers(sheet)[1]
    def get_can_edit(self, sheet):
        user = self.context.get('user')
        return bool(user) and (user.role == 'ADMIN' or sheet.owner_id == user.pk)


class SheetDetailSerializer(SheetListSerializer):
    summary = serializers.CharField()
    key_points = serializers.ListField()
    glossary = serializers.ListField()
    ai_model = serializers.CharField()
    generated_at = serializers.DateTimeField(allow_null=True)
    source_name = serializers.CharField()
    illustration_prompt = serializers.CharField()
    illustrations = serializers.SerializerMethodField()
    publication_blockers = serializers.SerializerMethodField()

    def get_illustrations(self, sheet):
        return IllustrationReadSerializer(Illustration.objects.filter(sheet=sheet), many=True).data
    def get_publication_blockers(self, sheet):
        from .services import publication_blockers
        return publication_blockers(sheet) if self.get_can_edit(sheet) and sheet.status == 'DRAFT' and not sheet.personal else []


class BulkActionSerializer(SheetInputSerializer):
    action = serializers.ChoiceField(choices=['publish', 'unpublish', 'archive', 'delete'],
                                     error_messages={'invalid_choice': 'Action inconnue.'})
    ids = serializers.ListField(child=ReferenceField(), min_length=1, max_length=50, error_messages={
        'min_length': 'Sélectionnez au moins une fiche.', 'max_length': 'Sélectionnez au plus 50 fiches.'})


class ReviewSerializer(SheetInputSerializer):
    known = serializers.ListField(child=serializers.CharField(max_length=40), max_length=40, allow_empty=True)


class SelfQuizSerializer(SheetInputSerializer):
    count = serializers.IntegerField(min_value=3, max_value=10, default=5)


class RatingSerializer(SheetInputSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, error_messages={
        'invalid': 'Choisissez une note de 1 à 5.', 'min_value': 'Choisissez une note de 1 à 5.', 'max_value': 'Choisissez une note de 1 à 5.'})


def job_data(job, viewer=None):
    data = {
        'id': str(job.pk), 'kind': job.kind, 'status': job.status, 'sheet_id': str(job.sheet_id) if job.sheet_id else None,
        'sheet_title': job.sheet_title, 'engine': job.engine, 'model': job.model, 'fallback': job.fallback, 'error': job.error,
        'params': {k: v for k, v in job.params.items() if k in ('length', 'style', 'caption', 'prompt', 'source_characters', 'count')},
        'source_name': job.source_name, 'metrics': job.metrics, 'rating': job.rating, 'duration_ms': job.duration_ms,
        'queue_ms': job.queue_ms, 'created_at': job.created_at, 'started_at': job.started_at, 'finished_at': job.finished_at,
        'illustration': IllustrationReadSerializer(job.illustration).data if job.illustration_id else None,
    }
    # The training quiz belongs to the person who asked for it.
    if job.kind == AIJob.Kind.QUIZ and viewer is not None and viewer.pk == job.user_id:
        data['result'] = job.result or {}
    if viewer is not None and viewer.role == 'ADMIN':
        data['user_name'] = f'{job.user.first_name} {job.user.last_name}'.strip() or job.user.email
    return data
