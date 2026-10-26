from django.urls import path
from . import views as v
from . import manage_views as m
urlpatterns = [
    path('assistant/scopes/', v.ScopesView.as_view()),
    path('assistant/conversations/', v.ConversationsView.as_view()),
    path('assistant/conversations/<str:uid>/', v.ConversationDetailView.as_view()),
    path('assistant/conversations/<str:uid>/restore/', v.RestoreView.as_view()),
    path('assistant/conversations/<str:uid>/messages/', v.MessagesView.as_view()),
    path('assistant/conversations/<str:uid>/export/', v.ExportView.as_view()),
    path('assistant/messages/<str:uid>/feedback/', v.FeedbackView.as_view()),
    path('assistant/transcriptions/', v.TranscriptionView.as_view()),
    path('assistant/notes/', m.NotesView.as_view()),
    path('assistant/notes/<str:uid>/', m.NoteDetailView.as_view()),
    path('assistant/settings/', m.SettingsListView.as_view()),
    path('assistant/settings/<str:source_type>/<str:scope_id>/', m.SettingsDetailView.as_view()),
    path('assistant/insights/<str:source_type>/<str:scope_id>/', m.InsightsView.as_view()),
    path('assistant/reviews/', m.ReviewsView.as_view()),
    path('assistant/reviews/<str:uid>/', m.ReviewDetailView.as_view()),
    path('assistant/admin/usage/', m.AdminUsageView.as_view()),
]
