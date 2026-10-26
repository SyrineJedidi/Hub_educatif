import hashlib
import importlib.util
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from uuid import uuid4
from django.conf import settings
from django.db import connection

GROQ_URL = 'https://api.groq.com/openai/v1/audio/transcriptions'
GROQ_MAX_BYTES = 25 * 1024 * 1024
LANGUAGE_CODES = {'french': 'fr', 'english': 'en', 'arabic': 'ar', 'spanish': 'es', 'german': 'de', 'italian': 'it', 'portuguese': 'pt', 'dutch': 'nl', 'turkish': 'tr'}


class TranscriptionError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    segments: list = field(default_factory=list)
    language: str = ''
    duration: float | None = None
    provider: str = ''
    model: str = ''


def language_code(value):
    value = str(value or '').strip().lower()
    return LANGUAGE_CODES.get(value, value)[:8]


class DisabledTranscriber:
    name = 'disabled'
    model = ''

    def transcribe(self, path, language=None):
        raise TranscriptionError('La transcription automatique n’est pas configurée sur ce serveur.')


class FakeTranscriber:
    """Deterministic output for tests and browser scenarios."""
    name = 'fake'
    model = 'fake-whisper'

    def transcribe(self, path, language=None):
        with open(path, 'rb') as handle:
            prefix = hashlib.sha256(handle.read()).hexdigest()[:8]
        segments = [TranscriptSegment(5.0 * i, 5.0 * (i + 1), f'Transcription de démonstration {prefix}, partie {i + 1}.') for i in range(3)]
        return Transcript(segments, 'fr', 15.0, self.name, self.model)


_local_models = {}


class LocalTranscriber:
    name = 'local'

    def __init__(self):
        self.model = settings.WHISPER_MODEL

    def load(self):
        key = (self.model, settings.WHISPER_CPU_THREADS)
        if key not in _local_models:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise TranscriptionError('faster-whisper n’est pas installé sur ce serveur : installez backend/requirements-whisper.txt.')
            # Loading takes seconds and hundreds of MB: keep one model per process.
            _local_models[key] = WhisperModel(self.model, device='cpu', compute_type='int8', cpu_threads=settings.WHISPER_CPU_THREADS)
        return _local_models[key]

    def transcribe(self, path, language=None):
        segments, info = self.load().transcribe(path, language=language or None, vad_filter=True, beam_size=5)
        # Segments are decoded lazily: refuse long recordings before paying for them.
        if info.duration and info.duration > settings.COURSES_MAX_AUDIO_SECONDS:
            raise TranscriptionError(f'Cet enregistrement dépasse la durée maximale de {settings.COURSES_MAX_AUDIO_SECONDS // 60} minutes.')
        items = [TranscriptSegment(float(s.start), float(s.end), s.text.strip()) for s in segments]
        return Transcript(items, language_code(info.language), float(info.duration or 0), self.name, self.model)


class GroqTranscriber:
    name = 'groq'

    def __init__(self):
        self.model = settings.GROQ_WHISPER_MODEL

    def body(self, path, language, boundary):
        fields = [('model', self.model), ('response_format', 'verbose_json'), ('timestamp_granularities[]', 'segment')]
        if language: fields.append(('language', language))
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode() for name, value in fields]
        with open(path, 'rb') as handle:
            content = handle.read()
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + content + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        return b''.join(parts)

    def transcribe(self, path, language=None):
        if not settings.GROQ_API_KEY:
            raise TranscriptionError('La transcription automatique n’est pas configurée sur ce serveur.')
        if os.path.getsize(path) > GROQ_MAX_BYTES:
            raise TranscriptionError('Ce fichier dépasse la limite de 25 Mo du service de transcription.')
        boundary = uuid4().hex
        request = urllib.request.Request(GROQ_URL, data=self.body(path, language, boundary), method='POST', headers={
            'Authorization': f'Bearer {settings.GROQ_API_KEY}', 'Content-Type': f'multipart/form-data; boundary={boundary}', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise TranscriptionError('Clé du service de transcription invalide.')
            if exc.code == 429 or exc.code >= 500:
                raise TranscriptionError('Le service de transcription est momentanément indisponible.', retryable=True)
            raise TranscriptionError('Le service de transcription a refusé ce fichier audio.')
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TranscriptionError('Le service de transcription ne répond pas.', retryable=True)
        except ValueError:
            raise TranscriptionError('Réponse inattendue du service de transcription.', retryable=True)
        try:
            segments = [TranscriptSegment(float(s['start']), float(s['end']), str(s['text']).strip()) for s in payload.get('segments') or []]
            duration = float(payload['duration']) if payload.get('duration') is not None else None
        except (AttributeError, KeyError, TypeError, ValueError):
            raise TranscriptionError('Réponse inattendue du service de transcription.', retryable=True)
        return Transcript(segments, language_code(payload.get('language') or language), duration, self.name, self.model)


PROVIDERS = {'disabled': DisabledTranscriber, 'fake': FakeTranscriber, 'local': LocalTranscriber, 'groq': GroqTranscriber}


def get_transcriber():
    provider = PROVIDERS.get(settings.WHISPER_PROVIDER, DisabledTranscriber)
    # Test databases must never reach a real model or the network.
    if provider in (LocalTranscriber, GroqTranscriber) and str(connection.settings_dict['NAME']).startswith('test_'):
        raise TranscriptionError('Les fournisseurs de transcription réels sont désactivés sur une base de test.')
    return provider()


def provider_status():
    provider = settings.WHISPER_PROVIDER if settings.WHISPER_PROVIDER in PROVIDERS else 'disabled'
    configured = {'disabled': False, 'fake': True, 'groq': bool(settings.GROQ_API_KEY),
        'local': importlib.util.find_spec('faster_whisper') is not None}[provider]
    model = {'disabled': '', 'fake': FakeTranscriber.model, 'groq': settings.GROQ_WHISPER_MODEL, 'local': settings.WHISPER_MODEL}[provider]
    return {'provider': provider, 'configured': configured, 'model': model}
