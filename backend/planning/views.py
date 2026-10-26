from django.http import HttpResponse
from rest_framework.response import Response
from accounts.views import SecureView, validated
from classrooms.services import paginated
from .generation import generate_plan, planning_context
from .ics import calendar
from .models import StudyGoal, Deadline, Availability, StudyPlan, RevisionTask
from .permissions import PlanningStudent
from .serializers import (GenerateSerializer, PlanUpdateSerializer, EmptyActionSerializer, goals_data, deadlines_data,
    slot_data, tasks_data, plan_item, plan_detail, objects_by_id)
from .services import (own, goal_values, deadline_values, slot_values, task_values, writable, model_errors, goal_minutes,
    student_goals, student_deadlines, filtered_plans, current_groups, activate_plan, archive_plan, delete_plan, delete_goal,
    delete_deadline, plan_tasks, dashboard_data)


class StudentPlanningView(SecureView):
    permission_classes = [PlanningStudent]


def own_goal(request, uid): return own(StudyGoal, request.user, uid, 'Objectif introuvable.')
def own_deadline(request, uid): return own(Deadline, request.user, uid, 'Échéance introuvable.')
def own_slot(request, uid): return own(Availability, request.user, uid, 'Créneau introuvable.')
def own_plan(request, uid): return own(StudyPlan, request.user, uid, 'Planning introuvable.')
def own_task(request, uid): return own(RevisionTask, request.user, uid, 'Tâche introuvable.')
def goal_response(request, goal): return goals_data([goal], goal_minutes(request.user))[0]


class GoalsView(StudentPlanningView):
    def get(self, request):
        return Response({'results': goals_data(student_goals(request), goal_minutes(request.user))})
    def post(self, request):
        goal = goal_values(request.user, request.data); goal.save()
        return Response(goal_response(request, goal), status=201)

class GoalDetailView(StudentPlanningView):
    def get(self, request, uid):
        return Response(goal_response(request, own_goal(request, uid)))
    def patch(self, request, uid):
        goal = goal_values(request.user, request.data, own_goal(request, uid)); goal.save()
        return Response(goal_response(request, goal))
    def delete(self, request, uid):
        delete_goal(own_goal(request, uid))
        return Response(status=204)


class DeadlinesView(StudentPlanningView):
    def get(self, request):
        return Response({'results': deadlines_data(student_deadlines(request))})
    def post(self, request):
        deadline = deadline_values(request.user, request.data); deadline.save()
        return Response(deadlines_data([deadline])[0], status=201)

class DeadlineDetailView(StudentPlanningView):
    def get(self, request, uid):
        return Response(deadlines_data([own_deadline(request, uid)])[0])
    def patch(self, request, uid):
        deadline = deadline_values(request.user, request.data, own_deadline(request, uid)); deadline.save()
        return Response(deadlines_data([deadline])[0])
    def delete(self, request, uid):
        delete_deadline(own_deadline(request, uid))
        return Response(status=204)


class AvailabilityView(StudentPlanningView):
    def get(self, request):
        slots = list(Availability.objects.filter(student=request.user).order_by('weekday', 'start_time', 'id'))
        return Response({'results': [slot_data(s) for s in slots], 'weekly_minutes': sum(s.minutes for s in slots)})
    def post(self, request):
        slot = slot_values(request.user, request.data); slot.save()
        return Response(slot_data(slot), status=201)

class AvailabilityDetailView(StudentPlanningView):
    def patch(self, request, uid):
        slot = slot_values(request.user, request.data, own_slot(request, uid)); slot.save()
        return Response(slot_data(slot))
    def delete(self, request, uid):
        own_slot(request, uid).delete()
        return Response(status=204)


class StudentGroupsView(StudentPlanningView):
    def get(self, request):
        return Response({'results': [{'id': str(g.pk), 'name': g.name, 'code': g.code} for g in current_groups(request.user)]})


class PlanningContextView(StudentPlanningView):
    def get(self, request):
        return Response(planning_context(request.user))


class PlansView(StudentPlanningView):
    def get(self, request):
        return Response(paginated(request, filtered_plans(request), plan_item))

class GeneratePlanView(StudentPlanningView):
    def post(self, request):
        plan = generate_plan(request, validated(GenerateSerializer, request))
        return Response(plan_detail(plan), status=201)

class PlanDetailView(StudentPlanningView):
    def get(self, request, uid):
        return Response(plan_detail(own_plan(request, uid)))
    def patch(self, request, uid):
        plan = own_plan(request, uid); writable(plan)
        plan.title = validated(PlanUpdateSerializer, request)['title']
        model_errors(plan); plan.save(update_fields=['title', 'updated_at'])
        return Response(plan_detail(plan))
    def delete(self, request, uid):
        delete_plan(own_plan(request, uid))
        return Response(status=204)

class ActivatePlanView(StudentPlanningView):
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        plan = own_plan(request, uid); activate_plan(plan)
        return Response(plan_detail(plan))

class ArchivePlanView(StudentPlanningView):
    def post(self, request, uid):
        validated(EmptyActionSerializer, request)
        plan = own_plan(request, uid); archive_plan(plan)
        return Response(plan_detail(plan))

class PlanCalendarView(StudentPlanningView):
    def perform_content_negotiation(self, request, force=False):
        # Calendar clients may only accept text/calendar; errors still fall back to JSON.
        return super().perform_content_negotiation(request, force=True)
    def get(self, request, uid):
        plan = own_plan(request, uid)
        tasks = plan_tasks(plan)
        goals = objects_by_id(StudyGoal, [t.goal_id for t in tasks])
        deadlines = objects_by_id(Deadline, [t.deadline_id for t in tasks])
        response = HttpResponse(calendar(plan, tasks, goals, deadlines), content_type='text/calendar; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="planning-{plan.pk}.ics"'
        return response


class PlanTasksView(StudentPlanningView):
    def post(self, request, uid):
        plan = own_plan(request, uid)
        task = task_values(request.user, plan, request.data); task.save()
        return Response(tasks_data([task])[0], status=201)

class TaskDetailView(StudentPlanningView):
    def patch(self, request, uid):
        task = own_task(request, uid)
        task = task_values(request.user, task.plan, request.data, task); task.save()
        return Response(tasks_data([task])[0])
    def delete(self, request, uid):
        task = own_task(request, uid); writable(task.plan)
        task.delete()
        return Response(status=204)


class DashboardView(StudentPlanningView):
    def get(self, request):
        return Response(dashboard_data(request.user))
