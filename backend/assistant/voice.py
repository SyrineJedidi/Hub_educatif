"""Voice questions: the recording is transcribed for the student to review, then deleted; it is never stored."""
import contextlib
import os
import tempfile
from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError
from accounts.views import validated
from ai.transcription import TranscriptionError, get_transcriber
from .models import QUESTION_MAX_LENGTH
from .serializers import TranscriptionSerializer
from .services import consume

MB = 1024 * 1024
UNSUPPORTED = 'Format audio non pris en charge : enregistrez en WebM, Ogg, MP4 (M4A), WAV ou MP3.'


class TranscriptionUnavailable(APIException):
    status_code = 503
    default_detail = 'Le service de transcription est momentanément indisponible. Réessayez ou écrivez votre question.'
    default_code = 'transcription_unavailable'


class TranscriptionFailed(APIException):
    status_code = 400
    default_detail = 'La transcription de cet enregistrement a échoué.'
    default_code = 'transcription_failed'


def sniff(head):
    """File extension from magic bytes; the client's name and Content-Type are ignored."""
    if head[:4] == b'\x1a\x45\xdf\xa3': return 'webm'
    if head[:4] == b'OggS': return 'ogg'
    if head[4:8] == b'ftyp': return 'm4a'
    if head[:4] == b'RIFF' and head[8:12] == b'WAVE': return 'wav'
    if head[:3] == b'ID3' or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0): return 'mp3'
    return None


def max_bytes():
    return int(settings.ASSISTANT_MAX_AUDIO_MB * MB)


def too_large():
    return ValidationError({'audio': [f'L’enregistrement dépasse la taille maximale de {settings.ASSISTANT_MAX_AUDIO_MB:g} Mo.']})


def reject_oversized_body(request):
    # Checked before the multipart body is parsed and spooled to disk.
    try: length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError: length = 0
    if length > max_bytes() + MB: raise too_large()


def transcribe_question(request):
    consume(request, 'assistant-voice', settings.ASSISTANT_VOICE_PER_HOUR, 3600, str(request.user.pk),
        f'Vous avez atteint la limite de {settings.ASSISTANT_VOICE_PER_HOUR} questions vocales par heure. Écrivez votre question ou réessayez plus tard.')
    reject_oversized_body(request)
    data = validated(TranscriptionSerializer, request)
    upload = data['audio']
    if upload.size > max_bytes(): raise too_large()
    head = upload.read(16)
    upload.seek(0)
    extension = sniff(head)
    if not extension: raise ValidationError({'audio': [UNSUPPORTED]})
    language = data.get('language') or settings.WHISPER_LANGUAGE or None
    descriptor, path = tempfile.mkstemp(prefix='assistant-voice-', suffix=f'.{extension}')
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            for chunk in upload.chunks(): handle.write(chunk)
        transcript = get_transcriber().transcribe(path, language=language)
    except TranscriptionError as exc:
        raise (TranscriptionUnavailable if exc.retryable else TranscriptionFailed)(exc.message)
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(path)
    if transcript.duration and transcript.duration > settings.ASSISTANT_MAX_AUDIO_SECONDS + 2:
        raise ValidationError({'audio': [f'L’enregistrement dépasse la durée maximale de {settings.ASSISTANT_MAX_AUDIO_SECONDS} secondes.']})
    text = ' '.join(s.text.strip() for s in transcript.segments if s.text.strip())[:QUESTION_MAX_LENGTH].strip()
    if not text: raise ValidationError({'audio': ['Aucune parole détectée.']})
    return {'text': text, 'language': transcript.language or language or '',
        'duration_seconds': round(transcript.duration, 1) if transcript.duration is not None else None}
