from django.urls import path
from .views import GroupsView, GroupDetailView, EnrollmentsView, EnrollmentDetailView
urlpatterns = [path('groups/', GroupsView.as_view()), path('groups/<str:uid>/', GroupDetailView.as_view()),
               path('enrollments/', EnrollmentsView.as_view()), path('enrollments/<str:uid>/', EnrollmentDetailView.as_view())]
