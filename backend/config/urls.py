from django.urls import path, include
from accounts import views as v

urlpatterns = [
    path('api/', include('classrooms.urls')),
    path('api/', include('attendance.urls')),
    path('api/', include('quizzes.urls')),
    path('api/', include('planning.urls')),
    path('api/csrf/', v.CSRFView.as_view()),
    path('api/auth/register/', v.RegisterView.as_view()),
    path('api/auth/login/', v.LoginView.as_view()),
    path('api/auth/logout/', v.LogoutView.as_view()),
    path('api/auth/me/', v.MeView.as_view()),
    path('api/auth/password/reset/', v.ResetRequestView.as_view()),
    path('api/auth/password/confirm/', v.ResetConfirmView.as_view()),
    path('api/auth/password/change/', v.ChangePasswordView.as_view()),
    path('api/profile/', v.ProfileView.as_view()),
    path('api/profile/avatar/', v.AvatarView.as_view()),
    path('api/admin/users/', v.UsersView.as_view()),
    path('api/admin/users/<str:uid>/', v.UserDetailView.as_view()),
]

handler400 = 'accounts.errors.bad_request'
handler404 = 'accounts.errors.not_found'
handler500 = 'accounts.errors.server_error'
