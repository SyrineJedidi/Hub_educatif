from rest_framework.authentication import SessionAuthentication as BaseSessionAuthentication
from rest_framework.permissions import BasePermission


class SessionAuthentication(BaseSessionAuthentication):
    def authenticate_header(self, request):
        return 'Session'


class ActiveAccount(BasePermission):
    message = 'Un compte actif est nécessaire.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.is_active)


class Administrator(ActiveAccount):
    message = 'Cette action est réservée aux administrateurs.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'ADMIN'
