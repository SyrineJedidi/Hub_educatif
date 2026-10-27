from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from . import tests as fixtures
from .models import Attempt, QuizFeedback


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FeedbackTests(TransactionTestCase):
    setUp=fixtures.QuizTests.setUp
    as_user=fixtures.QuizTests.as_user

    def finish(self,student=None):
        return Attempt.objects.create(student=student or self.student,quiz=self.quiz,learning_group=self.group,
            quiz_title=self.quiz.title,number=1,status='SUBMITTED',points_earned=3,total_points=5,ended_at=timezone.now())

    def test_only_after_completion_and_unique_update_without_score_changes(self):
        path=f'/api/student/quizzes/{self.quiz.pk}/feedback/';client=self.as_user(self.student)
        self.assertEqual(client.put(path,{'rating':'SUITABLE'},format='json').status_code,400)
        attempt=self.finish()
        for index,rating in enumerate(['SUITABLE','TOO_HARD']):
            response=client.put(path,{'rating':rating,'comment':'<script>alert(1)</script>'},format='json')
            self.assertEqual(response.status_code,201 if index==0 else 200,response.data)
        self.assertEqual(QuizFeedback.objects.count(),1)
        self.assertEqual(client.get(path).data['feedback']['rating'],'TOO_HARD')
        attempt.refresh_from_db();self.assertEqual(attempt.points_earned,3)

    def test_invalid_rating_comment_and_technical_fields_rejected(self):
        self.finish();client=self.as_user(self.student);path=f'/api/student/quizzes/{self.quiz.pk}/feedback/'
        for body in [{'rating':'OTHER'},{'rating':None},{'rating':'SUITABLE','comment':'x'*1001},
                     {'rating':'SUITABLE','student_id':str(self.other.pk)}]:
            self.assertEqual(client.put(path,body,format='json').status_code,400)
        self.assertFalse(QuizFeedback.objects.exists())

    def test_privacy_and_staff_distribution(self):
        self.finish();client=self.as_user(self.student);path=f'/api/student/quizzes/{self.quiz.pk}/feedback/'
        client.put(path,{'rating':'TOO_EASY','comment':'Commentaire privé'},format='json')
        self.assertEqual(self.as_user(self.outsider).get(path).status_code,404)
        staff=f'/api/quizzes/{self.quiz.pk}/feedback/'
        self.assertEqual(client.get(staff).status_code,403)
        self.assertEqual(self.as_user(self.other).get(staff).status_code,404)
        for actor in (self.teacher,self.admin):
            response=self.as_user(actor).get(staff);self.assertEqual(response.status_code,200)
            self.assertEqual(response.data['distribution']['TOO_EASY'],1)
            self.assertEqual(response.data['results'][0]['comment'],'Commentaire privé')

    def test_other_student_cannot_read_or_modify_author_feedback(self):
        self.finish();self.finish(self.outsider)
        from classrooms.models import Enrollment
        Enrollment.objects.create(student=self.outsider,group=self.group)
        path=f'/api/student/quizzes/{self.quiz.pk}/feedback/'
        self.as_user(self.student).put(path,{'rating':'SUITABLE','comment':'Privé'},format='json')
        other=self.as_user(self.outsider);self.assertIsNone(other.get(path).data['feedback'])
        other.put(path,{'rating':'TOO_HARD'},format='json')
        self.assertEqual(QuizFeedback.objects.count(),2)
        self.assertEqual(self.as_user(self.student).get(path).data['feedback']['comment'],'Privé')
