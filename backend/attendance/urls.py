from django.urls import path
from .views import SessionsView, SessionDetailView, SheetView, StatisticsView, ExportView
urlpatterns = [path('sessions/',SessionsView.as_view()), path('sessions/<str:uid>/',SessionDetailView.as_view()),
    path('sessions/<str:uid>/sheet/',SheetView.as_view()),path('statistics/',StatisticsView.as_view()),path('statistics/export/',ExportView.as_view())]
