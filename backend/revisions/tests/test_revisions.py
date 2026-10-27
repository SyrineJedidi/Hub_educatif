import secrets
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO
from unittest import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from ..ai.clients import AIServiceError
from ..models import AIJob, RevisionSheet, Illustration

MEDIA = tempfile.mkdtemp(prefix='nexora-revisions-')
SUMMARY = '## Introduction\nLa photosynthèse transforme la lumière en énergie chimique pour la plante.'
GENERATED = {'summary': SUMMARY, 'key_points': ['La chlorophylle capte la lumière.', 'Le glucose stocke l’énergie.'],
             'glossary': [{'term': 'Chlorophylle', 'definition': 'Pigment vert des végétaux.'}], 'tags': ['biologie', 'énergie'],
             'illustration_prompt': 'A leaf absorbing sunlight', 'model': 'gemini-test', 'duration_ms': 1200}


def png_bytes(size=(64, 48), color=(82, 95, 225)):
    output = BytesIO(); Image.new('RGB', size, color).save(output, format='PNG'); return output.getvalue()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MEDIA_ROOT=MEDIA,
                   GEMINI_API_KEY='test-key', HF_TOKEN='test-token', AI_JOB_BACKEND='sync')
class RevisionSheetTests(TransactionTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass(); shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        password = secrets.token_urlsafe(24)
        self.admin = User.objects.create_superuser('admin@fiches.test', password)
        self.teacher = User.objects.create_user('teacher@fiches.test', password, role='TEACHER', first_name='Amel', last_name='Prof')
        self.other = User.objects.create_user('other@fiches.test', password, role='TEACHER')
        self.student = User.objects.create_user('student@fiches.test', password, first_name='Sami', last_name='Élève')
        self.outsider = User.objects.create_user('outsider@fiches.test', password)
        self.group = LearningGroup.objects.create(name='Biologie', code='BIO', teacher=self.teacher, level='L1', academic_year='2026')
        self.other_group = LearningGroup.objects.create(name='Autre', code='OTH', teacher=self.other, level='L1', academic_year='2026')
        now = timezone.now()
        Enrollment.objects.create(student=self.student, group=self.group, starts_at=now - timedelta(days=1))
        Enrollment.objects.create(student=self.outsider, group=self.other_group, starts_at=now - timedelta(days=1))
        self.client = self.as_user(self.teacher)

    def as_user(self, user):
        c = APIClient(); c.force_login(user); return c

    def data(self, **kwargs):
        values = dict(title='La photosynthèse', course_label='Biologie végétale', learning_group_id=str(self.group.pk),
                      summary=SUMMARY, key_points=['La lumière est convertie en énergie.'], tags=['Bio', '#bio', 'Plantes'])
        values.update(kwargs); return values

    def create(self, client=None, **kwargs):
        r = (client or self.client).post('/api/sheets/', self.data(**kwargs), format='json')
        self.assertEqual(r.status_code, 201, r.data); return r.data

    def post(self, path, data=None, client=None, **kwargs):
        return (client or self.client).post('/api/' + path, data if data is not None else {}, **({'format': 'json'} | kwargs))

    # --- CRUD and validation -------------------------------------------------

    def test_teacher_creates_draft_with_normalized_content(self):
        sheet = self.create()
        self.assertEqual(sheet['status'], 'DRAFT'); self.assertFalse(sheet['personal'])
        self.assertEqual(sheet['tags'], ['bio', 'plantes']); self.assertTrue(sheet['can_edit'])
        self.assertEqual(sheet['learning_group_name'], 'Biologie'); self.assertEqual(sheet['owner_name'], 'Amel Prof')
        self.assertEqual(RevisionSheet.objects.get(pk=sheet['id']).owner_id, self.teacher.pk)

    def test_validation_errors(self):
        cases = [dict(title='  '), dict(title='x' * 121), dict(course_label=''), dict(summary='x' * 20001),
                 dict(key_points=['ok'] * 16), dict(key_points='texte'), dict(tags=[f't{i}' for i in range(9)]), dict(tags=['x' * 31]),
                 dict(glossary=[{'term': 'A', 'definition': 'B'}, {'term': ' a ', 'definition': 'C'}]),
                 dict(glossary=[{'term': 'A'}]), dict(glossary=[{'term': 'A', 'definition': 'B', 'extra': 1}]),
                 dict(color='PURPLE'), dict(pinned='yes'), dict(status='PUBLISHED'), dict(teacher_id=str(self.other.pk)),
                 dict(learning_group_id=str(self.other_group.pk)), dict(learning_group_id='nope'), dict(owner_id='x')]
        for change in cases:
            r = self.client.post('/api/sheets/', self.data(**change), format='json')
            self.assertEqual(r.status_code, 400, (change, r.data))
        self.assertEqual(self.client.post('/api/sheets/', ['liste'], format='json').status_code, 400)
        self.group.archived = True; self.group.save()
        self.assertEqual(self.client.post('/api/sheets/', self.data(), format='json').status_code, 400)

    def test_student_personal_sheets(self):
        student = self.as_user(self.student)
        r = student.post('/api/sheets/', self.data(), format='json')
        self.assertEqual(r.status_code, 400); self.assertIn('learning_group_id', r.data['error']['fields'])
        data = self.data(); data.pop('learning_group_id')
        sheet = student.post('/api/sheets/', data, format='json').data
        self.assertTrue(sheet['personal']); self.assertIsNone(sheet['learning_group_id'])
        r = self.post(f'sheets/{sheet["id"]}/publish/', client=student)
        self.assertEqual(r.status_code, 400); self.assertIn('Une fiche personnelle ne peut pas être publiée.', r.data['error']['fields']['publication'])
        # Personal sheets are private, even for the teacher and other students.
        self.assertEqual(self.client.get(f'/api/sheets/{sheet["id"]}/').status_code, 404)
        self.assertEqual(self.as_user(self.outsider).get(f'/api/sheets/{sheet["id"]}/').status_code, 404)
        self.assertEqual(self.as_user(self.admin).get(f'/api/sheets/{sheet["id"]}/').status_code, 200)

    def test_patch_partial_and_archived_lock(self):
        sheet = self.create()
        r = self.client.patch(f'/api/sheets/{sheet["id"]}/', {'title': 'Nouveau titre', 'pinned': True, 'color': 'TEAL'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['title'], r.data['pinned'], r.data['color'], r.data['summary']), ('Nouveau titre', True, 'TEAL', SUMMARY))
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/archive/').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/sheets/{sheet["id"]}/', {'title': 'Bloqué'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/sheets/{sheet["id"]}/', {'pinned': False}, format='json').status_code, 200)
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/unpublish/').data['status'], 'DRAFT')

    def test_delete_rules_and_files(self):
        sheet = self.create()
        ill = self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': SimpleUploadedFile('a.png', png_bytes()), 'caption': 'Schéma'}, format='multipart').data
        path = Illustration.objects.get(pk=ill['id']).image.path
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/publish/').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/sheets/{sheet["id"]}/').status_code, 400)
        self.post(f'sheets/{sheet["id"]}/unpublish/')
        self.assertEqual(self.client.delete(f'/api/sheets/{sheet["id"]}/').status_code, 204)
        self.assertFalse(RevisionSheet.objects.filter(pk=sheet['id']).exists()); self.assertFalse(Illustration.objects.exists())
        import os; self.assertFalse(os.path.exists(path))

    # --- Permissions -----------------------------------------------------------

    def test_isolation_between_teachers_and_students(self):
        sheet = self.create(); other = self.as_user(self.other)
        for path in [f'sheets/{sheet["id"]}/', f'sheets/{sheet["id"]}/export/', f'sheets/{sheet["id"]}/illustrations/']:
            self.assertEqual(other.get('/api/' + path).status_code, 404, path)
        for action in ['publish', 'archive', 'unpublish', 'duplicate', 'generate', 'illustrations/generate', 'illustrations/reorder']:
            self.assertEqual(self.post(f'sheets/{sheet["id"]}/{action}/', client=other).status_code, 404, action)
        self.assertEqual(other.get('/api/sheets/').data['count'], 0)
        # A draft is invisible to the group; a published sheet is visible but read-only.
        student = self.as_user(self.student)
        self.assertEqual(student.get(f'/api/sheets/{sheet["id"]}/').status_code, 404)
        self.post(f'sheets/{sheet["id"]}/publish/')
        r = student.get(f'/api/sheets/{sheet["id"]}/'); self.assertEqual(r.status_code, 200); self.assertFalse(r.data['can_edit'])
        self.assertEqual(r.data['publication_blockers'], [])
        self.assertEqual(student.patch(f'/api/sheets/{sheet["id"]}/', {'title': 'Pirate'}, format='json').status_code, 404)
        self.assertEqual(student.delete(f'/api/sheets/{sheet["id"]}/').status_code, 404)
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/archive/', client=student).status_code, 404)
        self.assertEqual(self.as_user(self.outsider).get(f'/api/sheets/{sheet["id"]}/').status_code, 404)
        self.assertEqual(APIClient().get('/api/sheets/').status_code, 401)

    def test_enrollment_window_controls_access(self):
        sheet = self.create(); self.post(f'sheets/{sheet["id"]}/publish/')
        student = self.as_user(self.student)
        self.assertEqual(student.get('/api/sheets/?scope=groups').data['count'], 1)
        Enrollment.objects.filter(student=self.student).update(ends_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(student.get('/api/sheets/').data['count'], 0)

    def test_admin_manages_on_behalf_of_teacher(self):
        admin = self.as_user(self.admin)
        r = admin.post('/api/sheets/', self.data(), format='json'); self.assertEqual(r.status_code, 400)
        self.assertIn('teacher_id', r.data['error']['fields'])
        r = admin.post('/api/sheets/', self.data(teacher_id=str(self.student.pk)), format='json'); self.assertEqual(r.status_code, 400)
        r = admin.post('/api/sheets/', self.data(teacher_id=str(self.other.pk)), format='json'); self.assertEqual(r.status_code, 400)
        r = admin.post('/api/sheets/', self.data(teacher_id=str(self.teacher.pk)), format='json'); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['owner_id'], str(self.teacher.pk)); self.assertTrue(r.data['can_edit'])
        self.assertEqual(self.client.get('/api/sheets/').data['count'], 1)

    def test_published_sheet_cannot_change_group(self):
        group2 = LearningGroup.objects.create(name='Bio 2', code='BIO2', teacher=self.teacher, level='L2', academic_year='2026')
        sheet = self.create(); self.post(f'sheets/{sheet["id"]}/publish/')
        r = self.client.patch(f'/api/sheets/{sheet["id"]}/', {'learning_group_id': str(group2.pk)}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.patch(f'/api/sheets/{sheet["id"]}/', {'summary': SUMMARY + ' Corrigé.'}, format='json').status_code, 200)

    # --- Publication -----------------------------------------------------------

    def test_publication_blockers(self):
        sheet = self.create(summary='Court', key_points=[])
        r = self.post(f'sheets/{sheet["id"]}/publish/'); self.assertEqual(r.status_code, 400)
        self.assertEqual(len(r.data['error']['fields']['publication']), 2)
        detail = self.client.get(f'/api/sheets/{sheet["id"]}/').data; self.assertEqual(len(detail['publication_blockers']), 2)
        self.client.patch(f'/api/sheets/{sheet["id"]}/', {'summary': SUMMARY, 'key_points': ['Un point']}, format='json')
        r = self.post(f'sheets/{sheet["id"]}/publish/'); self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'PUBLISHED'); self.assertIsNotNone(r.data['published_at'])
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/publish/').status_code, 400)
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/publish/', {'force': True}).status_code, 400)

    # --- AI generation ---------------------------------------------------------

    def generate(self, sheet_id, body, **kwargs):
        r = self.post(f'sheets/{sheet_id}/generate/', body, **kwargs)
        self.assertEqual(r.status_code, 202, r.data)
        return r.data

    @mock.patch('revisions.ai.jobs.generate_summary', return_value=dict(GENERATED))
    def test_generate_summary_job_requires_review(self, gemini):
        sheet = self.create(summary='', key_points=[], tags=['photosynthèse'])
        source = 'La chlorophylle des feuilles capte la lumière et produit du glucose. ' * 5
        job = self.generate(sheet['id'], {'source_text': source, 'length': 'SHORT'})
        self.assertEqual((job['kind'], job['status'], job['engine'], job['model']), ('SUMMARY', 'SUCCEEDED', 'gemini', 'gemini-test'))
        self.assertEqual(gemini.call_args.kwargs, {'title': 'La photosynthèse', 'course': 'Biologie végétale', 'length': 'SHORT'})
        self.assertEqual(job['params']['source_characters'], len(source.strip()))
        self.assertIsNotNone(job['duration_ms']); self.assertIsNotNone(job['queue_ms'])
        # Quality metrics are computed for every summary.
        metrics = job['metrics']
        self.assertGreater(metrics['keyword_coverage'], 0.5); self.assertTrue(metrics['checks']['has_sections'])
        self.assertEqual((metrics['key_points'], metrics['glossary_terms']), (2, 1))
        self.assertEqual(AIJob.objects.get(pk=job['id']).source_text, '')
        detail = self.client.get(f'/api/sheets/{sheet["id"]}/').data
        self.assertEqual(detail['summary'], SUMMARY); self.assertTrue(detail['ai_generated']); self.assertFalse(detail['ai_reviewed'])
        self.assertEqual(detail['tags'], ['photosynthèse', 'biologie', 'énergie']); self.assertEqual(detail['ai_model'], 'gemini-test')
        self.assertIn('Confirmez la relecture du contenu généré par l’IA avant de le partager.', detail['publication_blockers'])
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/publish/').status_code, 400)
        self.client.patch(f'/api/sheets/{sheet["id"]}/', {'ai_reviewed': True}, format='json')
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/publish/').status_code, 200)
        # A published sheet must go back to draft before regenerating unreviewed content.
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/generate/', {'source_text': 'Texte ' * 30}).status_code, 400)
        jobs = self.client.get(f'/api/sheets/{sheet["id"]}/jobs/').data['results']
        self.assertEqual([j['id'] for j in jobs], [job['id']])

    @mock.patch('revisions.ai.jobs.generate_summary', return_value=dict(GENERATED))
    def test_generate_from_uploaded_text_file_and_validation(self, gemini):
        sheet = self.create()
        upload = SimpleUploadedFile('cours.txt', ('Chapitre 1. ' * 30).encode('utf-8'), content_type='text/plain')
        job = self.generate(sheet['id'], {'file': upload, 'length': 'DETAILED'}, format='multipart')
        self.assertEqual(job['source_name'], 'cours.txt'); self.assertEqual(job['params']['length'], 'DETAILED')
        self.assertTrue(gemini.call_args.args[0].startswith('Chapitre 1.'))
        bad = [{'source_text': '   '}, {'source_text': 'x', 'length': 'HUGE'}, {'source_text': 'x' * 60001}]
        for body in bad: self.assertEqual(self.post(f'sheets/{sheet["id"]}/generate/', body).status_code, 400, body)
        for name, content in [('cours.exe', b'MZ' * 100), ('court.txt', b'trop court'), ('faux.pdf', b'%PDF-pas-un-pdf' * 10)]:
            r = self.post(f'sheets/{sheet["id"]}/generate/', {'file': SimpleUploadedFile(name, content)}, format='multipart')
            self.assertEqual(r.status_code, 400, name)
        self.assertEqual(gemini.call_count, 1)

    def test_ai_errors_are_recorded_on_the_job(self):
        sheet = self.create()
        with override_settings(GEMINI_API_KEY='', REVISIONS_OLLAMA_MODEL=''):
            job = self.generate(sheet['id'], {'source_text': 'Texte du cours ' * 10})
            self.assertEqual(job['status'], 'FAILED'); self.assertIn('Ollama n’est pas configuré', job['error'])
        with mock.patch('revisions.ai.jobs.generate_summary', side_effect=AIServiceError('Quota')):
            job = self.generate(sheet['id'], {'source_text': 'Texte du cours ' * 10})
            self.assertEqual((job['status'], job['error']), ('FAILED', 'Quota'))
        with mock.patch('revisions.ai.jobs.generate_summary', side_effect=RuntimeError('bug')):
            job = self.generate(sheet['id'], {'source_text': 'Texte du cours ' * 10})
            self.assertEqual(job['error'], 'Erreur interne pendant la génération. Réessayez.')
        self.assertEqual(RevisionSheet.objects.get(pk=sheet['id']).summary, SUMMARY)

    def test_job_aborted_when_sheet_published_meanwhile(self):
        sheet = self.create()
        def publish_during_call(*args, **kwargs):
            RevisionSheet.objects.filter(pk=sheet['id']).update(status='PUBLISHED')
            return dict(GENERATED, summary='## Nouveau\nContenu non relu qui ne doit pas être publié.')
        with mock.patch('revisions.ai.jobs.generate_summary', side_effect=publish_during_call):
            job = self.generate(sheet['id'], {'source_text': 'Texte du cours ' * 10})
        self.assertEqual(job['status'], 'FAILED'); self.assertIn('publiée', job['error'])
        self.assertEqual(RevisionSheet.objects.get(pk=sheet['id']).summary, SUMMARY)

    @mock.patch('revisions.ai.jobs.generate_summary', return_value=dict(GENERATED))
    def test_rating_metrics_and_job_permissions(self, gemini):
        sheet = self.create()
        job = self.generate(sheet['id'], {'source_text': 'Les feuilles captent la lumière du soleil. ' * 8})
        self.assertEqual(self.post(f'ai/jobs/{job["id"]}/rating/', {'rating': 4}).data['rating'], 4)
        for bad in [0, 6, 'cinq', 2.5]: self.assertEqual(self.post(f'ai/jobs/{job["id"]}/rating/', {'rating': bad}).status_code, 400, bad)
        other, student = self.as_user(self.other), self.as_user(self.student)
        for client in [other, student]:
            self.assertEqual(client.get(f'/api/ai/jobs/{job["id"]}/').status_code, 404)
            self.assertEqual(self.post(f'ai/jobs/{job["id"]}/rating/', {'rating': 1}, client=client).status_code, 404)
            self.assertEqual(client.get(f'/api/sheets/{sheet["id"]}/jobs/').status_code, 404)
        admin = self.as_user(self.admin)
        self.assertEqual(admin.get(f'/api/ai/jobs/{job["id"]}/').data['user_name'], 'Amel Prof')
        self.assertEqual(self.post(f'ai/jobs/{job["id"]}/rating/', {'rating': 1}, client=admin).status_code, 404)
        metrics = admin.get('/api/ai/metrics/').data
        self.assertEqual((metrics['totals']['jobs'], metrics['success_rate'], metrics['rating']['mean']), (1, 1.0, 4.0))
        self.assertEqual(metrics['latency'][0]['engine'], 'gemini'); self.assertEqual(len(metrics['per_day']), 14)
        self.assertEqual(metrics['review_rate'], 0.0); self.assertEqual(metrics['configuration']['job_backend'], 'sync')
        self.assertEqual(other.get('/api/ai/metrics/').data['totals']['jobs'], 0)
        self.assertEqual(student.get('/api/ai/metrics/').status_code, 404)
        self.assertEqual(admin.get('/api/ai/metrics/?days=abc').status_code, 400)
        status = student.get('/api/ai/status/').data
        self.assertTrue(status['summary'] and status['illustration']); self.assertNotIn('test-key', str(status))

    def test_stale_jobs_are_expired_and_duplicates_refused(self):
        from datetime import timedelta
        sheet = self.create(); rs = RevisionSheet.objects.get(pk=sheet['id'])
        job = AIJob.objects.create(kind='SUMMARY', sheet=rs, sheet_title=rs.title, user=self.teacher, source_text='x', params={'length': 'SHORT', 'course': 'C'})
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/generate/', {'source_text': 'Texte du cours ' * 10}).status_code, 400)
        AIJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(hours=2))
        data = self.client.get(f'/api/ai/jobs/{job.pk}/').data
        self.assertEqual(data['status'], 'FAILED'); self.assertIn('interrompue', data['error'])
        self.assertEqual(AIJob.objects.get(pk=job.pk).source_text, '')

    @override_settings(AI_JOB_BACKEND='celery')
    def test_celery_unavailable_falls_back_to_thread(self):
        from ..ai import jobs
        sheet = self.create(); rs = RevisionSheet.objects.get(pk=sheet['id'])
        job = AIJob.objects.create(kind='SUMMARY', sheet=rs, sheet_title=rs.title, user=self.teacher, params={'length': 'SHORT', 'course': 'C'})
        pool = mock.Mock()
        with mock.patch('revisions.tasks.run_ai_job.delay', side_effect=OSError('broker down')), mock.patch.object(jobs, '_pool', pool):
            jobs.dispatch(job)
        pool.submit.assert_called_once_with(jobs._run_in_thread, job.pk)

    @override_settings(REVISIONS_OLLAMA_MODEL='qwen3:8b')
    def test_ollama_fallback_when_gemini_fails(self):
        from ..ai.clients import generate_summary
        local = {**GENERATED, 'model': 'ollama/qwen3:8b'}
        with mock.patch('revisions.ai.clients.gemini_summary', side_effect=AIServiceError('Surchargé')), \
             mock.patch('revisions.ai.clients.ollama_summary', return_value=local) as ollama:
            result = generate_summary('texte', title='T', course='C', length='SHORT')
        self.assertTrue(result['fallback']); self.assertEqual(result['model'], 'ollama/qwen3:8b'); ollama.assert_called_once()
        # When both fail, the user sees the Gemini error, which is the primary engine.
        with mock.patch('revisions.ai.clients.gemini_summary', side_effect=AIServiceError('Surchargé')), \
             mock.patch('revisions.ai.clients.ollama_summary', side_effect=AIServiceError('Ollama absent')):
            with self.assertRaisesMessage(AIServiceError, 'Surchargé'): generate_summary('t', title='T', course='C', length='SHORT')
        with override_settings(GEMINI_API_KEY=''), mock.patch('revisions.ai.clients.ollama_summary', return_value=local):
            self.assertFalse(generate_summary('t', title='T', course='C', length='SHORT')['fallback'])
        with override_settings(REVISIONS_OLLAMA_MODEL=''), mock.patch('revisions.ai.clients.gemini_summary', side_effect=AIServiceError('Surchargé')):
            with self.assertRaisesMessage(AIServiceError, 'Surchargé'): generate_summary('t', title='T', course='C', length='SHORT')

    def test_ollama_request_and_parsing(self):
        import json
        from ..ai.clients import ollama_summary
        answer = {'message': {'content': json.dumps({'summary': '## Titre\nTexte', 'key_points': ['Un'], 'glossary': [], 'tags': ['Bio'], 'illustration_prompt': 'leaf'})}}
        with override_settings(REVISIONS_OLLAMA_MODEL='qwen3:8b'), mock.patch('revisions.ai.clients._post', return_value=(json.dumps(answer).encode(), 'application/json')) as post:
            result = ollama_summary('x' * 40000, title='T', course='C', length='SHORT')
        url, _, payload = post.call_args.args
        self.assertTrue(url.endswith('/api/chat')); self.assertEqual(payload['format']['type'], 'object')
        self.assertFalse(payload['think']); self.assertLess(len(payload['messages'][1]['content']), 31000)
        self.assertEqual((result['model'], result['summary'], result['tags']), ('ollama/qwen3:8b', '## Titre\nTexte', ['bio']))

    @override_settings(HF_IMAGE_SPACE='black-forest-labs/FLUX.1-schnell')
    def test_hugging_face_space_image(self):
        import json
        from ..ai.clients import hf_illustration, space_url
        base = space_url('black-forest-labs/FLUX.1-schnell')
        self.assertEqual(base, 'https://black-forest-labs-flux-1-schnell.hf.space')
        done = f'event: complete\ndata: {json.dumps([{"url": base + "/gradio_api/file=/tmp/x.webp"}, 1])}\n'.encode()
        with mock.patch('revisions.ai.clients._post', return_value=(b'{"event_id": "e1"}', 'application/json')) as post, \
             mock.patch('revisions.ai.clients._get', side_effect=[(done, 'text/event-stream'), (b'IMAGE', 'image/webp')]) as get:
            image, model, _ = hf_illustration('Une feuille', 'FLAT')
        self.assertEqual((image, model), (b'IMAGE', 'black-forest-labs/FLUX.1-schnell'))
        self.assertTrue(post.call_args.args[0].endswith('/gradio_api/call/infer'))
        self.assertIn('Une feuille', post.call_args.args[2]['data'][0])
        self.assertEqual(get.call_args_list[0].args[0], base + '/gradio_api/call/infer/e1')
        quota = b'event: error\ndata: "You have exceeded your GPU quota"\n'
        foreign = f'event: complete\ndata: {json.dumps([{"url": "https://evil.example/x.webp"}])}\n'.encode()
        for stream, message in [(quota, 'quota GPU'), (foreign, 'adresse inattendue')]:
            with mock.patch('revisions.ai.clients._post', return_value=(b'{"event_id": "e1"}', '')), \
                 mock.patch('revisions.ai.clients._get', return_value=(stream, '')):
                with self.assertRaisesMessage(AIServiceError, message): hf_illustration('x', 'SCHEMA')

    def test_gemini_response_parsing(self):
        import json
        from ..ai.clients import gemini_summary
        payload = {'candidates': [{'content': {'parts': [{'text': json.dumps({
            'summary': '  Résumé  ', 'key_points': ['  A   point ', '', 3], 'tags': ['#Bio'], 'illustration_prompt': 'leaf',
            'glossary': [{'term': 'ATP', 'definition': 'Énergie'}, {'term': 'atp', 'definition': 'Doublon'}, 'bad']})}]}}]}
        with mock.patch('revisions.ai.clients._post', return_value=(json.dumps(payload).encode(), 'application/json')):
            result = gemini_summary('texte', title='T', course='C', length='STANDARD')
        self.assertEqual((result['summary'], result['key_points'], result['tags']), ('Résumé', ['A point'], ['bio']))
        self.assertEqual(result['glossary'], [{'term': 'ATP', 'definition': 'Énergie'}])
        escaped = {'candidates': [{'content': {'parts': [{'text': json.dumps({
            'summary': '## Titre\\n\\n- un\\n- deux', 'key_points': [], 'glossary': [], 'tags': [], 'illustration_prompt': ''})}]}}]}
        with mock.patch('revisions.ai.clients._post', return_value=(json.dumps(escaped).encode(), 'application/json')):
            self.assertEqual(gemini_summary('t', title='T', course='C', length='SHORT')['summary'], '## Titre\n\n- un\n- deux')
        blocked = {'promptFeedback': {'blockReason': 'SAFETY'}}
        with mock.patch('revisions.ai.clients._post', return_value=(json.dumps(blocked).encode(), 'application/json')):
            with self.assertRaises(AIServiceError): gemini_summary('texte', title='T', course='C', length='SHORT')

    # --- Illustrations ---------------------------------------------------------

    def test_upload_serve_and_protect_illustrations(self):
        sheet = self.create()
        r = self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': SimpleUploadedFile('s.png', png_bytes((3000, 1500))), 'caption': 'Cycle de Calvin'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['width'], r.data['height'], r.data['source'], r.data['position']), (1600, 800, 'UPLOAD', 1))
        image = self.client.get(r.data['url']); self.assertEqual(image.status_code, 200); self.assertEqual(image['Content-Type'], 'image/webp')
        self.assertIn('private', image['Cache-Control'])
        self.assertEqual(self.as_user(self.student).get(r.data['url']).status_code, 404)
        self.post(f'sheets/{sheet["id"]}/publish/')
        self.assertEqual(self.as_user(self.student).get(r.data['url']).status_code, 200)
        self.assertEqual(self.as_user(self.outsider).get(r.data['url']).status_code, 404)
        for upload in [SimpleUploadedFile('x.svg', b'<svg></svg>'), SimpleUploadedFile('x.png', b'not an image')]:
            self.assertEqual(self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': upload, 'caption': 'X'}, format='multipart').status_code, 400)
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': SimpleUploadedFile('a.png', png_bytes()), 'caption': ' '}, format='multipart').status_code, 400)

    @mock.patch('revisions.ai.jobs.hf_illustration', return_value=(png_bytes((512, 512)), 'flux-test', 900))
    def test_generate_illustration_caption_and_reorder(self, hf):
        sheet = self.create()
        r = self.post(f'sheets/{sheet["id"]}/illustrations/generate/', {'prompt': 'Une feuille au soleil', 'caption': 'Feuille et lumière', 'style': 'FLAT'})
        self.assertEqual(r.status_code, 202, r.data); hf.assert_called_once_with('Une feuille au soleil', 'FLAT')
        self.assertEqual((r.data['status'], r.data['engine'], r.data['model']), ('SUCCEEDED', 'huggingface', 'flux-test'))
        r.data = r.data['illustration']
        self.assertEqual((r.data['source'], r.data['ai_model'], r.data['prompt']), ('AI', 'flux-test', 'Une feuille au soleil'))
        second = self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': SimpleUploadedFile('b.png', png_bytes()), 'caption': 'Deux'}, format='multipart').data
        self.assertEqual(second['position'], 2)
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/illustrations/generate/', {'prompt': 'x', 'caption': 'y', 'style': 'CUBISM'}).status_code, 400)
        r = self.post(f'sheets/{sheet["id"]}/illustrations/reorder/', {'illustration_ids': [second['id'], r.data['id']]})
        self.assertEqual([i['caption'] for i in r.data['results']], ['Deux', 'Feuille et lumière'])
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/illustrations/reorder/', {'illustration_ids': [second['id']]}).status_code, 400)
        r = self.client.patch(f'/api/sheets/{sheet["id"]}/illustrations/{second["id"]}/', {'caption': 'Nouvelle légende'}, format='json')
        self.assertEqual(r.data['caption'], 'Nouvelle légende')
        self.assertEqual(self.client.delete(f'/api/sheets/{sheet["id"]}/illustrations/{second["id"]}/').status_code, 204)
        self.assertEqual(self.client.get(f'/api/sheets/{sheet["id"]}/').data['illustration_count'], 1)
        other_sheet = self.create(title='Autre')
        self.assertEqual(self.client.delete(f'/api/sheets/{other_sheet["id"]}/illustrations/{r.data["id"]}/').status_code, 404)

    def test_illustration_limit(self):
        sheet = self.create(); rs = RevisionSheet.objects.get(pk=sheet['id'])
        for position in range(1, 13):
            Illustration.objects.create(sheet=rs, image='illustrations/x.webp', caption='c', width=1, height=1, position=position)
        r = self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': SimpleUploadedFile('a.png', png_bytes()), 'caption': 'Trop'}, format='multipart')
        self.assertEqual(r.status_code, 400)

    # --- Organisation, duplication and export ---------------------------------------

    def test_filters_sort_pinned_and_facets(self):
        a = self.create(title='Alpha', course_label='Chimie', tags=['atomes'])
        self.create(title='Bêta', course_label='Biologie végétale', tags=['bio'])
        c = self.create(title='Gamma', tags=['bio', 'cellule'])
        self.client.patch(f'/api/sheets/{c["id"]}/', {'pinned': True}, format='json')
        titles = lambda q: [s['title'] for s in self.client.get('/api/sheets/?' + q).data['results']]
        self.assertEqual(titles('sort=title'), ['Gamma', 'Alpha', 'Bêta'])
        self.assertEqual(titles('tag=bio&sort=title'), ['Gamma', 'Bêta'])
        self.assertEqual(titles('course=Chimie'), ['Alpha'])
        self.assertEqual(titles('q=chim'), ['Alpha'])
        self.assertEqual(titles('scope=pinned'), ['Gamma'])
        self.post(f'sheets/{a["id"]}/archive/')
        self.assertEqual(titles('status=ARCHIVED'), ['Alpha'])
        self.assertEqual(self.client.get('/api/sheets/?status=WRONG').status_code, 400)
        facets = self.client.get('/api/sheets/facets/').data
        self.assertEqual(facets['courses'], ['Biologie végétale', 'Chimie'])
        self.assertEqual(facets['tags'][0], {'name': 'bio', 'count': 2})

    def test_duplicate_for_teacher_and_student(self):
        sheet = self.create()
        self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': SimpleUploadedFile('a.png', png_bytes()), 'caption': 'Figure'}, format='multipart')
        copy = self.post(f'sheets/{sheet["id"]}/duplicate/').data
        self.assertEqual((copy['title'], copy['status'], copy['illustration_count']), ('La photosynthèse (copie)', 'DRAFT', 1))
        self.assertNotEqual(Illustration.objects.get(sheet_id=copy['id']).image.name, Illustration.objects.get(sheet_id=sheet['id']).image.name)
        self.post(f'sheets/{sheet["id"]}/publish/')
        student = self.as_user(self.student)
        mine = self.post(f'sheets/{sheet["id"]}/duplicate/', client=student)
        self.assertEqual(mine.status_code, 201, mine.data)
        self.assertTrue(mine.data['personal']); self.assertEqual(mine.data['owner_id'], str(self.student.pk)); self.assertTrue(mine.data['can_edit'])
        self.assertEqual(student.patch(f'/api/sheets/{mine.data["id"]}/', {'title': 'Ma version'}, format='json').status_code, 200)

    def test_markdown_export(self):
        sheet = self.create(glossary=[{'term': 'ATP', 'definition': 'Molécule énergétique.'}])
        r = self.client.get(f'/api/sheets/{sheet["id"]}/export/')
        self.assertEqual(r.status_code, 200); self.assertEqual(r['Content-Type'], 'text/markdown; charset=utf-8')
        self.assertIn('attachment; filename="fiche-la-photosynthese.md"', r['Content-Disposition'])
        body = r.content.decode()
        for expected in ['# La photosynthèse', '### Introduction', '**Cours :** Biologie végétale', '## Points clés', '1. La lumière est convertie en énergie.', '- **ATP** — Molécule énergétique.', '`#bio`']:
            self.assertIn(expected, body)

    # --- Management back-office ----------------------------------------------

    def test_bulk_actions_report_each_sheet(self):
        ready, blocked, foreign = self.create(), self.create(summary='Court', key_points=[]), self.create(client=self.as_user(self.other), learning_group_id=str(self.other_group.pk))
        r = self.post('sheets/bulk/', {'action': 'publish', 'ids': [ready['id'], blocked['id'], foreign['id']]})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['done'], [ready['id']])
        reasons = {f['id']: f for f in r.data['failed']}
        self.assertEqual(reasons[blocked['id']]['title'], 'La photosynthèse')
        self.assertEqual(reasons[foreign['id']]['title'], '')
        self.assertEqual(RevisionSheet.objects.get(pk=foreign['id']).status, 'DRAFT')
        r = self.post('sheets/bulk/', {'action': 'delete', 'ids': [ready['id'], blocked['id']]})
        self.assertEqual(r.data['done'], [blocked['id']]); self.assertIn('publication', r.data['failed'][0]['reason'])
        self.assertTrue(RevisionSheet.objects.filter(pk=ready['id']).exists())
        self.assertEqual(self.post('sheets/bulk/', {'action': 'archive', 'ids': [ready['id']]}).data['done'], [ready['id']])
        for body in [{'action': 'publish', 'ids': []}, {'action': 'explode', 'ids': [ready['id']]}, {'action': 'archive', 'ids': ['x']}]:
            self.assertEqual(self.post('sheets/bulk/', body).status_code, 400)

    def test_illustration_library_is_scoped(self):
        sheet = self.create()
        self.post(f'sheets/{sheet["id"]}/illustrations/', {'image': SimpleUploadedFile('a.png', png_bytes()), 'caption': 'Cycle de Calvin'}, format='multipart')
        r = self.client.get('/api/revisions/illustrations/')
        self.assertEqual((r.data['count'], r.data['stats']), (1, {'total': 1, 'AI': 0, 'UPLOAD': 1}))
        self.assertEqual((r.data['results'][0]['sheet_title'], r.data['results'][0]['sheet_status']), ('La photosynthèse', 'DRAFT'))
        self.assertEqual(self.client.get('/api/revisions/illustrations/?source=AI').data['count'], 0)
        self.assertEqual(self.client.get('/api/revisions/illustrations/?q=calvin').data['count'], 1)
        self.assertEqual(self.client.get('/api/revisions/illustrations/?source=X').status_code, 400)
        self.assertEqual(self.as_user(self.other).get('/api/revisions/illustrations/').data['count'], 0)
        self.assertEqual(self.as_user(self.admin).get('/api/revisions/illustrations/').data['count'], 1)

    @mock.patch('revisions.ai.jobs.generate_summary', return_value=dict(GENERATED))
    def test_overview_and_job_journal(self, gemini):
        sheet = self.create(summary='', key_points=[])
        self.generate(sheet['id'], {'source_text': 'La chlorophylle capte la lumière. ' * 10, 'length': 'SHORT'})
        ready = self.create(title='Prête')
        data = self.client.get('/api/revisions/overview/').data
        self.assertEqual((data['stats']['total'], data['to_review_count']), (2, 1))
        self.assertEqual(data['to_review'][0]['id'], sheet['id'])
        self.assertEqual([s['id'] for s in data['ready_to_publish']], [ready['id']])
        self.assertEqual(len(data['recent_jobs']), 1)
        self.assertEqual(self.as_user(self.other).get('/api/revisions/overview/').data['stats']['total'], 0)
        journal = self.client.get('/api/ai/jobs/').data
        self.assertEqual((journal['count'], journal['results'][0]['status']), (1, 'SUCCEEDED'))
        self.assertEqual(self.client.get('/api/ai/jobs/?kind=ILLUSTRATION').data['count'], 0)
        self.assertEqual(self.client.get('/api/ai/jobs/?status=NOPE').status_code, 400)
        self.assertEqual(self.as_user(self.other).get('/api/ai/jobs/').data['count'], 0)
        self.assertEqual(self.as_user(self.admin).get('/api/ai/jobs/').data['results'][0]['user_name'], 'Amel Prof')

    # --- Revision and follow-up ----------------------------------------------

    def test_flashcards_progress_and_engagement(self):
        sheet = self.create(glossary=[{'term': 'ATP', 'definition': 'Molécule énergétique.'}], key_points=['Un', 'Deux'])
        self.post(f'sheets/{sheet["id"]}/publish/')
        student = self.as_user(self.student)
        data = student.get(f'/api/sheets/{sheet["id"]}/cards/').data
        self.assertEqual((len(data['cards']), data['tracked'], data['progress']['mastery']), (3, True, 0.0))
        self.assertEqual(data['cards'][0]['kind'], 'TERM')
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/read/', client=student).data['views'], 1)
        ids = [c['id'] for c in data['cards']]
        r = self.post(f'sheets/{sheet["id"]}/review/', {'known': [ids[0], ids[1], 'g:inconnu']}, client=student)
        self.assertEqual((r.data['saved'], r.data['known'], r.data['mastery']), (True, ids[:2], 0.667))
        # Reordering the sheet keeps the mastery of each card.
        self.client.post(f'/api/sheets/{sheet["id"]}/unpublish/', {}, format='json')
        self.client.patch(f'/api/sheets/{sheet["id"]}/', {'key_points': ['Deux', 'Un']}, format='json')
        self.post(f'sheets/{sheet["id"]}/publish/')
        self.assertEqual(student.get(f'/api/sheets/{sheet["id"]}/cards/').data['progress']['mastery'], 0.667)
        # The teacher trains without recording anything, and follows the group.
        self.assertFalse(self.post(f'sheets/{sheet["id"]}/review/', {'known': ids}).data['saved'])
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/read/').status_code, 204)
        rows = self.client.get('/api/revisions/engagement/').data['results']
        self.assertEqual((rows[0]['students'], rows[0]['readers'], rows[0]['average_mastery']), (1, 1, 0.667))
        self.assertEqual(rows[0]['details'][0]['views'], 1)
        self.assertEqual(student.get('/api/revisions/engagement/').status_code, 404)
        self.assertEqual(self.as_user(self.other).get('/api/revisions/engagement/').data['results'], [])
        self.assertEqual(self.as_user(self.outsider).get(f'/api/sheets/{sheet["id"]}/cards/').status_code, 404)
        self.assertEqual(self.post(f'sheets/{sheet["id"]}/review/', {'known': 'x'}, client=student).status_code, 400)

    def test_health_endpoint(self):
        r = APIClient().get('/api/health/')
        self.assertEqual((r.status_code, r.json()), (200, {'status': 'ok', 'database': 'ok'}))
