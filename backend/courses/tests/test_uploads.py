import hashlib
import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from django.db import DatabaseError
from pypdf import PdfReader, PdfWriter
from rest_framework.exceptions import ValidationError
from courses import uploads
from courses.models import Course, ProcessingJob, Resource, ResourceSegment
from courses.processing import SCANNED_PDF
from .base import AUDIO, LESSON, MP3, CourseTestCase, blank_pdf, pdf_bytes

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 100


def owner_only_pdf(pages):
    """Encrypted PDF that opens without a password, as many generated documents are."""
    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf_bytes(pages))))
    writer.encrypt('', 'proprietaire')
    out = BytesIO(); writer.write(out); return out.getvalue()


class UploadTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.course = self.make_course(); self.chapter = self.make_chapter(self.course)

    def send(self, content, name='support.pdf', title='Support', **extra):
        return self.upload(self.course, self.chapter, content, name, title, **extra)

    def refused(self, response, message):
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['error']['fields'], {'file': [message]})

    def test_each_audio_type_is_recognised_by_its_content(self):
        for label, (content, mime, extension) in AUDIO.items():
            with self.subTest(label=label):
                r = self.send(content, 'photo.jpg', f'Audio {label}'); self.assertEqual(r.status_code, 201, r.data)
                self.assertEqual((r.data['kind'], r.data['mime_type'], r.data['processing_status'], r.data['size']), ('AUDIO', mime, 'PENDING', len(content)))
                self.assertEqual((r.data['original_name'], r.data['segments_count'], r.data['duration_seconds'], r.data['page_count']), ('photo.jpg', 0, None, None))
                resource = Resource.objects.get(pk=r.data['id'])
                self.assertRegex(resource.file.name, rf'^courses/[0-9a-f]{{32}}\.{extension}$')
                self.assertEqual((resource.sha256, resource.uploaded_by_id), (hashlib.sha256(content).hexdigest(), self.teacher.pk))
                with resource.file.open('rb') as handle: self.assertEqual(handle.read(), content)
                job = ProcessingJob.objects.get(resource=resource)
                self.assertEqual((job.kind, job.status, job.active, job.attempts), ('TRANSCRIBE_AUDIO', 'PENDING', True, 0))
        self.assertEqual([r.position for r in Resource.objects.filter(chapter=self.chapter)], list(range(1, 8)))
        self.assertEqual(len(self.stored_files()), 7); self.assertEqual(self.events, [])

    def test_pdf_is_extracted_inline_page_by_page(self):
        content = pdf_bytes(['Les fonctions   dérivées\n\n\n\nen mathématiques.', 'Les intégrales et les primitives.', ' '])
        r = self.send(content, 'cours.mp3', description='Chapitre complet.'); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['kind'], r.data['mime_type'], r.data['processing_status'], r.data['page_count']), ('PDF', 'application/pdf', 'READY', 3))
        self.assertEqual((r.data['segments_count'], r.data['text_version'], r.data['description'], r.data['processing_error']), (2, 1, 'Chapitre complet.', ''))
        job = r.data['job']
        self.assertEqual((job['status'], job['attempts'], job['provider'], job['model_name'], job['segments_count'], job['audio_seconds']), ('DONE', 1, 'pypdf', 'pypdf 6.21.2', 2, None))
        self.assertIsInstance(job['processing_ms'], int); self.assertIsNotNone(job['finished_at'])
        segments = list(ResourceSegment.objects.filter(resource_id=Resource.objects.get(pk=r.data['id']).pk))
        self.assertEqual([(s.order, s.page) for s in segments], [(1, 1), (2, 2)])
        self.assertEqual(segments[0].text, 'Les fonctions dérivées\nen mathématiques.')
        self.assertEqual(segments[0].search_text, 'les fonctions derivees en mathematiques.')
        self.assertTrue(all(s.course_id == self.course.pk and s.chapter_id == self.chapter.pk and s.start_seconds is None for s in segments))
        self.assertRegex(Resource.objects.get(pk=r.data['id']).file.name, r'^courses/[0-9a-f]{32}\.pdf$')
        self.assertEqual(self.version(self.course), 2)
        self.assertEqual(self.events, [{'signal': self.events[0]['signal'], 'sender': Course, 'course_id': str(self.course.pk), 'resource_id': r.data['id'], 'reason': 'resource_processed'}])
        # The signature may follow up to 1 KB of leading bytes; pypdf warns while it recovers the offsets.
        with self.assertLogs('pypdf', 'WARNING'):
            r = self.send(b'\x00' * 500 + pdf_bytes(LESSON), 'sans-extension', 'Préfixé')
        self.assertEqual((r.status_code, r.data['kind'], r.data['processing_status']), (201, 'PDF', 'READY'))

    def test_scanned_or_nearly_empty_pdf_is_kept_without_text(self):
        for content, pages in ((blank_pdf(2), 2), (pdf_bytes(['12', 'p. 3']), 2)):
            r = self.send(content, 'scan.pdf'); self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual((r.data['processing_status'], r.data['processing_label'], r.data['processing_error']), ('NO_TEXT', 'Sans texte exploitable', SCANNED_PDF))
            self.assertEqual((r.data['page_count'], r.data['segments_count'], r.data['job']['status'], r.data['job']['segments_count'], r.data['text_version']), (pages, 0, 'DONE', 0, 1))
        self.assertEqual(self.reasons(), ['resource_processed'] * 2)

    def test_encrypted_corrupt_and_oversized_pdfs_are_refused(self):
        self.refused(self.send(blank_pdf(1, 'secret')), 'Ce PDF est protégé par un mot de passe : retirez la protection avant de l’importer.')
        with self.assertLogs('pypdf', 'WARNING'):
            self.refused(self.send(b'%PDF-1.4 garbage'), 'Ce fichier PDF est illisible ou endommagé.')
        self.refused(self.send(pdf_bytes([])), 'Ce fichier PDF est illisible ou endommagé.')
        with self.settings(COURSES_MAX_PDF_PAGES=1):
            self.refused(self.send(pdf_bytes(['Page un avec du texte.', 'Page deux avec du texte.'])), 'Ce PDF compte 2 pages : la limite est de 1 pages.')
        self.assertEqual((Resource.objects.count(), self.stored_files()), (0, []))
        r = self.send(owner_only_pdf(LESSON), 'protege.pdf'); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['processing_status'], r.data['segments_count']), ('READY', 2))
        self.assertIn('dérivée', ResourceSegment.objects.filter(resource_id=Resource.objects.get(pk=r.data['id']).pk).first().text)

    def test_unknown_types_and_missing_files_are_refused(self):
        unsupported = 'Format non pris en charge : importez un PDF ou un fichier audio (MP3, M4A, WAV, OGG, WEBM, FLAC).'
        for content, name in ((b'hello world', 'notes.pdf'), (PNG, 'cours.mp3'), (JPEG, 'cours.m4a'), (b'RIFF\x24\x00\x00\x00AVI ' + b'\x00' * 50, 'cours.wav'), (b'\xff', 'x.mp3')):
            self.refused(self.send(content, name), unsupported)
        self.refused(self.send(b''), 'Le fichier est vide.')
        r = self.client.post(f'/api/courses/{self.course.pk}/resources/', {'chapter_id': str(self.chapter.pk), 'title': 'Sans fichier'}, format='multipart')
        self.assertEqual(r.data['error']['fields'], {'file': ['Choisissez un fichier.']})
        r = self.client.post(f'/api/courses/{self.course.pk}/resources/', {'chapter_id': str(self.chapter.pk), 'title': 'Texte', 'file': 'abc'}, format='multipart')
        self.assertIn('file', r.data['error']['fields'])
        r = self.client.post(f'/api/courses/{self.course.pk}/resources/', {}, format='multipart')
        self.assertEqual(set(r.data['error']['fields']), {'chapter_id', 'title', 'file'})
        self.assertEqual((Resource.objects.count(), self.stored_files()), (0, []))

    def test_field_errors_leave_no_stored_file(self):
        foreign = self.make_chapter(self.make_course(title='Autre cours'))
        for change, field in (({'title': ''}, 'title'), ({'title': 'x' * 121}, 'title'), ({'description': 'x' * 1001}, 'description'),
                ({'chapter_id': 'bad'}, 'chapter_id'), ({'kind': 'PDF'}, 'kind')):
            data = {'chapter_id': str(self.chapter.pk), 'title': 'Support', 'file': BytesIO(MP3), **change}
            r = self.client.post(f'/api/courses/{self.course.pk}/resources/', data, format='multipart')
            self.assertEqual(r.status_code, 400, r.data); self.assertIn(field, r.data['error']['fields'])
        for chapter_id in (str(foreign.pk), '0' * 24):
            r = self.upload(self.course, chapter_id, MP3, 'cours.mp3')
            self.assertEqual(r.data['error']['fields'], {'chapter_id': ['Sélectionnez un chapitre de ce cours.']})
        self.assertEqual((Resource.objects.count(), ProcessingJob.objects.count(), self.stored_files()), (0, 0, []))

    def test_size_limits_per_kind_and_body_length(self):
        with self.settings(COURSES_MAX_AUDIO_MB=0.001, COURSES_MAX_PDF_MB=0.002):
            self.assertEqual(self.send(MP3, 'petit.mp3').status_code, 201)
            self.refused(self.send(MP3 * 2, 'long.mp3'), 'Ce fichier dépasse la taille maximale de 0.001 Mo pour ce type de ressource.')
            self.assertEqual(self.send(pdf_bytes(LESSON)).status_code, 201)
            self.refused(self.send(pdf_bytes(LESSON * 3)), 'Ce fichier dépasse la taille maximale de 0.002 Mo pour ce type de ressource.')
        with self.settings(COURSES_MAX_PDF_MB=0.0001, COURSES_MAX_AUDIO_MB=0.0001), patch('courses.views.validated') as parse:
            r = self.send(MP3 * 1100, 'enorme.mp3'); self.refused(r, 'Le fichier dépasse la taille maximale autorisée (0.0001 Mo).')
            parse.assert_not_called()
        self.assertEqual(len(self.stored_files()), 2)
        for length in ('', 'abc', '12'): uploads.reject_oversized_body(SimpleNamespace(META={'CONTENT_LENGTH': length}))
        with self.assertRaises(ValidationError): uploads.reject_oversized_body(SimpleNamespace(META={'CONTENT_LENGTH': str(50 * uploads.MB)}))

    def test_duplicate_file_in_the_same_course_only(self):
        self.assertEqual(self.send(MP3, 'cours.mp3', 'Cours enregistré').status_code, 201)
        self.refused(self.send(MP3, 'copie.mp3', 'Copie'), 'Ce fichier existe déjà dans ce cours : « Cours enregistré ».')
        self.assertEqual(len(self.stored_files()), 1)
        other = self.make_course(title='Autre cours')
        self.assertEqual(self.upload(other, self.make_chapter(other), MP3, 'cours.mp3').status_code, 201)
        self.assertEqual(len(self.stored_files()), 2)

    def test_original_name_is_reduced_to_a_safe_display_name(self):
        r = self.send(MP3, 'C:\\Users\\amel\\cours\x00   du  lundi.mp3'); self.assertEqual(r.data['original_name'], 'cours du lundi.mp3')
        r = self.send(MP3 + b'1', 'é' * 200 + '.mp3'); self.assertEqual((len(r.data['original_name']), r.data['original_name'][-5:]), (180, 'éé.mp3'[-5:]))
        cases = {'../../etc/passwd': 'passwd', 'a\\b\\c.pdf': 'c.pdf', '\u200bcours\u202e.pdf': 'cours.pdf', '  ': 'ressource.pdf', '': 'ressource.pdf',
            None: 'ressource.pdf', 'x' * 190 + '.extension-trop-longue': 'x' * 180, 'n' * 200: 'n' * 180}
        for name, expected in cases.items():
            self.assertEqual(uploads.clean_name(name, 'pdf'), expected, name)
        self.assertEqual(uploads.clean_name('a' * 300 + '.pdf', 'pdf'), 'a' * 176 + '.pdf')

    def test_stored_file_is_removed_when_the_database_write_fails(self):
        with patch.object(Resource, 'save', side_effect=DatabaseError('write conflict')):
            r = self.send(MP3, 'cours.mp3')
        self.assertEqual((r.status_code, r.data['error']['code']), (409, 'conflict'))
        with patch.object(Resource, 'save', side_effect=RuntimeError('panne')), self.assertRaises(RuntimeError):
            self.send(MP3, 'cours.mp3')
        self.assertEqual((Resource.objects.count(), ProcessingJob.objects.count(), self.stored_files()), (0, 0, []))
        original, calls = Resource.save, []
        def flaky(resource, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1: raise DatabaseError('write conflict')
            return original(resource, *args, **kwargs)
        with patch.object(Resource, 'save', flaky):
            r = self.send(MP3, 'cours.mp3')
        self.assertEqual((r.status_code, len(calls), len(self.stored_files())), (201, 2, 1))
        self.assertEqual(Resource.objects.get().file.name, 'courses/' + self.stored_files()[0])

    def test_audio_is_transcribed_inline_when_configured(self):
        with self.settings(COURSES_PROCESS_INLINE=True):
            r = self.send(MP3, 'cours.mp3', 'Cours enregistré')
        self.assertEqual((r.status_code, r.data['processing_status'], r.data['segments_count'], r.data['duration_seconds'], r.data['language']), (201, 'READY', 3, 15.0, 'fr'))
        self.assertEqual((r.data['job']['provider'], r.data['job']['model_name'], r.data['job']['audio_seconds']), ('fake', 'fake-whisper', 15.0))
        with self.settings(COURSES_PROCESS_INLINE=True, WHISPER_PROVIDER='disabled'):
            r = self.send(MP3 + b'1', 'cours2.mp3')
        self.assertEqual((r.data['processing_status'], r.data['processing_error']), ('FAILED', 'La transcription automatique n’est pas configurée sur ce serveur.'))

    def test_upload_throttle_counts_every_attempt(self):
        with patch('accounts.services.time.time', return_value=1_800_000_000.0):
            for _ in range(30):
                self.assertEqual(self.client.post(f'/api/courses/{self.course.pk}/resources/', {}, format='multipart').status_code, 400)
            r = self.send(MP3, 'cours.mp3'); self.assertEqual((r.status_code, r.data['error']['code']), (429, 'throttled'))
            self.assertEqual(self.upload(self.course, self.chapter, MP3, 'cours.mp3', client=self.as_user(self.admin)).status_code, 201)
        self.assertEqual(Resource.objects.count(), 1); self.assertTrue(os.path.isdir(os.path.join(self.media, 'courses')))
