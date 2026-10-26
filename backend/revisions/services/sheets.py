from io import BytesIO
from uuid import uuid4
from django.core.exceptions import ValidationError as ModelValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import NotFound, ValidationError
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from classrooms.services import get_object
from ..models import RevisionSheet, Illustration
from ..serializers import SheetWriteSerializer, TeacherSheetWriteSerializer, AdminSheetWriteSerializer

CONTENT_FIELDS = ('title', 'course_label', 'summary', 'key_points', 'glossary', 'tags', 'color', 'pinned', 'ai_reviewed')


def active_group_ids(student):
    now = timezone.now()
    ids = list(Enrollment.objects.filter(student=student, starts_at__lte=now)
               .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('group_id', flat=True))
    return list(LearningGroup.objects.filter(pk__in=ids, archived=False).values_list('id', flat=True))


def readable_sheets(user):
    if user.role == 'ADMIN': return RevisionSheet.objects.all()
    if user.role == 'TEACHER': return RevisionSheet.objects.filter(owner=user)
    return RevisionSheet.objects.filter(Q(owner=user) | Q(learning_group_id__in=active_group_ids(user), status='PUBLISHED'))


def editable_sheets(user):
    return RevisionSheet.objects.all() if user.role == 'ADMIN' else RevisionSheet.objects.filter(owner=user)


def readable_sheet(user, uid):
    sheet = get_object(RevisionSheet, uid)
    if not readable_sheets(user).filter(pk=sheet.pk).exists(): raise NotFound('Fiche introuvable.')
    return sheet


def editable_sheet(user, uid):
    sheet = readable_sheet(user, uid)
    if user.role != 'ADMIN' and sheet.owner_id != user.pk: raise NotFound('Fiche introuvable.')
    return sheet


def not_archived(sheet):
    if sheet.status == RevisionSheet.Status.ARCHIVED:
        raise ValidationError({'status': ['Cette fiche est archivée. Restaurez-la pour la modifier.']})


def model_errors(instance):
    try: instance.full_clean(validate_unique=False, validate_constraints=False)
    except ModelValidationError as exc:
        errors = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
        rename = {'learning_group': 'learning_group_id', 'owner': 'teacher_id'}
        raise ValidationError({rename.get(k, k): v for k, v in errors.items()})


def sheet_values(request, data, instance=None):
    role = request.user.role
    cls = AdminSheetWriteSerializer if role == 'ADMIN' else TeacherSheetWriteSerializer if role == 'TEACHER' else SheetWriteSerializer
    serializer = cls(data=data, partial=bool(instance))
    serializer.is_valid(raise_exception=True)
    attrs = dict(serializer.validated_data)
    try:
        owner = get_object(User, attrs.pop('teacher_id')) if 'teacher_id' in attrs else instance.owner if instance else request.user
    except NotFound:
        raise ValidationError({'teacher_id': ['Sélectionnez un enseignant actif existant.']})
    if 'teacher_id' in serializer.validated_data and owner.role != 'TEACHER':
        raise ValidationError({'teacher_id': ['Sélectionnez un enseignant actif existant.']})
    try:
        group = get_object(LearningGroup, attrs.pop('learning_group_id')) if 'learning_group_id' in attrs else instance.learning_group if instance else None
    except NotFound:
        raise ValidationError({'learning_group_id': ['Sélectionnez un groupe actif autorisé existant.']})
    candidate = RevisionSheet(owner=owner, learning_group=group)
    for field in CONTENT_FIELDS:
        setattr(candidate, field, attrs[field] if field in attrs else getattr(instance, field) if instance else getattr(candidate, field))
    model_errors(candidate)
    values = {field: getattr(candidate, field) for field in CONTENT_FIELDS if field in attrs or not instance}
    values.update(owner=owner, learning_group=group)
    return values


