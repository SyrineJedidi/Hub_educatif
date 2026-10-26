from accounts.permissions import ActiveAccount


class AssistantUser(ActiveAccount):
    message = 'L’assistant pédagogique est réservé aux étudiants et aux enseignants.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in ('STUDENT', 'TEACHER')


class AssistantManager(ActiveAccount):
    message = 'Le suivi de l’assistant est réservé aux enseignants et à l’administrateur.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in ('TEACHER', 'ADMIN')
