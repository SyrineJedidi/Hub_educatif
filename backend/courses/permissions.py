from accounts.permissions import ActiveAccount

class CourseManager(ActiveAccount):
    message = 'La gestion des cours est réservée aux enseignants et à l’administrateur.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in ('TEACHER', 'ADMIN')

class CourseStudent(ActiveAccount):
    message = 'Cet espace est réservé aux étudiants.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'STUDENT'

class CourseReader(ActiveAccount):
    pass