def publication_blockers(sheet):
    reasons = []
    try: model_errors(sheet)
    except ValidationError as exc:
        labels = {'title': 'Titre', 'course_label': 'Cours', 'learning_group_id': 'Groupe pédagogique', 'teacher_id': 'Enseignant'}
        for field, messages in exc.detail.items():
            reasons.extend(f'{labels.get(field, field)} : {message}' for message in messages)
    if sheet.personal: reasons.append('Une fiche personnelle ne peut pas être publiée.')
    if len(sheet.summary.strip()) < 40: reasons.append('Rédigez ou générez un résumé d’au moins 40 caractères.')
    if not sheet.key_points: reasons.append('Ajoutez au moins un point clé.')
    if sheet.ai_generated and not sheet.ai_reviewed:
        reasons.append('Confirmez la relecture du contenu généré par l’IA avant de le partager.')
    if Illustration.objects.filter(sheet=sheet).filter(Q(caption='') | Q(caption__isnull=True)).exists():
        reasons.append('Chaque illustration doit avoir une description accessible.')
    return reasons


def filtered_sheets(request, queryset):
    from rest_framework.fields import ChoiceField
    params = request.query_params
    q = params.get('q', '')[:150].strip()
    if q: queryset = queryset.filter(Q(title__icontains=q) | Q(course_label__icontains=q))
    if params.get('status'):
        queryset = queryset.filter(status=ChoiceField(choices=RevisionSheet.Status.values).run_validation(params['status']))
    if params.get('course'): queryset = queryset.filter(course_label=params['course'][:120])
    if params.get('tag'): queryset = queryset.filter(tags__contains=[params['tag'][:30].lower()])
    if params.get('group'): queryset = queryset.filter(learning_group=get_object(LearningGroup, params['group']))
    scope = params.get('scope')
    if scope == 'mine': queryset = queryset.filter(owner=request.user)
    elif scope == 'groups': queryset = queryset.filter(learning_group__isnull=False).exclude(owner=request.user)
    elif scope == 'pinned': queryset = queryset.filter(pinned=True)
    if request.user.role == 'ADMIN' and params.get('teacher'):
        queryset = queryset.filter(owner=get_object(User, params['teacher']))
    order = {'title': ['title', 'id'], 'created': ['-created_at', 'id']}.get(params.get('sort'), ['-updated_at', 'id'])
    return queryset.order_by('-pinned', *order)


def facets(queryset):
    courses, tags = set(), {}
    stats = {'total': 0, 'published': 0, 'draft': 0, 'archived': 0, 'pinned': 0, 'ai': 0}
    for course, sheet_tags, status, pinned, ai in queryset.values_list('course_label', 'tags', 'status', 'pinned', 'ai_generated'):
        courses.add(course)
        for tag in sheet_tags or []: tags[tag] = tags.get(tag, 0) + 1
        stats['total'] += 1; stats[status.lower()] += 1; stats['pinned'] += pinned; stats['ai'] += ai
    return {'courses': sorted(courses, key=str.casefold), 'stats': stats,
            'tags': [{'name': name, 'count': count} for name, count in sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))]}


# --- Images -----------------------------------------------------------------

def normalized_image(raw, max_bytes=8 * 1024 * 1024):
    """Validate untrusted bytes and re-encode them as WebP (1600 px max). Returns (ContentFile, width, height)."""
    if len(raw) > max_bytes: raise ValidationError({'image': ['La taille maximale est de 8 Mo.']})
    try:
        with Image.open(BytesIO(raw)) as img:
            if img.format not in ('PNG', 'JPEG', 'WEBP') or img.width * img.height > 40_000_000: raise ValueError()
            img.verify()
        with Image.open(BytesIO(raw)) as img:
            img.thumbnail((1600, 1600))
            img = img.convert('RGBA' if img.mode in ('RGBA', 'LA', 'P') else 'RGB')
            output = BytesIO()
            img.save(output, format='WEBP', quality=88, method=4)
            return ContentFile(output.getvalue(), name=f'{uuid4().hex}.webp'), img.width, img.height
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError({'image': ['Choisissez une image PNG, JPEG ou WebP valide (40 mégapixels maximum).']})


