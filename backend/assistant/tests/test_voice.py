import glob
import hashlib
import http.client
import importlib.machinery
import json
import os
import shutil
import sys
import tempfile
import urllib.error
from io import BytesIO
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.db import connection
from django.http import HttpRequest
from django.http.multipartparser import MultiPartParser
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import RateBucket
from ai import transcription
from ai.transcription import (DisabledTranscriber, FakeTranscriber, GroqTranscriber, LocalTranscriber, Transcript, TranscriptSegment, TranscriptionError,
    get_transcriber, language_code, provider_status)
from assistant.models import Message
from assistant.services import bucket_key
from .base import AssistantTestCase

# Smallest payloads each magic-byte rule accepts, with the extension the temporary file gets.
AUDIO = {
    'webm': (b'\x1a\x45\xdf\xa3' + b'\x02' * 200, '.webm'),
    'ogg': (b'OggS' + b'\x01' * 200, '.ogg'),
    'm4a': (b'\x00\x00\x00\x20ftypM4A ' + b'\x03' * 200, '.m4a'),
    'wav': (b'RIFF\x24\x00\x00\x00WAVEfmt ' + b'\x00' * 200, '.wav'),
    'mp3-id3': (b'ID3\x04\x00' + b'\x05' * 200, '.mp3'),
    'mp3-sync': (b'\xff\xfb\x90\x00' + b'\x00' * 200, '.mp3'),
}
OGG = AUDIO['ogg'][0]
URLOPEN = 'urllib.request.urlopen'


def fake_text(content):
    prefix = hashlib.sha256(content).hexdigest()[:8]
    return ' '.join(f'Transcription de démonstration {prefix}, partie {n}.' for n in (1, 2, 3))


def pyav(frames=(), audio=True, error=None):
    """Stand-in for PyAV: frames are (samples, sample rate) pairs, decoded one at a time; 'invalid' is an unreadable packet."""
    module = ModuleType('av')
    module.error = SimpleNamespace(InvalidDataError=type('InvalidDataError', (ValueError,), {}))
    module.opened, module.decoded, module.selection = [], [], None
    class Container:
        def __init__(self, path, options):
            module.opened.append((path, options)); self.streams = SimpleNamespace(audio=(object(),) if audio else ())
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def decode(self, **selection):
            module.selection = selection
            for frame in frames:
                if frame == 'invalid': raise module.error.InvalidDataError('Invalid data found when processing input')
                module.decoded.append(frame); yield SimpleNamespace(samples=frame[0], sample_rate=frame[1])
    def open_(path, **options):
        if error: raise error
        return Container(path, options)
    module.open = open_
    return module


