from datetime import timedelta
from pathlib import Path
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from accounts.models import User
from classrooms.models import Enrollment
from . import tests as fixtures
from .models import Attempt
from .grades import grade_rows, grades_pdf


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GradeTests(TransactionTestCase):
    setUp=fixtures.QuizTests.setUp
    as_user=fixtures.QuizTests.as_user

    def attempt(self,user,status='SUBMITTED',points=0,number=1):
        return Attempt.objects.create(student=user,quiz=self.quiz,learning_group=self.group,quiz_title=self.quiz.title,
            number=number,status=status,points_earned=points,total_points=10,ended_at=timezone.now() if status!='IN_PROGRESS' else None)

    def test_roster_status_zero_best_and_former_members(self):
        current=self.student
        self.attempt(current,points=0)
        unstarted=User.objects.create_user('unstarted@pdf.test','unused')
        Enrollment.objects.create(student=unstarted,group=self.group)
        initial={row['student_id']:row for row in grade_rows(self.quiz)['current']}
        self.assertEqual(initial[str(current.pk)]['points'],0)
        self.assertEqual(initial[str(current.pk)]['percentage'],0)
        self.assertEqual(initial[str(unstarted.pk)]['status'],'NOT_STARTED')
        self.assertIsNone(initial[str(unstarted.pk)]['points'])
        self.attempt(current,points=7,number=2)
        other=User.objects.create_user('ongoing@pdf.test','unused',first_name='Élève',last_name='علي')
        Enrollment.objects.create(student=other,group=self.group);self.attempt(other,'IN_PROGRESS',None)
        self.attempt(self.outsider,points=3)
        rows=grade_rows(self.quiz)
        by_id={r['student_id']:r for r in rows['current']}
        self.assertEqual(by_id[str(current.pk)]['percentage'],70)
        self.assertEqual(by_id[str(current.pk)]['completed_attempts'],2)
        self.assertEqual(by_id[str(other.pk)]['status'],'IN_PROGRESS');self.assertIsNone(by_id[str(other.pk)]['points'])
        self.assertEqual(rows['former'][0]['student_id'],str(self.outsider.pk))

    def test_export_permissions_and_read_only(self):
        attempt=self.attempt(self.student,'IN_PROGRESS',None);attempt.deadline=timezone.now()-timedelta(seconds=1);attempt.save()
        path=f'/api/quizzes/{self.quiz.pk}/grades.pdf'
        for user,status in [(self.other,404),(self.student,403),(self.teacher,200),(self.admin,200)]:
            response=self.as_user(user).get(path);self.assertEqual(response.status_code,status)
            if status==200:self.assertTrue(response.content.startswith(b'%PDF'));self.assertEqual(response['Content-Type'],'application/pdf')
        attempt.refresh_from_db();self.assertEqual(attempt.status,'IN_PROGRESS');self.assertIsNone(attempt.points_earned)

    def test_unicode_multipage_pdf(self):
        rows={'current':[{'name':f'محمد أحمد — Élève Été {i}', 'status':'NOT_STARTED','completed_attempts':0,
                         'points':None,'total':None,'percentage':None} for i in range(110)],'former':[]}
        content=grades_pdf(self.quiz,rows,'fr')
        self.assertTrue(content.startswith(b'%PDF'))
        self.assertGreater(content.count(b'/Type /Page'),2)
        output=Path(__file__).resolve().parents[2]/'.local/grades-visual.pdf';output.parent.mkdir(exist_ok=True);output.write_bytes(content)
        arabic=grades_pdf(self.quiz,rows,'ar');self.assertTrue(arabic.startswith(b'%PDF'))
        output.with_name('grades-arabic-visual.pdf').write_bytes(arabic)
