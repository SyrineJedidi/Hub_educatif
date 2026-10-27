"""Voice questions: the recording is transcribed for the student to review, then deleted; it is never stored."""
import contextlib
import logging
import os
import tempfile
from django.conf import settings
from django.http import JsonResponse
from rest_framework.exceptions import APIException, ValidationError
from accounts.views import validated
from ai.transcription import TranscriptionError, get_transcriber
from .models import QUESTION_MAX_LENGTH
from .serializers import TranscriptionSerializer
from .services import consume

logger = logging.getLogger('assistant')

MB = 1024 * 1024
UNSUPPORTED = 'Format audio non pris en charge : enregistrez en WebM, Ogg, MP4 (M4A), WAV ou MP3.'
NO_AUDIO = 'Cet enregistrement ne contient aucune piste audio.'
# Providers that never decode the recording, so there is nothing to measure before calling them.
UNHEARD = {'disabled', 'fake'}


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


def size_message():
    return f'L’enregistrement dépasse la taille maximale de {settings.ASSISTANT_MAX_AUDIO_MB:g} Mo.'


def max_seconds():
    return settings.ASSISTANT_MAX_AUDIO_SECONDS + 2


def too_long():
    return ValidationError({'audio': [f'L’enregistrement dépasse la durée maximale de {settings.ASSISTANT_MAX_AUDIO_SECONDS} secondes.']})


def oversized_body(request):
    """The refusal of a body announced larger than any accepted recording, or None.

    It must run before the view: the CSRF check reads request.POST, which parses the whole multipart body and writes
    its file to disk."""
    try: length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError: length = 0
    # The other form fields and the multipart framing get one extra megabyte.
    if length <= max_bytes() + MB: return None
    # The body of a field error raised in a view; the API's exception handler does not run this early.
    response = JsonResponse({'error': {'code': 'invalid', 'message': 'Veuillez corriger les champs indiqués.', 'fields': {'audio': [size_message()]}}}, status=400)
    response['Cache-Control'] = 'private, no-store'
    return response


def decoded_seconds(path, limit):
    """Seconds of sound the decoder gets out of the file, counted until limit is passed; None without PyAV.

    A declared duration can lie and a low bitrate fits hours in a few megabytes: only decoding tells, and stopping
    past the limit keeps a refusal as cheap as a minute of audio."""
    try: import av
    except ImportError: return None
    seconds = 0.0
    with av.open(path, metadata_errors='ignore') as container:
        if not container.streams.audio: raise ValidationError({'audio': [NO_AUDIO]})
        try:
            for frame in container.decode(audio=0):
                if frame.sample_rate: seconds += frame.samples / frame.sample_rate
                if seconds > limit: break
        except av.error.InvalidDataError:
            # faster-whisper also stops at the first unreadable packet: what came before is what it transcribes.
            pass
    return seconds


def transcribe_question(request):
    consume(request, 'assistant-voice', settings.ASSISTANT_VOICE_PER_HOUR, 3600, str(request.user.pk),
        f'Vous avez atteint la limite de {settings.ASSISTANT_VOICE_PER_HOUR} questions vocales par heure. Écrivez votre question ou réessayez plus tard.')
    data = validated(TranscriptionSerializer, request)
    upload = data['audio']
    if upload.size > max_bytes(): raise ValidationError({'audio': [size_message()]})
    head = upload.read(16)
    upload.seek(0)
    extension = sniff(head)
    if not extension: raise ValidationError({'audio': [UNSUPPORTED]})
    language = data.get('language') or settings.WHISPER_LANGUAGE or None
    descriptor, path = tempfile.mkstemp(prefix='assistant-voice-', suffix=f'.{extension}')
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            for chunk in upload.chunks(): handle.write(chunk)
        transcriber = get_transcriber()
        # Refused before the provider spends its time, or the shared Groq quota, on a long recording.
        if transcriber.name not in UNHEARD and (decoded_seconds(path, max_seconds()) or 0) > max_seconds(): raise too_long()
        transcript = transcriber.transcribe(path, language=language)
    except TranscriptionError as exc:
        raise (TranscriptionUnavailable if exc.retryable else TranscriptionFailed)(exc.message)
    except APIException:
        raise
    except Exception:
        # A file the decoder cannot read, or a provider reply cut short. The traceback holds no text of the recording.
        logger.exception('assistant transcription failed')
        raise TranscriptionFailed()
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(path)
    if transcript.duration and transcript.duration > max_seconds(): raise too_long()
    text = ' '.join(s.text.strip() for s in transcript.segments if s.text.strip())[:QUESTION_MAX_LENGTH].strip()
    if not text: raise ValidationError({'audio': ['Aucune parole détectée.']})
    return {'text': text, 'language': transcript.language or language or '',
        'duration_seconds': round(transcript.duration, 1) if transcript.duration is not None else None}
