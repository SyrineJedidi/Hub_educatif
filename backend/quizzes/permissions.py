from accounts.permissions import ActiveAccount

class QuizManager(ActiveAccount):
    message = 'La gestion des quiz est réservée aux enseignants et à l’administrateur.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in ('TEACHER', 'ADMIN')

class QuizStudent(ActiveAccount):
    message = 'Cette présentation est réservée aux étudiants.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'STUDENT'
