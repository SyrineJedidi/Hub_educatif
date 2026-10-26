import hashlib
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote
from uuid import uuid4
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, StreamingHttpResponse
from pypdf import PdfReader
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from classrooms.services import mutation
from .models import ProcessingJob, Resource
from .services import body_chapter, editable, managed_course, model_errors, next_position

UNSUPPORTED = 'Format non pris en charge : importez un PDF ou un fichier audio (MP3, M4A, WAV, OGG, WEBM, FLAC).'
MB = 1024 * 1024


@dataclass
class Upload:
    file: object
    kind: str
    mime_type: str
    extension: str
    size: int
    sha256: str
    original_name: str
    page_count: int | None = None


def sniff(head):
    """Kind, MIME type and extension from magic bytes; the client's name and Content-Type are ignored."""
    if b'%PDF-' in head[:1024]: return 'PDF', 'application/pdf', 'pdf'
    if head[:3] == b'ID3' or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0): return 'AUDIO', 'audio/mpeg', 'mp3'
    if head[:4] == b'RIFF' and head[8:12] == b'WAVE': return 'AUDIO', 'audio/wav', 'wav'
    if head[:4] == b'OggS': return 'AUDIO', 'audio/ogg', 'ogg'
    if head[:4] == b'\x1a\x45\xdf\xa3': return 'AUDIO', 'audio/webm', 'webm'
    if head[4:8] == b'ftyp': return 'AUDIO', 'audio/mp4', 'm4a'
    if head[:4] == b'fLaC': return 'AUDIO', 'audio/flac', 'flac'
    raise ValidationError({'file': [UNSUPPORTED]})


def size_limit(kind):
    megabytes = settings.COURSES_MAX_PDF_MB if kind == 'PDF' else settings.COURSES_MAX_AUDIO_MB
    return int(megabytes * MB), f'{megabytes:g} Mo'


def reject_oversized_body(request):
    # Checked before DRF parses (and spools) the multipart body.
    largest = max(settings.COURSES_MAX_PDF_MB, settings.COURSES_MAX_AUDIO_MB)
    try: length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError: length = 0
    if length > int(largest * MB) + MB:
        raise ValidationError({'file': [f'Le fichier dépasse la taille maximale autorisée ({largest:g} Mo).']})


def clean_name(name, extension):
    name = str(name or '').replace('\\', '/').rsplit('/', 1)[-1]
    name = ' '.join(''.join(c for c in name if unicodedata.category(c)[0] != 'C').split()).strip()
    if len(name) > 180:
        stem, dot, suffix = name.rpartition('.')
        name = stem[:179 - len(suffix)] + dot + suffix if dot and len(suffix) <= 10 else name[:180]
    return name or f'ressource.{extension}'


def inspect_pdf(upload):
    try:
        reader = PdfReader(upload)
        if reader.is_encrypted:
            try: decrypted = reader.decrypt('')
            except Exception: decrypted = 0
            if not decrypted:
                raise ValidationError({'file': ['Ce PDF est protégé par un mot de passe : retirez la protection avant de l’importer.']})
        pages = len(reader.pages)
    except ValidationError:
        raise
    except Exception:
        # pypdf raises many exception types on damaged files.
        raise ValidationError({'file': ['Ce fichier PDF est illisible ou endommagé.']})
    if not pages: raise ValidationError({'file': ['Ce fichier PDF est illisible ou endommagé.']})
    if pages > settings.COURSES_MAX_PDF_PAGES:
        raise ValidationError({'file': [f'Ce PDF compte {pages} pages : la limite est de {settings.COURSES_MAX_PDF_PAGES} pages.']})
    return pages


def inspect_upload(file):
    file.seek(0)
    head = file.read(1024)
    if not head: raise ValidationError({'file': ['Le fichier est vide.']})
    kind, mime_type, extension = sniff(head)
    limit, label = size_limit(kind)
    if file.size > limit:
        raise ValidationError({'file': [f'Ce fichier dépasse la taille maximale de {label} pour ce type de ressource.']})
    digest = hashlib.sha256()
    file.seek(0)
    for chunk in file.chunks(): digest.update(chunk)
    file.seek(0)
    upload = Upload(file, kind, mime_type, extension, file.size, digest.hexdigest(), clean_name(file.name, extension))
    if kind == 'PDF':
        upload.page_count = inspect_pdf(file)
        file.seek(0)
    return upload


def store(upload):
    upload.file.seek(0)
    return default_storage.save(f'courses/{uuid4().hex}.{upload.extension}', upload.file)


@mutation
def create_resource(_self, request, course_id, data, upload, name):
    course = managed_course(request.user, course_id); editable(course)
    chapter = body_chapter(course, data['chapter_id'])
    duplicate = Resource.objects.filter(course=course, sha256=upload.sha256).first()
    if duplicate: raise ValidationError({'file': [f'Ce fichier existe déjà dans ce cours : « {duplicate.title} ».']})
    resource = Resource(course=course, chapter=chapter, kind=upload.kind, title=data['title'], description=data.get('description', ''),
        position=next_position(Resource.objects.filter(chapter=chapter)), original_name=upload.original_name,
        file=name, mime_type=upload.mime_type, size=upload.size, sha256=upload.sha256, page_count=upload.page_count, uploaded_by=request.user)
    model_errors(resource)
    resource.save()
    job = ProcessingJob.objects.create(resource=resource, kind='EXTRACT_PDF' if upload.kind == 'PDF' else 'TRANSCRIBE_AUDIO')
    course.save(update_fields=['updated_at'])
    return resource, job


def disposition(kind, name):
    fallback = ''.join(c if c.isascii() and c.isprintable() and c not in '"\\' else '_' for c in name)
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def byte_range(header, size):
    """(start, end) for a single satisfiable range, None to send the whole file, False when unsatisfiable."""
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header.strip())
    if not match or match.groups() == ('', ''): return None
    first, last = match.groups()
    if first == '':
        length = int(last)
        if not length or not size: return False
        return max(0, size - length), size - 1
    start = int(first)
    if start >= size: return False
    end = min(int(last), size - 1) if last else size - 1
    if end < start: return None
    return start, end


def ranged_chunks(handle, length, block=64 * 1024):
    try:
        while length > 0:
            data = handle.read(min(block, length))
            if not data: break
            length -= len(data)
            yield data
    finally:
        handle.close()


def file_response(request, resource):
    storage, name = resource.file.storage, resource.file.name
    try:
        size = storage.size(name)
        handle = storage.open(name, 'rb')
    except OSError:
        raise NotFound('Fichier introuvable.')
    selected = byte_range(request.META.get('HTTP_RANGE', ''), size) if request.META.get('HTTP_RANGE') else None
    if selected is False:
        handle.close()
        response = Response({'error': {'code': 'range_not_satisfiable', 'message': 'La plage demandée est invalide.', 'fields': {}}}, status=416)
        response['Content-Range'] = f'bytes */{size}'
        return response
    if selected:
        start, end = selected
        handle.seek(start)
        response = StreamingHttpResponse(ranged_chunks(handle, end - start + 1), status=206, content_type=resource.mime_type)
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
        response['Content-Length'] = str(end - start + 1)
    else:
        response = FileResponse(handle, content_type=resource.mime_type)
        response['Content-Length'] = str(size)
    response['Content-Disposition'] = disposition('attachment' if request.query_params.get('download') == '1' else 'inline', resource.original_name)
    response['Accept-Ranges'] = 'bytes'
    # The global DENY stays in force everywhere else; the viewer embeds the PDF in a same-origin iframe.
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response
