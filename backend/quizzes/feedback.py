from collections import Counter
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from accounts.models import User
from accounts.views import validated
from classrooms.services import get_object, mutation
from .models import Quiz, Attempt, QuizFeedback
from .serializers import QuizInputSerializer, QuizChoiceField, QuizTextField
from .attempt_views import StudentAttemptView
from .result_views import ReadOnlyResultsView
from .services import managed_quiz
from .attempt_services import require_group_access, refresh_expired, expire_if_due


class FeedbackInput(QuizInputSerializer):
    rating = QuizChoiceField(choices=QuizFeedback.Rating.choices)
    comment = QuizTextField(max_length=1000, allow_blank=True, required=False, default='')


def eligible_quiz(request, uid, within_mutation=False):
    quiz = get_object(Quiz, uid)
    require_group_access(request.user, quiz.learning_group)
    attempts = list(Attempt.objects.filter(quiz=quiz, student=request.user))
    if within_mutation:
        for attempt in attempts: expire_if_due(attempt)
    else: refresh_expired(request, attempts)
    if not any(attempt.status in ('SUBMITTED', 'EXPIRED') for attempt in attempts):
        raise ValidationError('Terminez une tentative avant de donner votre appréciation.')
    return quiz


def feedback_data(feedback):
    return {'id': str(feedback.pk), 'rating': feedback.rating, 'comment': feedback.comment, 'updated_at': feedback.updated_at}


class StudentFeedbackView(StudentAttemptView):
    def get(self, request, uid):
        quiz = eligible_quiz(request, uid)
        feedback = QuizFeedback.objects.filter(quiz=quiz, student=request.user).first()
        response=Response({'feedback': feedback_data(feedback) if feedback else None})
        response['Cache-Control']='private, no-store'
        return response
    @mutation
    def put(self, request, uid):
        quiz = eligible_quiz(request, uid, within_mutation=True)
        values = validated(FeedbackInput, request)
        feedback, created = QuizFeedback.objects.update_or_create(quiz=quiz, student=request.user, defaults=values)
        response=Response({'feedback': feedback_data(feedback)},status=201 if created else 200)
        response['Cache-Control']='private, no-store'
        return response


class ManagerFeedbackView(ReadOnlyResultsView):
    def get(self, request, uid):
        quiz=managed_quiz(request.user, uid)
        values=list(QuizFeedback.objects.filter(quiz=quiz).order_by('-updated_at','id'))
        try: page=max(1,int(request.query_params.get('page',1)))
        except ValueError: raise ValidationError({'page':['Page invalide.']})
        current=values[(page-1)*20:page*20]
        students={student.pk:student for student in User.objects.filter(pk__in=[value.student_id for value in current])}
        counts=Counter(value.rating for value in values)
        response=Response({'count':len(values),'page':page,'page_size':20,
            'distribution':{rating:counts[rating] for rating in QuizFeedback.Rating.values},
            'results':[{**feedback_data(value),'student':{'id':str(value.student_id),
                'first_name':students[value.student_id].first_name,'last_name':students[value.student_id].last_name}} for value in current]})
        response['Cache-Control']='private, no-store'
        return response
