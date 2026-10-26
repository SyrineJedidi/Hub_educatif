import hashlib
import importlib.machinery
import json
import os
import shutil
import sys
import tempfile
import urllib.error
from fractions import Fraction
from io import BytesIO
from socket import gaierror
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.db import connection
from django.http.multipartparser import MultiPartParser
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from ai import transcription
from ai.transcription import (DisabledTranscriber, FakeTranscriber, GroqTranscriber, LocalTranscriber, Transcript, TranscriptSegment,
    TranscriptionError, get_transcriber, language_code, provider_status)
from courses.models import ProcessingJob, Resource, ResourceSegment
from courses.uploads import size_limit
from .base import MP3, CourseTestCase

URLOPEN = 'urllib.request.urlopen'
NOT_CONFIGURED = 'La transcription automatique n’est pas configurée sur ce serveur.'
TEST_DATABASE = 'Les fournisseurs de transcription réels sont désactivés sur une base de test.'
UNAVAILABLE = 'Le service de transcription est momentanément indisponible.'
BAD_KEY = 'Clé du service de transcription invalide.'
REFUSED = 'Le service de transcription a refusé ce fichier audio.'
SILENT = 'Le service de transcription ne répond pas.'
UNEXPECTED = 'Réponse inattendue du service de transcription.'
# A database name the test runner never uses, so get_transcriber() may hand out the real providers.
SERVER_DATABASE = SimpleNamespace(settings_dict={'NAME': 'nexora_hub'})


def reply(body):
    """What urlopen() returns for a successful response: a context manager with read()."""
    return BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())


def http_error(code):
    return urllib.error.HTTPError(transcription.GROQ_URL, code, 'Error', {}, BytesIO(b'{"error": {"message": "refused"}}'))


class SlowReply(BytesIO):
    def read(self, *args): raise TimeoutError('The read operation timed out')


def faster_whisper(segments=(), language='fr', duration=6.5):
    """Stand-in for the optional package: records model loads, calls, and which segments were decoded."""
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


@override_settings(WHISPER_PROVIDER='fake', WHISPER_MODEL='small', WHISPER_CPU_THREADS=2, GROQ_API_KEY='gsk_test',
    GROQ_WHISPER_MODEL='whisper-large-v3-turbo', COURSES_MAX_AUDIO_SECONDS=7200, COURSES_MAX_AUDIO_MB=25)
