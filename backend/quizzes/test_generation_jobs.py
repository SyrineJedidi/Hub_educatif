from datetime import timedelta
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import QuestionGenerationJob
from . import tests as fixtures
from .generation import GenerationError
from .test_generation import proposal

COURSE = {'course_text': 'print affiche du texte.', 'count': 2, 'level': 'EASY'}
Status = QuestionGenerationJob.Status


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], QUIZ_GENERATION_ASYNC=True,
                   AI_JOB_BACKEND='sync', OLLAMA_BASE_URL='http://127.0.0.1:11434', OLLAMA_MODEL='qwen3:8b', OLLAMA_TIMEOUT_SECONDS='180')
class GenerationJobTests(TransactionTestCase):
    """The request returns 202 at once; the generation runs in the background and the page polls the job."""
    def setUp(self):
        fixtures.QuizTests.setUp(self)
    as_user = fixtures.QuizTests.as_user

    def start(self, client=None, data=None):
        return (client or self.client).post(f'/api/quizzes/{self.quiz.pk}/generate-questions/', data or COURSE, format='json')

    def poll(self, job_id, client=None):
        return (client or self.client).get(f'/api/quizzes/{self.quiz.pk}/generate-questions/{job_id}/')

    @patch('quizzes.generation_jobs.generate_questions')
    def test_job_is_accepted_then_delivers_proposals_once(self, generate):
        generate.return_value = [proposal(), {**proposal(), 'statement': 'Que fait len() ?', 'correct_answer': 'B', 'notion': 'Listes'}]
        started = self.start()
        self.assertEqual(started.status_code, 202, started.data)
        self.assertEqual((started.data['status'], 'questions' in started.data), ('SUCCEEDED', False))
        self.assertEqual(started['Cache-Control'], 'private, no-store')
        job = QuestionGenerationJob.objects.get(pk=started.data['id'])
        # The course is not kept, the metrics are.
        self.assertNotIn('course_text', job.inputs)
        self.assertEqual({k: job.metrics[k] for k in ('requested', 'returned', 'distinct_statements', 'answers', 'notions', 'model')},
                         {'requested': 2, 'returned': 2, 'distinct_statements': 2, 'answers': {'A': 1, 'B': 1}, 'notions': 2, 'model': 'qwen3:8b'})
        self.assertGreaterEqual(job.metrics['latency_ms'], 0)
        first = self.poll(job.pk)
        self.assertEqual((first.status_code, len(first.data['questions'])), (200, 2))
        # Handed over once, then forgotten: nothing is kept until the teacher confirms.
        self.assertEqual(QuestionGenerationJob.objects.get(pk=job.pk).proposals, [])
        again = self.poll(job.pk)
        self.assertEqual((again.data['questions'], again.data['delivered']), ([], True))
        self.assertEqual(self.quiz.questions.count(), 0)

    @patch('quizzes.generation_jobs.generate_questions')
    def test_provider_and_validation_errors_are_reported_on_the_job(self, generate):
        generate.side_effect = GenerationError('Le serveur Ollama est arrêté ou inaccessible.', 'ollama_unreachable')
        job_id = self.start().data['id']
        data = self.poll(job_id).data
        self.assertEqual((data['status'], data['error']['code'], data['error']['status']), ('FAILED', 'ollama_unreachable', 503))
        self.assertIn('Ollama', data['error']['message'])
        generate.side_effect = ValidationError({'course_text': ['Le cours est trop long pour ce modèle.']})
        data = self.poll(self.start().data['id']).data
        self.assertEqual((data['error']['status'], data['error']['fields']), (400, {'course_text': ['Le cours est trop long pour ce modèle.']}))
        generate.side_effect = RuntimeError('boom')
        with self.assertLogs('quizzes.generation_jobs', 'ERROR'):
            data = self.poll(self.start().data['id']).data
        self.assertEqual((data['error']['code'], data['error']['message']), ('generation_failed', 'La génération a échoué. Réessayez plus tard.'))

    @patch('quizzes.generation_jobs.generate_questions', return_value=[proposal()])
    def test_only_the_author_can_follow_the_job(self, generate):
        job_id = self.start().data['id']
        self.assertEqual(self.poll(job_id, self.as_user(self.other)).status_code, 404)
        self.assertEqual(self.poll(job_id, self.as_user(self.student)).status_code, 403)
        self.assertEqual(self.poll('not-an-id').status_code, 404)
        self.assertEqual(self.poll(job_id).status_code, 200)

    @patch('quizzes.generation_jobs.generate_questions', return_value=[proposal()])
    def test_invalid_input_is_refused_before_any_job(self, generate):
        self.assertEqual(self.start(data={**COURSE, 'count': 0}).status_code, 400)
        self.assertFalse(QuestionGenerationJob.objects.exists())
        generate.assert_not_called()

    @override_settings(AI_JOB_BACKEND='celery')
    def test_celery_backend_queues_the_task(self):
        with patch('quizzes.tasks.run_question_generation.delay') as delay:
            started = self.start()
        self.assertEqual((started.status_code, started.data['status']), (202, 'QUEUED'))
        delay.assert_called_once_with(started.data['id'])

    def test_abandoned_job_expires_with_a_clear_message(self):
        job = QuestionGenerationJob.objects.create(quiz=self.quiz, teacher=self.teacher, inputs=COURSE, status=Status.RUNNING)
        QuestionGenerationJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(minutes=10))
        data = self.poll(job.pk).data
        self.assertEqual((data['status'], data['error']['code']), ('FAILED', 'generation_expired'))
        self.assertEqual(QuestionGenerationJob.objects.get(pk=job.pk).inputs, {})