def store_image(content):
    # Stored before the transaction: a retried transaction must not write the file twice.
    return default_storage.save(f'illustrations/{content.name}', content)


def next_position(sheet):
    last = Illustration.objects.filter(sheet=sheet).order_by('-position').first()
    return last.position + 1 if last else 1


def delete_sheet_files(sheet):
    names = list(Illustration.objects.filter(sheet=sheet).values_list('image', flat=True))
    Illustration.objects.filter(sheet=sheet).delete()
    return names


def remove_files(names):
    for name in names:
        if name: default_storage.delete(name)


def copy_illustrations(source, target):
    for old in Illustration.objects.filter(sheet=source):
        with default_storage.open(old.image.name, 'rb') as handle:
            name = default_storage.save(f'illustrations/{uuid4().hex}.webp', ContentFile(handle.read()))
        Illustration.objects.create(sheet=target, image=name, caption=old.caption, prompt=old.prompt, source=old.source,
            ai_model=old.ai_model, width=old.width, height=old.height, position=old.position)


# --- Source text ------------------------------------------------------------

def extract_text(upload):
    name = upload.name.lower()
    if name.endswith('.pdf'):
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
        try:
            reader = PdfReader(upload)
            if reader.is_encrypted: raise ValidationError({'file': ['Ce PDF est protégé par un mot de passe.']})
            pages = [page.extract_text() or '' for page in reader.pages[:80]]
        except (PdfReadError, ValueError, KeyError, OSError):
            raise ValidationError({'file': ['Ce PDF est illisible ou endommagé.']})
        text = '\n'.join(pages)
    else:
        raw = upload.read()
        try: text = raw.decode('utf-8-sig')
        except UnicodeDecodeError: text = raw.decode('latin-1')
    text = '\n'.join(line.rstrip() for line in text.splitlines()).strip()
    if len(text) < 80:
        raise ValidationError({'file': ['Le fichier ne contient pas assez de texte exploitable (un PDF scanné doit d’abord être converti en texte).']})
    return text[:60000]


# --- Export -----------------------------------------------------------------

def markdown_export(sheet):
    lines = [f'# {sheet.title}', '', f'**Cours :** {sheet.course_label}  ']
    if sheet.learning_group_id: lines.append(f'**Groupe :** {sheet.learning_group.name}  ')
    lines.append(f'**Auteur :** {sheet.owner.first_name} {sheet.owner.last_name}  ')
    lines.append(f'**Mise à jour :** {timezone.localtime(sheet.updated_at):%d/%m/%Y %H:%M}')
    if sheet.tags: lines += ['', ' '.join(f'`#{tag}`' for tag in sheet.tags)]
    if sheet.summary.strip():
        # Summary titles sit one level below the "## Résumé" section heading.
        summary = '\n'.join('#' + line if line.lstrip().startswith('#') else line for line in sheet.summary.strip().splitlines())
        lines += ['', '## Résumé', '', summary]
    if sheet.key_points: lines += ['', '## Points clés', ''] + [f'{i}. {point}' for i, point in enumerate(sheet.key_points, 1)]
    if sheet.glossary: lines += ['', '## Glossaire', ''] + [f'- **{e["term"]}** — {e["definition"]}' for e in sheet.glossary]
    illustrations = list(Illustration.objects.filter(sheet=sheet))
    if illustrations: lines += ['', '## Illustrations', ''] + [f'- Figure {i} : {ill.caption}' for i, ill in enumerate(illustrations, 1)]
    if sheet.ai_generated:
        lines += ['', '---', '', f'_Contenu généré avec {sheet.ai_model or "Gemini"}'
                  + (' puis relu par son auteur._' if sheet.ai_reviewed else ', non encore relu._')]
    return '\n'.join(lines) + '\n'
