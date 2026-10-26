import os
import secrets
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO, StringIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from courses.models import Chapter, Course, CourseGroup, Subject
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


def blank_pdf(pages=2, password=None, owner=None):
    """Pages without any text layer, like a scanned document; optionally encrypted."""
    writer = PdfWriter()
    for _ in range(pages): writer.add_blank_page(612, 792)
    if password is not None: writer.encrypt(password, owner)
    out = BytesIO(); writer.write(out); return out.getvalue()


MP3 = b'ID3\x04\x00\x00\x00\x00\x00\x00' + bytes(range(256)) * 4
# Smallest payloads each magic-byte rule accepts: (content, MIME type, stored extension).
AUDIO = {
    'mp3-id3': (MP3, 'audio/mpeg', 'mp3'),
    'mp3-sync': (b'\xff\xfb\x90\x00' + b'\x00' * 200, 'audio/mpeg', 'mp3'),
    'wav': (b'RIFF\x24\x00\x00\x00WAVEfmt ' + b'\x00' * 200, 'audio/wav', 'wav'),
    'ogg': (b'OggS' + b'\x01' * 200, 'audio/ogg', 'ogg'),
    'webm': (b'\x1a\x45\xdf\xa3' + b'\x02' * 200, 'audio/webm', 'webm'),
    'm4a': (b'\x00\x00\x00\x20ftypM4A ' + b'\x03' * 200, 'audio/mp4', 'm4a'),
    'flac': (b'fLaC' + b'\x04' * 200, 'audio/flac', 'flac'),
}
LESSON = ['Les fonctions dérivées en mathématiques.\nUne dérivée mesure une variation locale.', 'Les intégrales et les primitives.']


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], WHISPER_PROVIDER='fake', COURSES_PROCESS_INLINE=False)
class CourseTestCase(TransactionTestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        media = self.settings(MEDIA_ROOT=self.media); media.enable()
        self.addCleanup(media.disable); self.addCleanup(shutil.rmtree, self.media, True)
        password = secrets.token_urlsafe(24)
        self.admin = User.objects.create_superuser('admin@cours.test', password, first_name='Admin', last_name='Nexora')
        self.teacher = User.objects.create_user('teacher@cours.test', password, role='TEACHER', first_name='Amel', last_name='Ben Salah')
        self.other = User.objects.create_user('other@cours.test', password, role='TEACHER', first_name='Karim', last_name='Jlassi')
        self.student = User.objects.create_user('student@cours.test', password, first_name='Sami', last_name='Trabelsi')
        self.classmate = User.objects.create_user('classmate@cours.test', password, first_name='Ines', last_name='Gharbi')
        self.past = User.objects.create_user('past@cours.test', password, first_name='Ali', last_name='Ancien')
        self.future = User.objects.create_user('future@cours.test', password, first_name='Nour', last_name='Futur')
        self.outsider = User.objects.create_user('outsider@cours.test', password, first_name='Rim', last_name='Ailleurs')
        self.group = LearningGroup.objects.create(name='Analyse', code='AN1', teacher=self.teacher, level='L1', academic_year='2026')
        self.second_group = LearningGroup.objects.create(name='Algèbre', code='AL1', teacher=self.teacher, level='L1', academic_year='2026')
        self.other_group = LearningGroup.objects.create(name='Physique', code='PH1', teacher=self.other, level='L1', academic_year='2026')
        now = timezone.now()
        self.enrollment = Enrollment.objects.create(student=self.student, group=self.group, starts_at=now - timedelta(days=1))
        Enrollment.objects.create(student=self.classmate, group=self.group, starts_at=now - timedelta(days=1))
        Enrollment.objects.create(student=self.past, group=self.group, starts_at=now - timedelta(days=30), ends_at=now - timedelta(days=1))
        Enrollment.objects.create(student=self.future, group=self.group, starts_at=now + timedelta(days=1))
        Enrollment.objects.create(student=self.outsider, group=self.other_group, starts_at=now - timedelta(days=1))
        self.subject = Subject.objects.create(name='Mathématiques', code='MATH', created_by=self.teacher)
        self.client = self.as_user(self.teacher)
        self.events = []
        def receiver(**kwargs): self.events.append(kwargs)
        course_content_changed.connect(receiver, weak=False, dispatch_uid='course-tests')
        self.addCleanup(course_content_changed.disconnect, dispatch_uid='course-tests')

    def as_user(self, user):
        c = APIClient(); c.force_login(user); return c

    def post(self, path, data=None, client=None):
        return (client or self.client).post('/api/' + path, data if data is not None else {}, format='json')

    def patch(self, path, data, client=None):
        return (client or self.client).patch('/api/' + path, data, format='json')

    def course_data(self, **kwargs):
        data = dict(title='Analyse réelle', description='Dérivées et intégrales.', subject_id=str(self.subject.pk), group_ids=[str(self.group.pk)])
        data.update(kwargs); return data

    def make_course(self, groups=None, teacher=None, **kwargs):
        """Course written straight to the database, linked to the given groups (the teacher's first group by default)."""
        values = dict(title='Analyse réelle', description='Dérivées et intégrales.', subject=self.subject, teacher=teacher or self.teacher)
        values.update(kwargs)
        course = Course.objects.create(**values)
        for group in (groups if groups is not None else [self.group]): CourseGroup.objects.create(course=course, group=group)
        return course

    def make_chapter(self, course, title='Chapitre 1', **kwargs):
        position = Chapter.objects.filter(course=course).count() + 1
        return Chapter.objects.create(course=course, title=title, position=position, **kwargs)

    def upload(self, course, chapter, content, name='support.pdf', title='Support', client=None, **extra):
        data = {'chapter_id': str(getattr(chapter, 'pk', chapter)), 'title': title, 'file': SimpleUploadedFile(name, content, content_type='application/octet-stream'), **extra}
        return (client or self.client).post(f'/api/courses/{getattr(course, "pk", course)}/resources/', data, format='multipart')

    def add_resource(self, course, chapter, content=None, name='support.pdf', title='Support'):
        response = self.upload(course, chapter, content if content is not None else pdf_bytes(LESSON), name, title)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def published_course(self, groups=None, content=None, **kwargs):
        """Published course with one chapter and one processed PDF resource."""
        course = self.make_course(groups, **kwargs); chapter = self.make_chapter(course)
        resource = self.add_resource(course, chapter, content)
        response = self.post(f'courses/{course.pk}/publish/', client=self.as_user(course.teacher))
        self.assertEqual(response.status_code, 200, response.data)
        course.refresh_from_db()
        return course, chapter, resource

    def work(self, *args):
        out = StringIO(); call_command('process_course_jobs', '--once', *args, stdout=out); return out.getvalue()

    def stored_files(self):
        folder = os.path.join(self.media, 'courses')
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def version(self, course):
        return Course.objects.get(pk=course.pk).content_version

    def reasons(self):
        return [event['reason'] for event in self.events]