class VoiceQuestionTests(AssistantTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.media, True)
        media = override_settings(MEDIA_ROOT=self.media); media.enable(); self.addCleanup(media.disable)
        self.paths = []

    def post(self, data, client=None, **extra):
        return (client or self.student_client).post('/api/assistant/transcriptions/', data, format='multipart', **extra)

    def audio(self, content=OGG, name='question.ogg', content_type='audio/ogg'):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def transcriber(self, result=None, error=None):
        """Replaces the fake transcriber's work; records the temporary path, the language and whether a transaction was open."""
        def transcribe(_, path, language=None):
            self.paths.append((path, language, os.path.exists(path), connection.in_atomic_block_mongo))
            if error: raise error
            return result
        return patch.object(FakeTranscriber, 'transcribe', transcribe)

    def assert_no_temporary_file(self):
        self.assertTrue(self.paths)
        self.assertFalse([path for path, *_ in self.paths if os.path.exists(path)])
        self.assertTrue(all(exists and not atomic for _, _, exists, atomic in self.paths))

    def test_every_supported_format_is_transcribed_for_review(self):
        real = FakeTranscriber.transcribe
        extensions = []
        def spy(transcriber, path, language=None):
            extensions.append(os.path.splitext(path)[1]); self.paths.append((path, language, True, connection.in_atomic_block_mongo))
            return real(transcriber, path, language)
        with patch.object(FakeTranscriber, 'transcribe', spy), self.settings(ASSISTANT_VOICE_PER_HOUR=50):
            for name, (content, _) in AUDIO.items():
                with self.subTest(format=name):
                    # The name and type sent by the browser are ignored: only the bytes count.
                    response = self.post({'audio': self.audio(content, 'enregistrement.bin', 'application/octet-stream')})
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data, {'text': fake_text(content), 'language': 'fr', 'duration_seconds': 15.0})
        self.assertEqual(extensions, [extension for _, extension in AUDIO.values()])
        self.assertTrue(all(os.path.basename(path).startswith('assistant-voice-') for path, *_ in self.paths))
        self.assert_no_temporary_file()
        # Never sent on its own, never stored.
        self.assertEqual((Message.objects.count(), os.listdir(self.media)), (0, []))
        self.assertEqual(self.post({'audio': self.audio()}, self.teacher_client).status_code, 200)

    def test_unsupported_or_missing_audio(self):
        for content in (b'fLaC' + b'\x00' * 50, b'<svg></svg>' * 10, b'RIFF\x24\x00\x00\x00AVI LIST' + b'\x00' * 50, b'\x00' * 64, b'\xff'):
            with self.subTest(content=content[:8]):
                response = self.post({'audio': self.audio(content)})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['error']['fields'], {'audio': ['Format audio non pris en charge : enregistrez en WebM, Ogg, MP4 (M4A), WAV ou MP3.']})
        self.assertEqual(self.post({}).data['error']['fields'], {'audio': ['Joignez un enregistrement audio.']})
        self.assertEqual(self.post({'audio': self.audio(b'')}).data['error']['fields'], {'audio': ['L’enregistrement audio est vide.']})
        self.assertIn('text', self.post({'audio': self.audio(), 'text': 'déjà écrit'}).data['error']['fields'])
        self.assertIn('language', self.post({'audio': self.audio(), 'language': 'de'}).data['error']['fields'])
        self.assertEqual(self.student_client.post('/api/assistant/transcriptions/', {'audio': 'texte'}, format='json').status_code, 400)

    @override_settings(ASSISTANT_MAX_AUDIO_MB=0.001)
    def test_size_limit(self):
        error = self.post({'audio': self.audio(OGG + b'\x00' * 2000)}).data['error']
        self.assertEqual(error['fields'], {'audio': ['L’enregistrement dépasse la taille maximale de 0.001 Mo.']})
        # A body far above the limit is refused from its length, before anything parses it and writes it to disk:
        # the CSRF check itself reads the form, so it runs after.
        client = APIClient(enforce_csrf_checks=True); client.force_login(self.student)
        token = client.get('/api/csrf/').data['csrfToken']
        with patch.object(HttpRequest, '_load_post_and_files', side_effect=AssertionError('parsed')):
            for headers in ({'HTTP_X_CSRFTOKEN': token}, {}):
                response = client.post('/api/assistant/transcriptions/', {'audio': self.audio(OGG + b'\x00' * (1100 * 1024))}, format='multipart', **headers)
                self.assertEqual((response.status_code, response['Cache-Control']), (400, 'private, no-store'))
                self.assertEqual(response.json(), {'error': {'code': 'invalid', 'message': 'Veuillez corriger les champs indiqués.',
                    'fields': {'audio': ['L’enregistrement dépasse la taille maximale de 0.001 Mo.']}}})
            self.assertEqual(APIClient().post('/api/assistant/transcriptions/', {'audio': self.audio(OGG + b'\x00' * (1100 * 1024))}, format='multipart').status_code, 400)
        # Only the first, smaller recording reached the view and its hourly limit.
        self.assertEqual(RateBucket.objects.get(key=bucket_key('assistant-voice', str(self.student.pk), 3600)).hits, 1)
        self.assertEqual(client.post('/api/assistant/transcriptions/', {'audio': self.audio(OGG + b'\x00' * 700)}, format='multipart', HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(self.post({'audio': self.audio()}, CONTENT_LENGTH='beaucoup').status_code, 400)

    def test_duration_limit_and_empty_speech(self):
        cases = [(Transcript([TranscriptSegment(0, 62.5, 'Trop long.')], 'fr', 62.5), {'audio': ['L’enregistrement dépasse la durée maximale de 60 secondes.']}),
            (Transcript([TranscriptSegment(0, 2, '   '), TranscriptSegment(2, 3, '')], 'fr', 3.0), {'audio': ['Aucune parole détectée.']}),
            (Transcript([], 'fr', 1.0), {'audio': ['Aucune parole détectée.']})]
        for transcript, fields in cases:
            with self.subTest(transcript=transcript), self.transcriber(transcript):
                response = self.post({'audio': self.audio()})
                self.assertEqual((response.status_code, response.data['error']['fields']), (400, fields))
        with self.transcriber(Transcript([TranscriptSegment(0, 62, ' Juste ')], '', 62.0)):
            self.assertEqual(self.post({'audio': self.audio()}).data, {'text': 'Juste', 'language': '', 'duration_seconds': 62.0})
        self.assert_no_temporary_file()

    def test_text_language_and_duration_are_tidied(self):
        segments = [TranscriptSegment(0, 1, ' Bonjour '), TranscriptSegment(1, 2, ''), TranscriptSegment(2, 3, 'la norme ? ')]
        with self.transcriber(Transcript(segments, '', 12.345)):
            self.assertEqual(self.post({'audio': self.audio(), 'language': 'ar'}).data, {'text': 'Bonjour la norme ?', 'language': 'ar', 'duration_seconds': 12.3})
            with self.settings(WHISPER_LANGUAGE='en'): self.post({'audio': self.audio()})
            self.post({'audio': self.audio()})
        self.assertEqual([language for _, language, *_ in self.paths], ['ar', 'en', None])
        with self.transcriber(Transcript([TranscriptSegment(0, 1, 'mot ' * 600)], 'fr', None)):
            data = self.post({'audio': self.audio()}).data
        self.assertEqual((len(data['text']), data['duration_seconds']), (1999, None))

    def test_transcription_errors(self):
        cases = [(TranscriptionError('Le service de transcription est momentanément indisponible.', retryable=True), 503, 'transcription_unavailable'),
            (TranscriptionError('Le service de transcription a refusé ce fichier audio.'), 400, 'transcription_failed')]
        for error, status, code in cases:
            with self.subTest(code=code), self.transcriber(error=error):
                self.assertEqual(self.refused(self.post({'audio': self.audio()}), status, code)['message'], error.message)
        with self.settings(WHISPER_PROVIDER='disabled'):
            self.assertEqual(self.refused(self.post({'audio': self.audio()}), 400, 'transcription_failed')['message'],
                'La transcription automatique n’est pas configurée sur ce serveur.')
        self.assert_no_temporary_file()

    def test_real_providers_never_run_against_the_test_database(self):
        for provider in ('groq', 'local'):
            with self.subTest(provider=provider), self.settings(WHISPER_PROVIDER=provider, GROQ_API_KEY='test-groq-key'), patch(URLOPEN, side_effect=AssertionError('network')) as urlopen:
                error = self.refused(self.post({'audio': self.audio()}), 400, 'transcription_failed')
                self.assertEqual(error['message'], 'Les fournisseurs de transcription réels sont désactivés sur une base de test.')
                self.assertFalse(urlopen.called)

    def test_unexpected_errors_become_a_failed_transcription(self):
        # An undecodable file from the local decoder, or a reply from Groq cut short.
        for failure in (RuntimeError('décodeur en panne'), http.client.IncompleteRead(b'{"text": "Bonj')):
            with self.subTest(failure=type(failure).__name__), self.transcriber(error=failure), self.assertLogs('assistant', 'ERROR') as logs:
                error = self.refused(self.post({'audio': self.audio()}), 400, 'transcription_failed')
            self.assertEqual(error['message'], 'La transcription de cet enregistrement a échoué.')
            self.assertIn('assistant transcription failed', logs.output[0])
        self.assert_no_temporary_file()
        self.assertFalse(glob.glob(os.path.join(tempfile.gettempdir(), 'assistant-voice-*')))

    def measured(self, av, provider, data=None):
        with patch.dict(sys.modules, {'av': av}), patch('assistant.voice.get_transcriber', return_value=provider):
            return self.post(data or {'audio': self.audio()})

    def test_a_long_recording_is_refused_before_the_provider_runs(self):
        # Opus at 6 kbit/s fits more than an hour and a half in 5 MB, and a declared duration can lie: decoding tells.
        calls = []
        provider = SimpleNamespace(name='local', transcribe=lambda path, language=None: calls.append(path))
        av = pyav([(48000, 48000)] * 6300)
        response = self.measured(av, provider)
        self.assertEqual((response.status_code, response.data['error']['fields']), (400, {'audio': ['L’enregistrement dépasse la durée maximale de 60 secondes.']}))
        # Decoding stops just past the limit of 60 s plus 2 s of margin, and the provider is never called.
        self.assertEqual((len(av.decoded), calls, av.selection), (63, [], {'audio': 0}))
        (path, options), = av.opened
        self.assertEqual((options, os.path.exists(path)), ({'metadata_errors': 'ignore'}, False))

    def test_a_recording_within_the_limit_is_measured_then_transcribed(self):
        calls = []
        def transcribe(path, language=None):
            calls.append(language); return Transcript([TranscriptSegment(0, 61.5, 'La norme ?')], 'fr', 61.5)
        for name in ('local', 'groq'):
            with self.subTest(provider=name):
                av = pyav([(16000, 16000)] * 61 + [(8000, 16000)])
                response = self.measured(av, SimpleNamespace(name=name, transcribe=transcribe), {'audio': self.audio(), 'language': 'fr'})
                self.assertEqual((response.status_code, response.data), (200, {'text': 'La norme ?', 'language': 'fr', 'duration_seconds': 61.5}))
                self.assertEqual(len(av.decoded), 62)
        self.assertEqual(calls, ['fr', 'fr'])
        # The decoder stops at the first unreadable packet, as faster-whisper does: what came before is measured.
        av = pyav([(16000, 16000)] * 10 + ['invalid'] + [(16000, 16000)] * 100)
        self.assertEqual(self.measured(av, SimpleNamespace(name='local', transcribe=transcribe)).status_code, 200)
        self.assertEqual(len(av.decoded), 10)

    def test_files_without_readable_sound_are_refused(self):
        calls = []
        provider = SimpleNamespace(name='local', transcribe=lambda path, language=None: calls.append(path))
        # A screen recording without its sound, for instance.
        response = self.measured(pyav(audio=False), provider)
        self.assertEqual((response.status_code, response.data['error']['fields']), (400, {'audio': ['Cet enregistrement ne contient aucune piste audio.']}))
        # Right magic bytes, then garbage.
        broken = pyav()
        broken.open = Mock(side_effect=broken.error.InvalidDataError('Invalid data found when processing input'))
        with self.assertLogs('assistant', 'ERROR'):
            self.refused(self.measured(broken, provider), 400, 'transcription_failed')
        self.assertEqual(calls, [])

    def test_without_pyav_the_reported_duration_still_decides(self):
        provider = SimpleNamespace(name='groq', transcribe=lambda path, language=None: Transcript([TranscriptSegment(0, 6300, 'Cours entier.')], 'fr', 6300.0))
        response = self.measured(None, provider)
        self.assertEqual((response.status_code, response.data['error']['fields']), (400, {'audio': ['L’enregistrement dépasse la durée maximale de 60 secondes.']}))

    def test_providers_that_ignore_the_audio_are_not_measured(self):
        with patch.dict(sys.modules, {'av': pyav(error=AssertionError('measured'))}):
            self.assertEqual(self.post({'audio': self.audio()}).status_code, 200)
            with self.settings(WHISPER_PROVIDER='disabled'): self.refused(self.post({'audio': self.audio()}), 400, 'transcription_failed')

    @override_settings(ASSISTANT_VOICE_PER_HOUR=2)
    def test_hourly_limit_per_user(self):
        for _ in range(2): self.assertEqual(self.post({'audio': self.audio()}).status_code, 200)
        response = self.post({'audio': self.audio()})
        error = self.refused(response, 429, 'quota_exceeded')
        self.assertEqual(error['message'], 'Vous avez atteint la limite de 2 questions vocales par heure. Écrivez votre question ou réessayez plus tard.')
        self.assertTrue(1 <= int(response['Retry-After']) <= 3600)
        self.assertEqual(RateBucket.objects.get(key=bucket_key('assistant-voice', str(self.student.pk), 3600)).hits, 2)
        self.assertEqual(self.post({'audio': self.audio()}, self.teacher_client).status_code, 200)


@override_settings(WHISPER_PROVIDER='fake', WHISPER_MODEL='small', WHISPER_CPU_THREADS=2, GROQ_API_KEY='test-groq-key', GROQ_WHISPER_MODEL='whisper-large-v3-turbo',
    COURSES_MAX_AUDIO_SECONDS=7200)
class TranscriberTests(SimpleTestCase):
    """The shared transcription module, as the voice questions use it."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.folder, True)
        # Local models are cached per process: one test's stand-in must not serve the next one.
        models = patch.dict(transcription._local_models, clear=True); models.start(); self.addCleanup(models.stop)

    def audio(self, content=OGG, name='question.ogg', size=None):
        path = os.path.join(self.folder, name)
        with open(path, 'wb') as handle:
            handle.write(content)
            if size is not None: handle.truncate(size)
        return path

    def refused(self, call, message, retryable=False):
        with self.assertRaises(TranscriptionError) as caught: call()
        self.assertEqual((caught.exception.message, str(caught.exception), caught.exception.retryable), (message, message, retryable))

    def test_provider_choice_and_the_test_database_guard(self):
        server = SimpleNamespace(settings_dict={'NAME': 'nexora_hub'})
        cases = {'disabled': DisabledTranscriber, 'fake': FakeTranscriber, 'local': LocalTranscriber, 'groq': GroqTranscriber, 'openai': DisabledTranscriber}
        with patch('ai.transcription.connection', server), patch.dict(sys.modules, {'faster_whisper': None}):
            for value, provider in cases.items():
                with self.subTest(provider=value), self.settings(WHISPER_PROVIDER=value): self.assertIs(type(get_transcriber()), provider)
        with patch('ai.transcription.connection', SimpleNamespace(settings_dict={'NAME': 'test_nexora'})):
            for value in ('local', 'groq'):
                with self.subTest(provider=value), self.settings(WHISPER_PROVIDER=value):
                    self.refused(get_transcriber, 'Les fournisseurs de transcription réels sont désactivés sur une base de test.')
        self.refused(lambda: DisabledTranscriber().transcribe(self.audio()), 'La transcription automatique n’est pas configurée sur ce serveur.')

    def test_fake_transcript_depends_only_on_the_content(self):
        expected = Transcript([TranscriptSegment(5.0 * i, 5.0 * (i + 1), f'Transcription de démonstration {hashlib.sha256(OGG).hexdigest()[:8]}, partie {i + 1}.')
            for i in range(3)], 'fr', 15.0, 'fake', 'fake-whisper')
        self.assertEqual([FakeTranscriber().transcribe(self.audio()), FakeTranscriber().transcribe(self.audio(name='copie.webm'), language='en')], [expected] * 2)

    def test_language_names_become_codes(self):
        self.assertEqual([language_code(v) for v in ('French', ' english ', 'ARABIC', 'fr', '', None, 'Vietnamese')], ['fr', 'en', 'ar', 'fr', '', '', 'vietname'])

    def test_groq_request_and_answer(self):
        path = self.audio()
        body = {'language': 'French', 'duration': 9.5, 'segments': [{'start': 0, 'end': 4.25, 'text': ' Bonjour. '}, {'start': '4.25', 'end': 9.5, 'text': 'La norme.'}]}
        with patch(URLOPEN, return_value=BytesIO(json.dumps(body).encode())) as urlopen:
            transcript = GroqTranscriber().transcribe(path, language='fr')
        self.assertEqual(transcript, Transcript([TranscriptSegment(0.0, 4.25, 'Bonjour.'), TranscriptSegment(4.25, 9.5, 'La norme.')], 'fr', 9.5, 'groq', 'whisper-large-v3-turbo'))
        request = urlopen.call_args.args[0]
        self.assertEqual((request.full_url, request.get_method(), urlopen.call_args.kwargs), (transcription.GROQ_URL, 'POST', {'timeout': 300}))
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-groq-key')
        meta = {'CONTENT_TYPE': request.get_header('Content-type'), 'CONTENT_LENGTH': str(len(request.data))}
        fields, files = MultiPartParser(meta, BytesIO(request.data), [MemoryFileUploadHandler()]).parse()
        self.assertEqual(dict(fields.lists()), {'model': ['whisper-large-v3-turbo'], 'response_format': ['verbose_json'], 'timestamp_granularities[]': ['segment'], 'language': ['fr']})
        self.assertEqual((files['file'].name, files['file'].read()), ('question.ogg', OGG))
        with patch(URLOPEN, return_value=BytesIO(b'{"segments": null}')):
            self.assertEqual(GroqTranscriber().transcribe(path), Transcript([], '', None, 'groq', 'whisper-large-v3-turbo'))

    def test_groq_failures(self):
        path = self.audio()
        def http(code): return urllib.error.HTTPError(transcription.GROQ_URL, code, 'Error', {}, BytesIO(b'{}'))
        cases = [(http(429), 'Le service de transcription est momentanément indisponible.', True), (http(503), 'Le service de transcription est momentanément indisponible.', True),
            (http(401), 'Clé du service de transcription invalide.', False), (http(400), 'Le service de transcription a refusé ce fichier audio.', False),
            (TimeoutError('timed out'), 'Le service de transcription ne répond pas.', True), (urllib.error.URLError('refused'), 'Le service de transcription ne répond pas.', True)]
        for failure, message, retryable in cases:
            with self.subTest(failure=repr(failure)), patch(URLOPEN, side_effect=failure):
                self.refused(lambda: GroqTranscriber().transcribe(path), message, retryable)
        for reply in (b'<html>502</html>', b'[]', b'{"segments": [{"start": 0}]}', b'{"segments": [], "duration": "long"}'):
            with self.subTest(reply=reply), patch(URLOPEN, return_value=BytesIO(reply)):
                self.refused(lambda: GroqTranscriber().transcribe(path), 'Réponse inattendue du service de transcription.', True)
        with patch(URLOPEN) as urlopen:
            with self.settings(GROQ_API_KEY=''): self.refused(lambda: GroqTranscriber().transcribe(path), 'La transcription automatique n’est pas configurée sur ce serveur.')
            self.refused(lambda: GroqTranscriber().transcribe(self.audio(name='long.ogg', size=transcription.GROQ_MAX_BYTES + 1)),
                'Ce fichier dépasse la limite de 25 Mo du service de transcription.')
        self.assertFalse(urlopen.called)

    def faster_whisper(self, segments=(), language='fr', duration=6.5):
        """Stand-in for the optional package: records model loads, calls and decoded segments."""
        module = ModuleType('faster_whisper')
        module.__spec__ = importlib.machinery.ModuleSpec('faster_whisper', None)
        module.loads, module.calls, module.decoded = [], [], []
        class WhisperModel:
            def __init__(self, *args, **kwargs): module.loads.append((args, kwargs))
            def transcribe(self, path, **options):
                module.calls.append((path, options))
                def decode():
                    for start, end, text in segments:
                        module.decoded.append(text); yield SimpleNamespace(start=start, end=end, text=text)
                return decode(), SimpleNamespace(language=language, duration=duration)
        module.WhisperModel = WhisperModel
        return module

    def test_local_whisper(self):
        module = self.faster_whisper([(0, 2.5, ' Bonjour. '), (2.5, 6.25, 'La norme.')])
        path = self.audio()
        with patch.dict(sys.modules, {'faster_whisper': module}), self.settings(WHISPER_MODEL='base', WHISPER_CPU_THREADS=3):
            first = LocalTranscriber().transcribe(path)
            LocalTranscriber().transcribe(path, language='fr')
        self.assertEqual(first, Transcript([TranscriptSegment(0.0, 2.5, 'Bonjour.'), TranscriptSegment(2.5, 6.25, 'La norme.')], 'fr', 6.5, 'local', 'base'))
        self.assertEqual(module.loads, [(('base',), {'device': 'cpu', 'compute_type': 'int8', 'cpu_threads': 3})])
        self.assertEqual([options['language'] for _, options in module.calls], [None, 'fr'])
        long = self.faster_whisper([(0, 1, 'Jamais décodé.')], duration=7200.5)
        transcription._local_models.clear()
        with patch.dict(sys.modules, {'faster_whisper': long}):
            self.refused(lambda: LocalTranscriber().transcribe(path), 'Cet enregistrement dépasse la durée maximale de 120 minutes.')
        self.assertEqual(long.decoded, [])
        transcription._local_models.clear()
        with patch.dict(sys.modules, {'faster_whisper': None}):
            self.refused(lambda: LocalTranscriber().transcribe(path), 'faster-whisper n’est pas installé sur ce serveur : installez backend/requirements-whisper.txt.')

    def test_provider_status(self):
        cases = [('disabled', {}, ('disabled', False, '')), ('fake', {}, ('fake', True, 'fake-whisper')), ('groq', {'GROQ_API_KEY': ''}, ('groq', False, 'whisper-large-v3-turbo')),
            ('groq', {}, ('groq', True, 'whisper-large-v3-turbo')), ('openai', {}, ('disabled', False, ''))]
        for provider, extra, (name, configured, model) in cases:
            with self.subTest(provider=provider), self.settings(WHISPER_PROVIDER=provider, **extra):
                self.assertEqual(provider_status(), {'provider': name, 'configured': configured, 'model': model})
        for module, configured in ((None, False), (self.faster_whisper(), True)):
            with self.settings(WHISPER_PROVIDER='local'), patch.dict(sys.modules, {'faster_whisper': module}):
                self.assertEqual(provider_status(), {'provider': 'local', 'configured': configured, 'model': 'small'})
