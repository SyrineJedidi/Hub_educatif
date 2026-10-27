import secrets
import shutil
import tempfile
from datetime import timedelta
from io import StringIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from courses.models import ProcessingJob, Resource, ResourceSegment
from courses.signals import course_content_changed


def pdf_bytes(pages):
    """Minimal PDF with one Helvetica text stream per page; lines are separated by \\n."""
    def literal(line): return line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
        f'<< /Type /Pages /Kids [{" ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))}] /Count {len(pages)} >>'.encode(),
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    for i, text in enumerate(pages):
        stream = ('BT /F1 12 Tf 14 TL 72 720 Td ' + ' '.join(f'({literal(line)}) Tj T*' for line in text.split('\n')) + ' ET').encode('cp1252')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>'.encode())
        objects.append(b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream')
    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out)); out += b'%d 0 obj\n' % number + body + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offsets)
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
    return bytes(out)


MP3 = b'ID3\x04\x00\x00\x00\x00\x00\x00' + bytes(range(256)) * 4


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], WHISPER_PROVIDER='fake', COURSES_PROCESS_INLINE=False)
class CourseSmokeTests(TransactionTestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        override = self.settings(MEDIA_ROOT=media); override.enable()
        self.addCleanup(override.disable); self.addCleanup(shutil.rmtree, media, True)
        password = secrets.token_urlsafe(24)
        self.admin = User.objects.create_superuser('admin@cours.test', password)
        self.teacher = User.objects.create_user('teacher@cours.test', password, role='TEACHER', first_name='Amel', last_name='Ben Salah')
        self.other = User.objects.create_user('other@cours.test', password, role='TEACHER')
        self.student = User.objects.create_user('student@cours.test', password, first_name='Sami', last_name='Trabelsi')
        self.group = LearningGroup.objects.create(name='Analyse', code='AN1', teacher=self.teacher, level='L1', academic_year='2026')
        Enrollment.objects.create(student=self.student, group=self.group, starts_at=timezone.now() - timedelta(days=1))
        self.client = self.as_user(self.teacher)
        self.events = []
        def receiver(**kwargs): self.events.append(kwargs)
        course_content_changed.connect(receiver, weak=False, dispatch_uid='smoke')
        self.addCleanup(course_content_changed.disconnect, dispatch_uid='smoke')
    def as_user(self, user):
        c = APIClient(); c.force_login(user); return c
    def create_course(self):
        subject = self.client.post('/api/subjects/', {'name': 'Mathématiques', 'code': 'math-1'}, format='json')
        self.assertEqual(subject.status_code, 201, subject.data); self.assertEqual(subject.data['code'], 'MATH-1')
        duplicate = self.client.post('/api/subjects/', {'name': '  mathematiques ', 'code': 'MATH-2'}, format='json')
        self.assertEqual(duplicate.status_code, 400); self.assertIn('name', duplicate.data['error']['fields'])
        course = self.client.post('/api/courses/', {'title': 'Analyse réelle', 'description': 'Dérivées et intégrales.',
            'subject_id': subject.data['id'], 'group_ids': [str(self.group.pk)]}, format='json')
        self.assertEqual(course.status_code, 201, course.data); self.assertEqual(course.data['status'], 'DRAFT')
        self.assertEqual(len(course.data['publication_blockers']), 2)
        chapter = self.client.post(f'/api/courses/{course.data["id"]}/chapters/', {'title': 'Chapitre 1 : dérivation'}, format='json')
        self.assertEqual(chapter.status_code, 201, chapter.data); self.assertEqual(chapter.data['position'], 1)
        return course.data['id'], chapter.data['id']
    def upload(self, course_id, chapter_id, content, name, title='Support'):
        return self.client.post(f'/api/courses/{course_id}/resources/', {'chapter_id': chapter_id, 'title': title,
            'file': SimpleUploadedFile(name, content, content_type='application/octet-stream')}, format='multipart')

    def test_pdf_publication_student_consultation_search_and_statistics(self):
        course_id, chapter_id = self.create_course()
        pdf = pdf_bytes(['Les fonctions dérivées en mathématiques.\nUne dérivée mesure une variation.', 'Les intégrales et les primitives.'])
        r = self.upload(course_id, chapter_id, pdf, '../../cours\x00 1.pdf')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['kind'], r.data['mime_type'], r.data['processing_status'], r.data['page_count'], r.data['segments_count']), ('PDF', 'application/pdf', 'READY', 2, 2))
        self.assertEqual(r.data['original_name'], 'cours 1.pdf'); self.assertEqual(r.data['job']['status'], 'DONE')
        self.assertRegex(Resource.objects.get(pk=r.data['id']).file.name, r'^courses/[0-9a-f]{32}\.pdf$')
        self.assertEqual(self.events[-1]['reason'], 'resource_processed')
        resource_id = r.data['id']
        self.assertEqual(self.upload(course_id, chapter_id, pdf, 'copie.pdf').status_code, 400)
        r = self.client.post(f'/api/courses/{course_id}/publish/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data); self.assertEqual(r.data['status'], 'PUBLISHED'); self.assertIsNotNone(r.data['published_at'])

        student = self.as_user(self.student)
        listing = student.get('/api/student/courses/')
        self.assertEqual(listing.data['count'], 1); self.assertEqual(listing.data['results'][0]['progress'], {'viewed': 0, 'total': 1, 'percent': 0})
        detail = student.get(f'/api/student/courses/{course_id}/')
        self.assertFalse(detail.data['chapters'][0]['resources'][0]['viewed'])
        segments = student.get(f'/api/student/courses/{course_id}/resources/{resource_id}/segments/')
        self.assertEqual([s['page'] for s in segments.data['results']], [1, 2]); self.assertIn('dérivée', segments.data['results'][0]['text'])
        view = student.post(f'/api/student/courses/{course_id}/resources/{resource_id}/views/', {}, format='json')
        self.assertEqual(view.status_code, 200, view.data); self.assertEqual(view.data['progress'], {'viewed': 1, 'total': 1, 'percent': 100})
        file = student.get(f'/api/courses/resources/{resource_id}/file/')
        self.assertEqual((file.status_code, file['Content-Type'], file['X-Frame-Options']), (200, 'application/pdf', 'SAMEORIGIN'))
        self.assertEqual(b''.join(file.streaming_content), pdf)
        part = student.get(f'/api/courses/resources/{resource_id}/file/?download=1', HTTP_RANGE='bytes=0-7')
        self.assertEqual((part.status_code, part['Content-Range'], b''.join(part.streaming_content)), (206, f'bytes 0-7/{len(pdf)}', pdf[:8]))
        self.assertTrue(part['Content-Disposition'].startswith('attachment;'))
        self.assertEqual(self.as_user(self.other).get(f'/api/courses/resources/{resource_id}/file/').status_code, 404)

        found = student.get('/api/courses/search/', {'q': 'DERIVEE variation'})
        self.assertEqual(found.status_code, 200, found.data)
        hit = next(item for item in found.data['results'] if item['type'] == 'segment')
        self.assertEqual((hit['page'], hit['link']), (1, f'/espace/cours/{course_id}/ressources/{resource_id}?page=1'))
        self.assertEqual([hit['snippet'][a:b] for a, b in hit['highlights']], ['dérivée', 'dérivée', 'variation'])
        self.assertEqual(student.get('/api/courses/search/', {'q': 'd'}).status_code, 400)
        self.assertEqual(self.as_user(self.other).get('/api/courses/search/', {'q': 'dérivée'}).data['count'], 0)

        stats = self.client.get(f'/api/courses/{course_id}/statistics/')
        self.assertEqual(stats.status_code, 200, stats.data)
        self.assertEqual(stats.data['summary'], {'students': 1, 'resources': 1, 'average_percent': 100.0, 'completed_students': 1})
        self.assertEqual(stats.data['resources'][0]['total_views'], 1)
        export = self.client.get(f'/api/courses/{course_id}/statistics/', {'format': 'csv'})
        self.assertEqual(export.status_code, 200); self.assertIn('Trabelsi;Sami;1;1;100;', export.content.decode('utf-8-sig'))
        self.assertEqual(student.get(f'/api/courses/{course_id}/statistics/').status_code, 403)

    def test_audio_transcribed_by_worker_with_fake_provider(self):
        course_id, chapter_id = self.create_course()
        r = self.upload(course_id, chapter_id, MP3, 'cours.mp3', 'Cours enregistré')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['kind'], r.data['mime_type'], r.data['processing_status']), ('AUDIO', 'audio/mpeg', 'PENDING'))
        out = StringIO(); call_command('process_course_jobs', '--once', stdout=out)
        self.assertIn('1 tâche(s) traitée(s).', out.getvalue())
        resource = Resource.objects.get(pk=r.data['id'])
        self.assertEqual((resource.processing_status, resource.duration_seconds, resource.language, resource.text_version), ('READY', 15.0, 'fr', 1))
        self.assertEqual(list(ResourceSegment.objects.filter(resource=resource).values_list('start_seconds', flat=True)), [0.0, 5.0, 10.0])
        job = ProcessingJob.objects.get(resource=resource)
        self.assertEqual((job.status, job.active, job.attempts, job.provider, job.segments_count), ('DONE', False, 1, 'fake', 3))
        self.assertEqual(self.events[-1], {'signal': course_content_changed, 'sender': self.events[-1]['sender'], 'course_id': course_id, 'resource_id': r.data['id'], 'reason': 'resource_processed'})
        status = self.client.get('/api/courses/processing/').data
        self.assertEqual((status['provider'], status['configured'], status['pending']), ('fake', True, 0))

    def test_scope_roles_and_integration_checks(self):
        course_id, _ = self.create_course()
        self.assertEqual(APIClient().get('/api/courses/').status_code, 401)
        self.assertEqual(self.as_user(self.student).get('/api/courses/').status_code, 403)
        self.assertEqual(self.as_user(self.other).get(f'/api/courses/{course_id}/').status_code, 404)
        self.assertEqual(self.as_user(self.student).get(f'/api/student/courses/{course_id}/').status_code, 404)
        admin = self.as_user(self.admin)
        self.assertEqual(admin.delete(f'/api/groups/{self.group.pk}/').status_code, 400)
        self.group.archived = True; self.group.save()
        r = admin.patch(f'/api/admin/users/{self.teacher.pk}/', {'role': 'STUDENT'}, format='json')
        self.assertEqual(r.status_code, 400); self.assertIn('cours', r.data['error']['fields']['role'][0])
        self.assertEqual(admin.post(f'/api/courses/{course_id}/archive/', {}, format='json').status_code, 200)
        self.assertEqual(admin.patch(f'/api/admin/users/{self.teacher.pk}/', {'role': 'STUDENT'}, format='json').status_code, 200)
