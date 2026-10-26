from accounts.permissions import ActiveAccount

class PlanningStudent(ActiveAccount):
    message = 'Le planning de révision est réservé aux étudiants.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'STUDENT'

class PlanningCoach(ActiveAccount):
    message = 'Le suivi des révisions est réservé aux enseignants et à l’administrateur.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in ('TEACHER', 'ADMIN')
