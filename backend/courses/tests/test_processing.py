import hashlib
import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import pypdf
from django.core.management import call_command
from django.db import DatabaseError, connection, connections
from django.utils import timezone
from accounts.models import AdminGuard
from ai.transcription import FakeTranscriber, Transcript, TranscriptSegment, TranscriptionError
from courses import processing
from courses.models import CourseGroup, ProcessingJob, Resource, ResourceSegment
from .base import MP3, CourseTestCase, pdf_bytes

TRANSCRIBE = 'ai.transcription.FakeTranscriber.transcribe'


class ProcessingTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.course = self.make_course(); self.chapter = self.make_chapter(self.course)

    def audio(self, content=MP3, title='Cours enregistré'):
        data = self.add_resource(self.course, self.chapter, content, 'cours.mp3', title)
        return Resource.objects.get(pk=data['id'])

    def job(self, resource):
        return ProcessingJob.objects.filter(resource=resource).order_by('-created_at', '-id').first()

    def release(self, job):
        ProcessingJob.objects.filter(pk=job.pk).update(available_at=timezone.now())

    def test_worker_transcribes_pending_audio_with_metrics(self):
        resource = self.audio(); job = self.job(resource); self.events.clear()
        states = []
        def receiver(**kwargs): states.append((connection.in_atomic_block_mongo, Resource.objects.get(pk=resource.pk).processing_status))
        from courses.signals import course_content_changed
        course_content_changed.connect(receiver, weak=False, dispatch_uid='commit-check'); self.addCleanup(course_content_changed.disconnect, dispatch_uid='commit-check')
        out = self.work()
        job.refresh_from_db(); resource.refresh_from_db()
        self.assertRegex(out, rf'^{job.pk} Transcription audio \(tentative 1\) : Terminé, 3 segment\(s\), \d+ ms\n1 tâche\(s\) traitée\(s\)\.\n$')
        self.assertEqual((resource.processing_status, resource.processing_error, resource.duration_seconds, resource.language, resource.text_version), ('READY', '', 15.0, 'fr', 1))
        prefix = hashlib.sha256(MP3).hexdigest()[:8]
        self.assertEqual([(s.order, s.text, s.start_seconds, s.end_seconds, s.page) for s in ResourceSegment.objects.filter(resource=resource)],
            [(i + 1, f'Transcription de démonstration {prefix}, partie {i + 1}.', 5.0 * i, 5.0 * (i + 1), None) for i in range(3)])
        self.assertEqual((job.status, job.active, job.attempts, job.provider, job.model_name, job.audio_seconds, job.segments_count, job.error), ('DONE', False, 1, 'fake', 'fake-whisper', 15.0, 3, ''))
        self.assertIsInstance(job.processing_ms, int); self.assertIsNotNone(job.started_at); self.assertGreaterEqual(job.finished_at, job.started_at)
        self.assertRegex(job.worker, r'-\d+$')
        self.assertEqual((self.version(self.course), self.reasons(), self.events[0]['resource_id']), (2, ['resource_processed'], str(resource.pk)))
        self.assertEqual(states, [(False, 'READY')])
        self.assertEqual(self.work(), '0 tâche(s) traitée(s).\n')

    def test_worker_takes_oldest_jobs_first_and_honours_the_limit(self):
        resources = [self.audio(MP3 + bytes([i]), f'Audio {i}') for i in range(3)]
        out = self.work('--limit', '2'); self.assertIn('2 tâche(s) traitée(s).', out)
        self.assertEqual([Resource.objects.get(pk=r.pk).processing_status for r in resources], ['READY', 'READY', 'PENDING'])
        self.assertIn('1 tâche(s) traitée(s).', self.work())

    def test_retryable_errors_back_off_then_fail_after_three_attempts(self):
        resource = self.audio(); job = self.job(resource); self.events.clear()
        with patch(TRANSCRIBE, side_effect=TranscriptionError('Service indisponible.', retryable=True)):
            for attempt in (1, 2):
                before = timezone.now(); out = self.work(); after = timezone.now()
                job.refresh_from_db(); resource.refresh_from_db()
                self.assertIn(f'(tentative {attempt}) : En attente — Service indisponible.', out)
                self.assertEqual((job.status, job.active, job.attempts, job.error, job.worker, resource.processing_status), ('PENDING', True, attempt, 'Service indisponible.', '', 'PENDING'))
                delay = timedelta(seconds=60 * attempt)
                self.assertGreaterEqual(job.available_at, (before + delay).replace(microsecond=before.microsecond // 1000 * 1000))
                self.assertLessEqual(job.available_at, after + delay)
                self.assertEqual(self.work(), '0 tâche(s) traitée(s).\n')
                self.release(job)
            out = self.work()
        job.refresh_from_db(); resource.refresh_from_db()
        self.assertIn('(tentative 3) : Échec — Service indisponible.', out)
        self.assertEqual((job.status, job.active, job.attempts, resource.processing_status, resource.processing_error), ('FAILED', False, 3, 'FAILED', 'Service indisponible.'))
        self.assertIsNotNone(job.finished_at); self.assertEqual((self.events, ResourceSegment.objects.count()), ([], 0))

    def test_unexpected_errors_are_logged_and_retried_with_a_generic_message(self):
        resource = self.audio(); job = self.job(resource)
        with patch(TRANSCRIBE, side_effect=ValueError('bug')), self.assertLogs('courses', 'ERROR') as logs:
            self.work()
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts, job.error), ('PENDING', 1, 'Le traitement a échoué. Réessayez plus tard.'))
        self.assertIn(f'Processing job {job.pk} failed', logs.output[0])
        os.remove(resource.file.path); self.release(job)
        with self.assertLogs('courses', 'ERROR'): self.work()
        job.refresh_from_db(); self.assertEqual((job.status, job.attempts), ('PENDING', 2))

    def test_non_retryable_errors_fail_at_once(self):
        resource = self.audio()
        with patch(TRANSCRIBE, side_effect=TranscriptionError('Fichier audio illisible.')):
            self.work()
        job = self.job(resource); resource.refresh_from_db()
        self.assertEqual((job.status, job.active, job.attempts, job.error), ('FAILED', False, 1, 'Fichier audio illisible.'))
        self.assertEqual((resource.processing_status, resource.processing_error), ('FAILED', 'Fichier audio illisible.'))
        other = self.audio(MP3 + b'x', 'Autre')
        with self.settings(WHISPER_PROVIDER='disabled'): self.work()
        other.refresh_from_db(); self.assertEqual((other.processing_status, other.processing_error), ('FAILED', 'La transcription automatique n’est pas configurée sur ce serveur.'))
        with patch(TRANSCRIBE, side_effect=TranscriptionError('x' * 400)):
            third = self.audio(MP3 + b'y', 'Troisième'); self.work()
        self.assertEqual(len(Resource.objects.get(pk=third.pk).processing_error), 300)

    def test_empty_or_long_transcripts(self):
        resource = self.audio()
        with patch(TRANSCRIBE, return_value=Transcript([TranscriptSegment(0.0, 1.0, '   ')], 'fr', 3.5, 'fake', 'fake-whisper')):
            self.work()
        resource.refresh_from_db(); job = self.job(resource)
        self.assertEqual((resource.processing_status, resource.processing_error, resource.duration_seconds), ('NO_TEXT', 'Aucune parole détectée dans cet enregistrement.', 3.5))
        self.assertEqual((job.status, job.segments_count, self.reasons()[-1]), ('DONE', 0, 'resource_processed'))
        long = self.audio(MP3 + b'1', 'Long')
        segments = [TranscriptSegment(0.12345, 2.5, '  ' + 'a' * 25000 + ' '), TranscriptSegment(2.5, 4.0, ''), TranscriptSegment(4.0, 6.0, ' Fin. ')]
        with patch(TRANSCRIBE, return_value=Transcript(segments, 'english-like-code', None, 'fake', 'fake-whisper')):
            self.work()
        saved = list(ResourceSegment.objects.filter(resource=long))
        self.assertEqual([(s.order, len(s.text), s.start_seconds) for s in saved], [(1, 20000, 0.123), (2, 4, 4.0)])
        long.refresh_from_db(); self.assertEqual((long.language, long.duration_seconds), ('english-', None))

    def test_pdf_pages_capped_and_unreadable_pages_skipped(self):
        with patch.object(pypdf.PageObject, 'extract_text', side_effect=[RuntimeError('page'), 'x' * 25000]), self.assertLogs('courses', 'WARNING'):
            data = self.add_resource(self.course, self.chapter, pdf_bytes(['Première page.', 'Seconde page.']))
        self.assertEqual(data['processing_status'], 'READY')
        self.assertEqual([(s.page, len(s.text)) for s in ResourceSegment.objects.filter(resource_id=Resource.objects.get(pk=data['id']).pk)], [(2, 20000)])
        self.assertEqual(processing.clean_text('  Un\t\tdeux\x0c  trois \n\n\n\n quatre\r\n\x00cinq  '), 'Un deux trois\n\nquatre\ncinq')

    def test_reprocess_replaces_text_and_refuses_while_active(self):
        pdf = Resource.objects.get(pk=self.add_resource(self.course, self.chapter)['id'])
        segment = ResourceSegment.objects.filter(resource=pdf).first()
        self.patch(f'courses/{self.course.pk}/resources/{pdf.pk}/segments/{segment.pk}/', {'text': 'Correction manuelle.'})
        self.events.clear(); before = self.version(self.course)
        r = self.post(f'courses/{self.course.pk}/resources/{pdf.pk}/reprocess/'); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['processing_status'], r.data['text_version'], r.data['job']['status'], r.data['job']['attempts']), ('READY', 3, 'DONE', 1))
        self.assertEqual(ProcessingJob.objects.filter(resource=pdf).count(), 2)
        self.assertFalse(ResourceSegment.objects.filter(resource=pdf, edited=True).exists())
        self.assertEqual((self.reasons(), self.version(self.course)), (['resource_updated', 'resource_processed'], before + 2))
        audio = self.audio(); path = f'courses/{self.course.pk}/resources/{audio.pk}/reprocess/'
        r = self.post(path); self.assertEqual((r.status_code, r.data['error']['code'], r.data['error']['message']), (409, 'processing_in_progress', 'Un traitement est déjà en cours pour cette ressource.'))
        self.assertEqual(self.post(path, {'force': True}).status_code, 400)
        with patch(TRANSCRIBE, side_effect=TranscriptionError('Refusé.')): self.work()
        self.events.clear()
        r = self.post(path); self.assertEqual((r.status_code, r.data['processing_status'], r.data['processing_error'], r.data['job']['attempts']), (200, 'PENDING', '', 0))
        self.assertEqual((ProcessingJob.objects.filter(resource=audio).count(), self.events), (2, []))
        self.assertEqual(self.post(path).status_code, 409)
        self.work(); self.assertEqual(Resource.objects.get(pk=audio.pk).processing_status, 'READY')
        with self.settings(COURSES_PROCESS_INLINE=True):
            r = self.post(path); self.assertEqual((r.data['processing_status'], r.data['text_version']), ('READY', 2))
        self.assertEqual(self.post(f'courses/{self.course.pk}/resources/{"0" * 24}/reprocess/').status_code, 404)

    def test_stale_running_jobs_are_recovered(self):
        resource = self.audio(); job = processing.claim(worker='w1')
        self.assertEqual((job.status, job.attempts, job.worker), ('RUNNING', 1, 'w1'))
        self.assertEqual(Resource.objects.get(pk=resource.pk).processing_status, 'PROCESSING')
        ProcessingJob.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=10))
        self.assertEqual(processing.recover_stale(), 0)
        self.assertEqual(processing.recover_stale(now=timezone.now() + timedelta(minutes=6)), 1)
        job.refresh_from_db(); self.assertEqual((job.status, job.attempts, job.error), ('PENDING', 1, 'Le traitement a échoué. Réessayez plus tard.'))
        self.assertGreater(job.available_at, timezone.now()); self.assertEqual(Resource.objects.get(pk=resource.pk).processing_status, 'PENDING')
        ProcessingJob.objects.filter(pk=job.pk).update(attempts=2, available_at=timezone.now())
        job = processing.claim(); self.assertEqual(job.attempts, 3)
        ProcessingJob.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=20))
        self.assertIn('0 tâche(s) traitée(s).', self.work())
        job.refresh_from_db(); resource.refresh_from_db()
        self.assertEqual((job.status, job.active, resource.processing_status), ('FAILED', False, 'FAILED'))

    def test_claim_is_a_compare_and_swap(self):
        first = self.job(self.audio()); later = self.job(self.audio(MP3 + b'1', 'Autre'))
        ProcessingJob.objects.filter(pk=later.pk).update(available_at=timezone.now() + timedelta(minutes=5))
        self.assertEqual(processing.claim().pk, first.pk); self.assertIsNone(processing.claim(job_id=first.pk))
        self.assertIsNone(processing.claim()); self.assertIsNone(processing.claim(job_id=later.pk))
        ProcessingJob.objects.filter(pk=later.pk).update(available_at=timezone.now(), active=False)
        self.assertIsNone(processing.claim())
        ProcessingJob.objects.filter(pk=later.pk).update(active=True)
        AdminGuard.objects.get_or_create(key='accounts')
        def grab(_):
            try: return processing.claim(worker='concurrent')
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: claimed = [job for job in pool.map(grab, range(2)) if job]
        self.assertEqual([job.pk for job in claimed], [later.pk]); self.assertEqual(ProcessingJob.objects.get(pk=later.pk).attempts, 1)

    def test_result_of_a_superseded_claim_is_discarded(self):
        resource = self.audio(); stale = processing.claim(worker='w1')
        ProcessingJob.objects.filter(pk=stale.pk).update(started_at=timezone.now() - timedelta(minutes=20))
        processing.recover_stale(); self.release(stale)
        fresh = processing.claim(worker='w2'); self.assertEqual(fresh.attempts, 2)
        self.assertEqual(processing.run(stale).status, 'RUNNING')
        self.assertEqual((ResourceSegment.objects.count(), self.events), (0, []))
        done = processing.run(fresh); self.assertEqual((done.status, done.worker, done.segments_count), ('DONE', 'w2', 3))
        self.assertEqual(Resource.objects.get(pk=resource.pk).text_version, 1)

    def test_resource_deleted_during_processing(self):
        resource = self.audio(); name = resource.file.name.split('/')[-1]; real = FakeTranscriber.transcribe
        def delete_then_answer(transcriber, path, language=None):
            transcript = real(transcriber, path, language)
            self.assertEqual(self.client.delete(f'/api/courses/{self.course.pk}/resources/{resource.pk}/').status_code, 204)
            return transcript
        with patch(TRANSCRIBE, delete_then_answer): out = self.work()
        self.assertIn('ressource supprimée pendant le traitement', out)
        self.assertEqual((ResourceSegment.objects.count(), ProcessingJob.objects.count(), Resource.objects.count()), (0, 0, 0))
        self.assertNotIn(name, self.stored_files()); self.assertEqual(self.reasons(), ['resource_deleted'])
        self.assertIsNone(processing.run(ProcessingJob(pk=resource.pk, resource_id=resource.pk, kind='TRANSCRIBE_AUDIO', attempts=1)))

    def test_job_left_without_its_resource_is_closed(self):
        resource = self.audio(); job = processing.claim()
        Resource.objects.filter(pk=resource.pk)._raw_delete('default')
        done = processing.run(job)
        self.assertEqual((done.status, done.active, done.error), ('FAILED', False, 'La ressource a été supprimée pendant le traitement.'))
        second = self.audio(MP3 + b'1', 'Autre'); job = processing.claim(); real = FakeTranscriber.transcribe
        def vanish(transcriber, path, language=None):
            transcript = real(transcriber, path, language); Resource.objects.filter(pk=second.pk)._raw_delete('default'); return transcript
        with patch(TRANSCRIBE, vanish): done = processing.run(job)
        self.assertEqual((done.status, done.active, done.error), ('FAILED', False, 'La ressource a été supprimée pendant le traitement.'))
        self.assertEqual((ResourceSegment.objects.count(), self.events), (0, []))

    def test_signal_is_not_sent_when_the_transaction_rolls_back(self):
        self.events.clear()
        with patch('courses.views.course_detail', side_effect=DatabaseError('write conflict')):
            r = self.patch(f'courses/{self.course.pk}/', {'group_ids': [str(self.second_group.pk)]})
        self.assertEqual((r.status_code, self.events, self.version(self.course)), (409, [], 1))
        self.assertEqual(list(CourseGroup.objects.filter(course=self.course).values_list('group_id', flat=True)), [self.group.pk])

    def test_signal_receiver_errors_do_not_break_the_request(self):
        from courses.signals import course_content_changed
        def broken(**kwargs): raise RuntimeError('récepteur')
        course_content_changed.connect(broken, weak=False, dispatch_uid='broken'); self.addCleanup(course_content_changed.disconnect, dispatch_uid='broken')
        with self.assertLogs('django.db.backends.base', 'ERROR'):
            r = self.patch(f'courses/{self.course.pk}/', {'group_ids': [str(self.second_group.pk)]})
        self.assertEqual((r.status_code, self.reasons()), (200, ['groups_changed']))

    def test_worker_stops_cleanly_on_sigterm_or_sigint(self):
        before = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
        for number, queued in ((signal.SIGTERM, 0), (signal.SIGINT, 1)):
            if queued: self.audio()
            naps = []
            # Only the worker's own clock is replaced; the handler it installed is invoked as a delivered signal would.
            def nap(seconds): naps.append(seconds); signal.getsignal(number)(number, None)
            clock = SimpleNamespace(monotonic=time.monotonic, sleep=nap)
            out = StringIO()
            with patch('courses.management.commands.process_course_jobs.time', clock):
                call_command('process_course_jobs', '--sleep', '30', stdout=out)
            self.assertEqual((out.getvalue().splitlines()[-1], naps), (f'{queued} tâche(s) traitée(s).', [0.2]))
            self.assertEqual((signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)), before)
        self.assertEqual(Resource.objects.get().processing_status, 'READY')

    def test_processing_status_is_scoped(self):
        self.audio(); self.audio(MP3 + b'1', 'Autre')
        failed = self.audio(MP3 + b'2', 'Échec'); Resource.objects.filter(pk=failed.pk).update(processing_status='FAILED')
        running = self.audio(MP3 + b'3', 'En cours'); Resource.objects.filter(pk=running.pk).update(processing_status='PROCESSING')
        foreign = self.make_course(teacher=self.other, groups=[self.other_group])
        Resource.objects.create(course=foreign, chapter=self.make_chapter(foreign), kind='AUDIO', title='Étranger', position=1, file='courses/x.mp3',
            original_name='x.mp3', mime_type='audio/mpeg', size=1, sha256='0' * 64, uploaded_by=self.other)
        r = self.client.get('/api/courses/processing/')
        self.assertEqual(r.data, {'provider': 'fake', 'configured': True, 'model': 'fake-whisper', 'process_inline': False, 'pending': 2, 'running': 1, 'failed': 1})
        self.assertEqual(self.as_user(self.admin).get('/api/courses/processing/').data['pending'], 3)
        self.assertEqual(self.as_user(self.other).get('/api/courses/processing/').data['pending'], 1)
        with self.settings(WHISPER_PROVIDER='disabled', COURSES_PROCESS_INLINE=True):
            r = self.client.get('/api/courses/processing/')
        self.assertEqual((r.data['provider'], r.data['configured'], r.data['model'], r.data['process_inline']), ('disabled', False, '', True))
        self.assertEqual(self.as_user(self.student).get('/api/courses/processing/').status_code, 403)
