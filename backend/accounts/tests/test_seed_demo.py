import shutil
import tempfile
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, override_settings
from accounts.models import User
from attendance.models import AttendanceSheet, LearningSession
from quizzes.models import Attempt, Quiz
from revisions.models import Illustration, RevisionSheet

MEDIA = tempfile.mkdtemp(prefix='nexora-seed-')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], MEDIA_ROOT=MEDIA)
class SeedDemoTests(TransactionTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass(); shutil.rmtree(MEDIA, ignore_errors=True)

    def test_seed_is_complete_and_idempotent(self):
        out = StringIO()
        call_command('seed_demo', password='Demo-Seed-Password-42', stdout=out)
        self.assertEqual(User.objects.filter(email__endswith='@demo.nexora.test').count(), 8)
        self.assertTrue(User.objects.get(email='etudiant@demo.nexora.test').check_password('Demo-Seed-Password-42'))
        self.assertEqual((LearningSession.objects.count(), AttendanceSheet.objects.filter(validated=True).count()), (9, 5))
        self.assertEqual(set(Quiz.objects.values_list('status', flat=True)), {'DRAFT', 'PUBLISHED', 'ARCHIVED'})
        self.assertEqual(Attempt.objects.filter(status='SUBMITTED').count(), 4)
        self.assertEqual(RevisionSheet.objects.count(), 8); self.assertEqual(Illustration.objects.count(), 4)
        self.assertIn('Mot de passe commun : Demo-Seed-Password-42', out.getvalue())
        call_command('seed_demo', password='Demo-Seed-Password-42', stdout=StringIO())
        self.assertEqual((LearningSession.objects.count(), Quiz.objects.count(), Attempt.objects.count(), RevisionSheet.objects.count()), (9, 4, 4, 8))

    def test_existing_real_admin_is_untouched_and_weak_password_refused(self):
        admin = User.objects.create_superuser('direction@ecole.test', 'Un-Mot-De-Passe-Fort-1')
        call_command('seed_demo', password='Demo-Seed-Password-42', stdout=StringIO())
        admin.refresh_from_db(); self.assertTrue(admin.check_password('Un-Mot-De-Passe-Fort-1'))
        self.assertFalse(User.objects.filter(email='admin@demo.nexora.test').exists())
        with self.assertRaises(CommandError): call_command('seed_demo', password='123', stdout=StringIO())
