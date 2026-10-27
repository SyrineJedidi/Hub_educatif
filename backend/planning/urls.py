from django.urls import path
from . import views as v
from . import coach_views as c
urlpatterns = [
    path('student/planning/goals/', v.GoalsView.as_view()),
    path('student/planning/goals/<str:uid>/', v.GoalDetailView.as_view()),
    path('student/planning/deadlines/', v.DeadlinesView.as_view()),
    path('student/planning/deadlines/<str:uid>/', v.DeadlineDetailView.as_view()),
    path('student/planning/availability/', v.AvailabilityView.as_view()),
    path('student/planning/availability/<str:uid>/', v.AvailabilityDetailView.as_view()),
    path('student/planning/groups/', v.StudentGroupsView.as_view()),
    path('student/planning/context/', v.PlanningContextView.as_view()),
    path('student/planning/dashboard/', v.DashboardView.as_view()),
    path('student/planning/plans/', v.PlansView.as_view()),
    path('student/planning/plans/generate/', v.GeneratePlanView.as_view()),
    path('student/planning/plans/<str:uid>/', v.PlanDetailView.as_view()),
    path('student/planning/plans/<str:uid>/activate/', v.ActivatePlanView.as_view()),
    path('student/planning/plans/<str:uid>/archive/', v.ArchivePlanView.as_view()),
    path('student/planning/plans/<str:uid>/ics/', v.PlanCalendarView.as_view()),
    path('student/planning/plans/<str:uid>/tasks/', v.PlanTasksView.as_view()),
    path('student/planning/tasks/<str:uid>/', v.TaskDetailView.as_view()),
    path('planning/students/', c.CoachStudentsView.as_view()),
    path('planning/students/<str:uid>/', c.CoachStudentDetailView.as_view()),
]
