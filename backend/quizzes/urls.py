from django.urls import path
from . import views as v
from . import attempt_views as a
from . import result_views as r
urlpatterns = [
    path('quizzes/', v.QuizzesView.as_view()),
    path('quizzes/results/', r.ResultsListView.as_view()),
    path('quizzes/results/<str:attempt_id>/', r.ResultDetailView.as_view()),
    path('quizzes/<str:uid>/', v.QuizDetailView.as_view()),
    path('quizzes/<str:uid>/results/', r.ResultsListView.as_view()),
    path('quizzes/<str:uid>/questions/', v.QuestionsView.as_view()),
    path('quizzes/<str:uid>/questions/<str:question_id>/', v.QuestionDetailView.as_view()),
    path('quizzes/<str:uid>/reorder/', v.ReorderView.as_view()),
    path('quizzes/<str:uid>/preview/', v.PreviewView.as_view()),
    path('quizzes/<str:uid>/publish/', v.PublishView.as_view()),
    path('quizzes/<str:uid>/archive/', v.ArchiveView.as_view()),
    path('quizzes/<str:uid>/duplicate/', v.DuplicateView.as_view()),
    path('student/quizzes/', v.StudentQuizzesView.as_view()),
    path('student/quizzes/<str:uid>/', v.StudentQuizDetailView.as_view()),
    path('student/quizzes/<str:uid>/attempts/', a.QuizAttemptsView.as_view()),
    path('student/attempts/', a.StudentAttemptsListView.as_view()),
    path('student/attempts/<str:attempt_id>/', a.AttemptDetailView.as_view()),
    path('student/attempts/<str:attempt_id>/answers/<str:question_id>/', a.SaveAnswerView.as_view()),
    path('student/attempts/<str:attempt_id>/submit/', a.SubmitAttemptView.as_view()),
    path('student/attempts/<str:attempt_id>/result/', a.AttemptResultView.as_view()),
]