class TranscriberTests(SimpleTestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.folder, True)
        # Models are cached per process: one test's stand-in must not serve the next test.
        models = patch.dict(transcription._local_models, clear=True); models.start(); self.addCleanup(models.stop)

    def audio(self, content=MP3, name='9f86d081884c7d659a2feaa0c55ad015.mp3', size=None):
        path = os.path.join(self.folder, name)
        with open(path, 'wb') as handle:
            handle.write(content)
            if size is not None: handle.truncate(size)
        return path

    def refused(self, call, message, retryable=False):
        with self.assertRaises(TranscriptionError) as caught: call()
        self.assertEqual((caught.exception.message, str(caught.exception), caught.exception.retryable), (message, message, retryable))

    def groq(self, body, path=None, language=None):
        with patch(URLOPEN, return_value=body if isinstance(body, BytesIO) else reply(body)) as urlopen:
            transcript = GroqTranscriber().transcribe(path or self.audio(), language=language)
        self.assertEqual(urlopen.call_count, 1)
        return transcript, urlopen.call_args

    def multipart(self, request):
        """Form fields and files of a request body, decoded by Django's own multipart parser."""
        content_type = request.get_header('Content-type')
        self.assertRegex(content_type, r'^multipart/form-data; boundary=[0-9a-f]{32}$')
        meta = {'CONTENT_TYPE': content_type, 'CONTENT_LENGTH': str(len(request.data))}
        fields, files = MultiPartParser(meta, BytesIO(request.data), [MemoryFileUploadHandler()]).parse()
        return dict(fields.lists()), files

    def test_provider_is_chosen_from_settings(self):
        cases = {'disabled': DisabledTranscriber, 'fake': FakeTranscriber, 'local': LocalTranscriber, 'groq': GroqTranscriber, '': DisabledTranscriber, 'openai': DisabledTranscriber}
        # Choosing the local provider must not import faster-whisper: that happens on the first transcription.
        with patch('ai.transcription.connection', SERVER_DATABASE), patch.dict(sys.modules, {'faster_whisper': None}):
            for value, provider in cases.items():
                with self.subTest(provider=value), self.settings(WHISPER_PROVIDER=value):
                    self.assertIs(type(get_transcriber()), provider)
            with self.settings(WHISPER_PROVIDER='local', WHISPER_MODEL='base'): self.assertEqual(get_transcriber().model, 'base')
            with self.settings(WHISPER_PROVIDER='groq', GROQ_WHISPER_MODEL='whisper-large-v3'): self.assertEqual(get_transcriber().model, 'whisper-large-v3')
        self.refused(lambda: DisabledTranscriber().transcribe(self.audio()), NOT_CONFIGURED)
        self.refused(lambda: DisabledTranscriber().transcribe(self.audio(), language='fr'), NOT_CONFIGURED)

    def test_real_providers_are_refused_on_a_test_database(self):
        with patch('ai.transcription.connection', SimpleNamespace(settings_dict={'NAME': 'test_nexora_hub'})):
            for value in ('local', 'groq'):
                with self.subTest(provider=value), self.settings(WHISPER_PROVIDER=value): self.refused(get_transcriber, TEST_DATABASE)
            for value, provider in (('fake', FakeTranscriber), ('disabled', DisabledTranscriber), ('openai', DisabledTranscriber)):
                with self.subTest(provider=value), self.settings(WHISPER_PROVIDER=value): self.assertIs(type(get_transcriber()), provider)

    def test_fake_transcript_depends_only_on_the_file_content(self):
        prefix = hashlib.sha256(MP3).hexdigest()[:8]
        expected = Transcript([TranscriptSegment(5.0 * i, 5.0 * (i + 1), f'Transcription de démonstration {prefix}, partie {i + 1}.') for i in range(3)],
            'fr', 15.0, 'fake', 'fake-whisper')
        first, copy = self.audio(), self.audio(name='copie.ogg')
        self.assertEqual([FakeTranscriber().transcribe(first), FakeTranscriber().transcribe(first), FakeTranscriber().transcribe(copy, language='en')], [expected] * 3)
        other = FakeTranscriber().transcribe(self.audio(MP3 + b'1', 'autre.mp3'))
        self.assertEqual([s.text for s in other.segments], [f'Transcription de démonstration {hashlib.sha256(MP3 + b"1").hexdigest()[:8]}, partie {i}.' for i in (1, 2, 3)])

    def test_language_names_become_iso_codes(self):
        names = {'French': 'fr', ' english ': 'en', 'ARABIC': 'ar', 'spanish': 'es', 'german': 'de', 'italian': 'it', 'portuguese': 'pt', 'dutch': 'nl', 'turkish': 'tr'}
        self.assertEqual({name: language_code(name) for name in names}, names)
        self.assertEqual([language_code(value) for value in ('fr', 'EN', '', None)], ['fr', 'en', '', ''])
        # Names without a code are kept, but never wider than Resource.language.
        self.assertLessEqual(len(language_code('Vietnamese')), 8)

    def test_groq_sends_one_multipart_request_and_reads_verbose_json(self):
        path = self.audio()
        transcript, call = self.groq({'task': 'transcribe', 'language': 'French', 'duration': 9.5, 'text': 'Bonjour à tous. Les dérivées.', 'segments': [
            {'id': 0, 'start': 0, 'end': 4.25, 'text': ' Bonjour à tous. '}, {'id': 1, 'start': '4.25', 'end': 9.5, 'text': 'Les dérivées.'}],
            'x_groq': {'id': 'req_1'}}, path, 'fr')
        self.assertEqual(transcript, Transcript([TranscriptSegment(0.0, 4.25, 'Bonjour à tous.'), TranscriptSegment(4.25, 9.5, 'Les dérivées.')],
            'fr', 9.5, 'groq', 'whisper-large-v3-turbo'))
        self.assertEqual({type(value) for s in transcript.segments for value in (s.start, s.end)}, {float})
        request = call.args[0]
        self.assertEqual((request.full_url, request.get_method(), call.kwargs), ('https://api.groq.com/openai/v1/audio/transcriptions', 'POST', {'timeout': 300}))
        self.assertEqual((request.get_header('Authorization'), request.get_header('Accept')), ('Bearer gsk_test', 'application/json'))
        fields, files = self.multipart(request)
        self.assertEqual(fields, {'model': ['whisper-large-v3-turbo'], 'response_format': ['verbose_json'], 'timestamp_granularities[]': ['segment'], 'language': ['fr']})
        self.assertEqual((list(files), files['file'].name, files['file'].read()), (['file'], os.path.basename(path), MP3))

    def test_groq_language_comes_from_the_answer_then_from_the_request(self):
        for requested, answered, expected in ((None, 'english', 'en'), ('fr', 'Arabic', 'ar'), ('ar', None, 'ar'), (None, None, '')):
            with self.subTest(requested=requested, answered=answered):
                transcript, call = self.groq({'segments': [], 'duration': 3, **({'language': answered} if answered else {})}, language=requested)
                fields, _ = self.multipart(call.args[0])
                self.assertEqual((transcript.language, transcript.duration, fields.get('language')), (expected, 3.0, [requested] if requested else None))

    def test_groq_answer_without_speech_or_duration(self):
        self.assertEqual(self.groq({'text': '', 'segments': None})[0], Transcript([], '', None, 'groq', 'whisper-large-v3-turbo'))

    def test_groq_http_errors_say_whether_to_retry(self):
        path = self.audio()
        cases = [(429, UNAVAILABLE, True), (500, UNAVAILABLE, True), (502, UNAVAILABLE, True), (503, UNAVAILABLE, True), (504, UNAVAILABLE, True),
            (401, BAD_KEY, False), (403, BAD_KEY, False), (400, REFUSED, False), (404, REFUSED, False), (413, REFUSED, False), (415, REFUSED, False)]
        for code, message, retryable in cases:
            with self.subTest(code=code), patch(URLOPEN, side_effect=http_error(code)):
                self.refused(lambda: GroqTranscriber().transcribe(path), message, retryable)

    def test_groq_network_failures_are_retried(self):
        path = self.audio()
        failures = [TimeoutError('timed out'), urllib.error.URLError(ConnectionRefusedError(111, 'Connection refused')),
            urllib.error.URLError(gaierror(-3, 'Temporary failure in name resolution')), ConnectionResetError(104, 'Connection reset by peer')]
        for failure in failures:
            with self.subTest(failure=repr(failure)), patch(URLOPEN, side_effect=failure):
                self.refused(lambda: GroqTranscriber().transcribe(path), SILENT, True)
        with patch(URLOPEN, return_value=SlowReply()):
            self.refused(lambda: GroqTranscriber().transcribe(path), SILENT, True)

    def test_groq_unexpected_answers_are_retried(self):
        path = self.audio()
        bodies = [b'<html>502 Bad Gateway</html>', b'\xff\xfe\x00', b'', b'null', b'[]', {'segments': 'texte'}, {'segments': [None]},
            {'segments': [{'start': 0, 'text': 'Sans fin.'}]}, {'segments': [{'start': 'zéro', 'end': 1, 'text': 'x'}]},
            {'segments': [], 'duration': 'longue'}, {'segments': [], 'duration': [12]}]
        for body in bodies:
            with self.subTest(body=body), patch(URLOPEN, return_value=reply(body)):
                self.refused(lambda: GroqTranscriber().transcribe(path), UNEXPECTED, True)

    def test_groq_checks_the_key_and_the_size_before_sending(self):
        with patch(URLOPEN) as urlopen:
            with self.settings(GROQ_API_KEY=''): self.refused(lambda: GroqTranscriber().transcribe(self.audio()), NOT_CONFIGURED)
            self.refused(lambda: GroqTranscriber().transcribe(self.audio(name='long.mp3', size=transcription.GROQ_MAX_BYTES + 1)),
                'Ce fichier dépasse la limite de 25 Mo du service de transcription.')
        self.assertFalse(urlopen.called)
        # The largest audio file an upload accepts is still sent.
        largest = size_limit('AUDIO')[0]
        self.assertEqual(largest, transcription.GROQ_MAX_BYTES)
        _, call = self.groq({'segments': []}, self.audio(name='limite.mp3', size=largest))
        self.assertGreater(len(call.args[0].data), largest)

    def test_local_whisper_runs_on_cpu_and_converts_segments(self):
        module = faster_whisper([(0, Fraction(5, 2), ' Bonjour à tous. '), (Fraction(5, 2), 6.25, 'Les dérivées.')], language='fr', duration=Fraction(13, 2))
        path = self.audio()
        with patch.dict(sys.modules, {'faster_whisper': module}), self.settings(WHISPER_MODEL='base', WHISPER_CPU_THREADS=3):
            transcript = LocalTranscriber().transcribe(path)
        self.assertEqual(transcript, Transcript([TranscriptSegment(0.0, 2.5, 'Bonjour à tous.'), TranscriptSegment(2.5, 6.25, 'Les dérivées.')], 'fr', 6.5, 'local', 'base'))
        self.assertEqual({type(value) for s in transcript.segments for value in (s.start, s.end)} | {type(transcript.duration)}, {float})
        self.assertEqual(module.loads, [(('base',), {'device': 'cpu', 'compute_type': 'int8', 'cpu_threads': 3})])
        self.assertEqual(module.calls, [(path, {'language': None, 'vad_filter': True, 'beam_size': 5})])

    def test_local_model_is_loaded_once_per_model_and_thread_count(self):
        module = faster_whisper([(0, 1, 'Un.')]); path = self.audio()
        with patch.dict(sys.modules, {'faster_whisper': module}):
            for model, threads, language in (('small', 2, None), ('small', 2, 'fr'), ('small', 2, ''), ('base', 2, None), ('base', 4, None), ('small', 2, 'ar')):
                with self.settings(WHISPER_MODEL=model, WHISPER_CPU_THREADS=threads): LocalTranscriber().transcribe(path, language=language)
        self.assertEqual([(args[0], kwargs['cpu_threads']) for args, kwargs in module.loads], [('small', 2), ('base', 2), ('base', 4)])
        self.assertEqual([options['language'] for _, options in module.calls], [None, 'fr', None, None, None, 'ar'])

    def test_local_whisper_refuses_long_recordings_before_decoding_them(self):
        path = self.audio(); long = faster_whisper([(0, 1, 'Jamais décodé.')], duration=7200.5)
        with patch.dict(sys.modules, {'faster_whisper': long}):
            self.refused(lambda: LocalTranscriber().transcribe(path), 'Cet enregistrement dépasse la durée maximale de 120 minutes.')
        self.assertEqual((len(long.calls), long.decoded), (1, []))
        transcription._local_models.clear(); exact = faster_whisper([(0, 1, 'Décodé.')], duration=7200)
        with patch.dict(sys.modules, {'faster_whisper': exact}):
            self.assertEqual(LocalTranscriber().transcribe(path).segments, [TranscriptSegment(0.0, 1.0, 'Décodé.')])
        self.assertEqual(exact.decoded, ['Décodé.'])

    def test_local_whisper_explains_how_to_install_it(self):
        with patch.dict(sys.modules, {'faster_whisper': None}):
            self.refused(lambda: LocalTranscriber().transcribe(self.audio()), 'faster-whisper n’est pas installé sur ce serveur : installez backend/requirements-whisper.txt.')
        self.assertEqual(transcription._local_models, {})

    def test_provider_status_reports_what_can_run(self):
        cases = [('disabled', {}, ('disabled', False, '')), ('openai', {}, ('disabled', False, '')), ('fake', {}, ('fake', True, 'fake-whisper')),
            ('groq', {'GROQ_API_KEY': ''}, ('groq', False, 'whisper-large-v3-turbo')), ('groq', {'GROQ_WHISPER_MODEL': 'whisper-large-v3'}, ('groq', True, 'whisper-large-v3'))]
        for provider, extra, (name, configured, model) in cases:
            with self.subTest(provider=provider, **extra), self.settings(WHISPER_PROVIDER=provider, **extra):
                self.assertEqual(provider_status(), {'provider': name, 'configured': configured, 'model': model})
        with self.settings(WHISPER_PROVIDER='local', WHISPER_MODEL='base'):
            for module, configured in ((None, False), (faster_whisper(), True)):
                with patch.dict(sys.modules, {'faster_whisper': module}):
                    self.assertEqual(provider_status(), {'provider': 'local', 'configured': configured, 'model': 'base'})
        self.assertEqual(transcription._local_models, {})


class ProviderPipelineTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.course = self.make_course(); self.chapter = self.make_chapter(self.course)

    def audio(self, content=MP3, title='Cours enregistré'):
        return Resource.objects.get(pk=self.add_resource(self.course, self.chapter, content, 'cours.mp3', title)['id'])

    def test_real_providers_never_run_against_the_test_database(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        module = faster_whisper([(0, 1, 'Jamais.')])
        with patch(URLOPEN, side_effect=AssertionError('réseau')) as urlopen, patch.dict(sys.modules, {'faster_whisper': module}), \
                patch.dict(transcription._local_models, clear=True):
            for number, provider in enumerate(('groq', 'local')):
                resource = self.audio(MP3 + bytes([number]), f'Cours {provider}')
                with self.subTest(provider=provider), self.settings(WHISPER_PROVIDER=provider, GROQ_API_KEY='gsk_test'):
                    with self.assertRaises(TranscriptionError) as caught: get_transcriber()
                    self.assertEqual((caught.exception.message, caught.exception.retryable), (TEST_DATABASE, False))
                    self.work()
                    resource.refresh_from_db(); job = ProcessingJob.objects.get(resource=resource)
                    self.assertEqual((resource.processing_status, resource.processing_error, job.status, job.attempts), ('FAILED', TEST_DATABASE, 'FAILED', 1))
        self.assertEqual((urlopen.called, module.loads, self.events), (False, [], []))

    def test_worker_saves_a_groq_transcript_after_a_retry(self):
        resource = self.audio(); self.events.clear()
        body = {'language': 'French', 'duration': 8, 'segments': [{'start': 0, 'end': 3.5, 'text': ' Bonjour à tous. '}, {'start': 3.5, 'end': 8, 'text': 'Les dérivées.'}]}
        with patch('ai.transcription.connection', SERVER_DATABASE), self.settings(WHISPER_PROVIDER='groq', GROQ_API_KEY='gsk_test', GROQ_WHISPER_MODEL='whisper-large-v3-turbo', WHISPER_LANGUAGE='fr'):
            with patch(URLOPEN, side_effect=http_error(503)): self.work()
            job = ProcessingJob.objects.get(resource=resource); resource.refresh_from_db()
            self.assertEqual((job.status, job.attempts, job.error, resource.processing_status), ('PENDING', 1, UNAVAILABLE, 'PENDING'))
            ProcessingJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
            with patch(URLOPEN, return_value=reply(body)) as urlopen: self.work()
        self.assertIn(b'name="language"\r\n\r\nfr\r\n', urlopen.call_args.args[0].data)
        job.refresh_from_db(); resource.refresh_from_db()
        self.assertEqual((resource.processing_status, resource.processing_error, resource.language, resource.duration_seconds, resource.text_version), ('READY', '', 'fr', 8.0, 1))
        self.assertEqual([(s.order, s.text, s.start_seconds, s.end_seconds) for s in ResourceSegment.objects.filter(resource=resource)],
            [(1, 'Bonjour à tous.', 0.0, 3.5), (2, 'Les dérivées.', 3.5, 8.0)])
        self.assertEqual((job.status, job.attempts, job.error, job.provider, job.model_name, job.audio_seconds, job.segments_count),
            ('DONE', 2, '', 'groq', 'whisper-large-v3-turbo', 8.0, 2))
        self.assertEqual(self.reasons(), ['resource_processed'])
