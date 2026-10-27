from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from planning.models import StudyGoal, Deadline, Availability, RevisionTask
from .base import PlanningTestCase, API


class ObjectiveTests(PlanningTestCase):
    def goal_data(self, **kwargs):
        data = dict(title='Réussir Python', description='Les bases du langage.', learning_group_id=str(self.group.pk),
            target_date=(self.today + timedelta(days=20)).isoformat(), priority='HIGH', estimated_hours=8)
        data.update(kwargs); return data

    def deadline_data(self, **kwargs):
        data = dict(title='Partiel Python', kind='EXAM', due_at=(timezone.now() + timedelta(days=5)).isoformat())
        data.update(kwargs); return data

    def test_goal_create_defaults_and_shape(self):
        r = self.post('goals/', {'title': 'Lire le cours'}); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['priority'], r.data['estimated_hours'], r.data['status'], r.data['status_label']), ('MEDIUM', 5, 'ACTIVE', 'En cours'))
        self.assertIsNone(r.data['learning_group']); self.assertIsNone(r.data['target_date'])
        self.assertEqual((r.data['planned_minutes'], r.data['done_minutes']), (0, 0))
        r = self.post('goals/', self.goal_data()); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['learning_group'], {'id': str(self.group.pk), 'name': 'Python', 'code': 'PLAN1'})
        self.assertEqual(r.data['priority_label'], 'Haute'); self.assertEqual(r.data['target_date'], (self.today + timedelta(days=20)).isoformat())
        goal = StudyGoal.objects.get(pk=r.data['id']); self.assertEqual(goal.student_id, self.student.pk)
        self.assertEqual(set(r.data), {'id', 'title', 'description', 'learning_group', 'target_date', 'priority', 'priority_label', 'estimated_hours',
            'status', 'status_label', 'planned_minutes', 'done_minutes', 'created_at', 'updated_at'})

    def test_goal_validation(self):
        for change in [dict(title='  '), dict(title='x' * 121), dict(description='x' * 1001), dict(priority='URGENT'), dict(estimated_hours=0),
                dict(estimated_hours=201), dict(estimated_hours=1.5), dict(estimated_hours='1e2'), dict(estimated_hours=True), dict(target_date='26/10/2026'),
                dict(target_date='2026-02-30'), dict(learning_group_id='abc'), dict(status='ACHIEVED'), dict(student_id=str(self.other.pk)), dict(title=12)]:
            r = self.post('goals/', self.goal_data(**change)); self.assertEqual(r.status_code, 400, (change, r.data))
        self.assertEqual(self.post('goals/', []).status_code, 400)
        r = self.post('goals/', self.goal_data(estimated_hours=0))
        self.assertIn('estimated_hours', r.data['error']['fields'])
        self.assertEqual(StudyGoal.objects.count(), 0)

    def test_goal_group_must_be_a_current_enrollment(self):
        foreign = LearningGroup.objects.create(name='Autre', code='PLANX', teacher=self.teacher, level='L1', academic_year='2026')
        archived = LearningGroup.objects.create(name='Ancien', code='PLANA', teacher=self.teacher, level='L1', academic_year='2026', archived=True)
        ended = LearningGroup.objects.create(name='Terminé', code='PLANE', teacher=self.teacher, level='L1', academic_year='2026')
        future = LearningGroup.objects.create(name='Futur', code='PLANF', teacher=self.teacher, level='L1', academic_year='2026')
        now = timezone.now()
        Enrollment.objects.create(student=self.student, group=archived, starts_at=now - timedelta(days=3))
        Enrollment.objects.create(student=self.student, group=ended, starts_at=now - timedelta(days=9), ends_at=now - timedelta(days=1))
        Enrollment.objects.create(student=self.student, group=future, starts_at=now + timedelta(days=3))
        for group in (foreign, archived, ended, future):
            r = self.post('goals/', self.goal_data(learning_group_id=str(group.pk))); self.assertEqual(r.status_code, 400, group.name)
            self.assertIn('learning_group_id', r.data['error']['fields'])
        self.assertEqual(self.post('goals/', self.goal_data(learning_group_id='0' * 24)).status_code, 400)
        groups = self.get('groups/').data['results']
        self.assertEqual(groups, [{'id': str(self.math.pk), 'name': 'Mathématiques', 'code': 'PLAN2'}, {'id': str(self.group.pk), 'name': 'Python', 'code': 'PLAN1'}])
        # An unchanged group survives the end of the enrollment; changing it is checked again.
        goal = self.goal(learning_group=ended)
        r = self.patch(f'goals/{goal.pk}/', {'learning_group_id': str(ended.pk), 'title': 'Nouveau titre'}); self.assertEqual(r.status_code, 200, r.data)
        r = self.patch(f'goals/{goal.pk}/', {'learning_group_id': str(foreign.pk)}); self.assertEqual(r.status_code, 400)
        r = self.patch(f'goals/{goal.pk}/', {'learning_group_id': None}); self.assertEqual(r.status_code, 200, r.data); self.assertIsNone(r.data['learning_group'])

    def test_goal_patch_status_filter_and_delete(self):
        goal = self.goal()
        r = self.patch(f'goals/{goal.pk}/', {'status': 'ACHIEVED', 'priority': 'LOW'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['status'], r.data['priority']), ('ACHIEVED', 'LOW'))
        self.assertEqual(self.patch(f'goals/{goal.pk}/', {'status': 'DONE'}).status_code, 400)
        self.assertEqual(self.patch(f'goals/{goal.pk}/', {'title': ' '}).status_code, 400)
        self.goal(title='Autre objectif')
        self.assertEqual(len(self.get('goals/').data['results']), 2)
        self.assertEqual([g['title'] for g in self.get('goals/?status=ACTIVE').data['results']], ['Autre objectif'])
        self.assertEqual(self.get('goals/?status=WRONG').status_code, 400)
        deadline = self.deadline(goal=goal)
        self.assertEqual(self.delete(f'goals/{goal.pk}/').status_code, 204)
        self.assertFalse(StudyGoal.objects.filter(pk=goal.pk).exists())
        deadline.refresh_from_db(); self.assertIsNone(deadline.goal_id)

    def test_goal_used_by_tasks_cannot_be_deleted(self):
        goal = self.goal(); plan = self.plan()
        self.task(plan, timezone.now() + timedelta(days=1), goal=goal)
        r = self.delete(f'goals/{goal.pk}/'); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Cet objectif est utilisé par des tâches : marquez-le « Abandonné » plutôt que de le supprimer.')
        self.assertTrue(StudyGoal.objects.filter(pk=goal.pk).exists())

    def test_deadline_crud_and_rules(self):
        goal = self.goal()
        r = self.post('deadlines/', self.deadline_data(goal_id=str(goal.pk), notes='Chapitres 1 à 3')); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['goal'], {'id': str(goal.pk), 'title': goal.title}); self.assertEqual(r.data['kind_label'], 'Examen')
        self.assertEqual(set(r.data), {'id', 'title', 'kind', 'kind_label', 'due_at', 'goal', 'notes', 'created_at', 'updated_at'})
        uid = r.data['id']
        for change in [dict(due_at=(timezone.now() - timedelta(minutes=1)).isoformat()), dict(due_at='2030-01-01'), dict(due_at='demain'),
                dict(kind='TEST'), dict(title=''), dict(notes='x' * 501), dict(goal_id=str(self.goal(student=self.other).pk)), dict(goal_id='1' * 24)]:
            r = self.post('deadlines/', self.deadline_data(**change)); self.assertEqual(r.status_code, 400, (change, r.data))
        r = self.post('deadlines/', self.deadline_data(due_at=(timezone.now() - timedelta(days=1)).isoformat()))
        self.assertEqual(r.data['error']['fields']['due_at'], ['Choisissez une échéance dans le futur.'])
        # A deadline already passed can still be edited as long as its date does not change.
        past = self.deadline(due_at=timezone.now() - timedelta(days=2))
        r = self.patch(f'deadlines/{past.pk}/', {'title': 'Rattrapage', 'due_at': past.due_at.isoformat()}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.patch(f'deadlines/{past.pk}/', {'due_at': (timezone.now() - timedelta(days=1)).isoformat()}).status_code, 400)
        r = self.patch(f'deadlines/{uid}/', {'goal_id': None, 'kind': 'QUIZ'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['goal']); self.assertEqual(r.data['kind'], 'QUIZ')
        self.assertEqual([d['title'] for d in self.get('deadlines/').data['results']], ['Rattrapage', 'Partiel Python'])
        self.assertEqual([d['title'] for d in self.get('deadlines/?upcoming=true').data['results']], ['Partiel Python'])
        self.assertEqual(len(self.get('deadlines/?upcoming=false').data['results']), 2)
        self.assertEqual(self.get('deadlines/?upcoming=oui').status_code, 400)
        self.assertEqual(self.get(f'deadlines/{uid}/').data['title'], 'Partiel Python')

    def test_deadline_delete_keeps_tasks(self):
        deadline = self.deadline(); plan = self.plan()
        task = self.task(plan, timezone.now() + timedelta(days=1), deadline=deadline)
        self.assertEqual(self.delete(f'deadlines/{deadline.pk}/').status_code, 204)
        task.refresh_from_db(); self.assertIsNone(task.deadline_id)
        self.assertFalse(Deadline.objects.filter(pk=deadline.pk).exists())

    def test_availability_crud_and_rules(self):
        r = self.post('availability/', {'weekday': 0, 'start_time': '09:00', 'end_time': '11:30'}); self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data, {'id': r.data['id'], 'weekday': 0, 'weekday_label': 'Lundi', 'start_time': '09:00', 'end_time': '11:30', 'minutes': 150})
        uid = r.data['id']
        for data in [dict(weekday=7, start_time='09:00', end_time='10:00'), dict(weekday=-1, start_time='09:00', end_time='10:00'),
                dict(weekday=1, start_time='09:10', end_time='10:00'), dict(weekday=1, start_time='09:00', end_time='09:15'),
                dict(weekday=1, start_time='08:00', end_time='14:15'), dict(weekday=1, start_time='10:00', end_time='09:00'),
                dict(weekday=1, start_time='9h', end_time='10:00'), dict(weekday=1, start_time='24:00', end_time='10:00'),
                dict(weekday=0, start_time='11:00', end_time='12:00'), dict(weekday=0, start_time='08:00', end_time='12:00'), dict(weekday='lundi', start_time='08:00', end_time='09:00')]:
            r = self.post('availability/', data); self.assertEqual(r.status_code, 400, (data, r.data))
        r = self.post('availability/', dict(weekday=0, start_time='10:00', end_time='12:00'))
        self.assertEqual(r.data['error']['fields']['start_time'], ['Ce créneau chevauche un autre créneau du même jour.'])
        # Touching slots are allowed, and the same hours on another day too.
        self.assertEqual(self.post('availability/', dict(weekday=0, start_time='11:30', end_time='12:30')).status_code, 201)
        self.assertEqual(self.post('availability/', dict(weekday=1, start_time='09:00', end_time='15:00')).status_code, 201)
        r = self.patch(f'availability/{uid}/', {'end_time': '11:00'}); self.assertEqual(r.status_code, 200, r.data); self.assertEqual(r.data['minutes'], 120)
        self.assertEqual(self.patch(f'availability/{uid}/', {'end_time': '12:00'}).status_code, 400)
        listing = self.get('availability/').data
        self.assertEqual(listing['weekly_minutes'], 120 + 60 + 360)
        self.assertEqual([(s['weekday'], s['start_time']) for s in listing['results']], [(0, '09:00'), (0, '11:30'), (1, '09:00')])
        self.assertEqual(self.delete(f'availability/{uid}/').status_code, 204)
        self.assertEqual(self.get(f'availability/{uid}/').status_code, 405)

    def test_availability_limit(self):
        for index in range(21): self.slot(index % 7, f'{6 + index // 7 * 2:02d}:00', f'{7 + index // 7 * 2:02d}:00')
        r = self.post('availability/', dict(weekday=0, start_time='20:00', end_time='21:00')); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Vous avez atteint la limite de 21 créneaux hebdomadaires.')
        self.assertEqual(Availability.objects.filter(student=self.student).count(), 21)

    def test_ownership_returns_404(self):
        goal = self.goal(student=self.other); deadline = self.deadline(student=self.other); slot = self.slot(0, '09:00', '10:00', self.other)
        plan = self.plan(student=self.other); task = self.task(plan, timezone.now() + timedelta(days=1))
        for path in [f'goals/{goal.pk}/', f'deadlines/{deadline.pk}/', f'plans/{plan.pk}/', f'plans/{plan.pk}/ics/']:
            self.assertEqual(self.get(path).status_code, 404, path)
        for path in [f'goals/{goal.pk}/', f'deadlines/{deadline.pk}/', f'availability/{slot.pk}/', f'plans/{plan.pk}/', f'tasks/{task.pk}/']:
            self.assertEqual(self.patch(path, {'title': 'Pris'}).status_code, 404, path)
            self.assertEqual(self.delete(path).status_code, 404, path)
        for path in [f'plans/{plan.pk}/activate/', f'plans/{plan.pk}/archive/', f'plans/{plan.pk}/tasks/']:
            self.assertEqual(self.post(path).status_code, 404, path)
        self.assertEqual(self.get('goals/').data['results'], []); self.assertEqual(self.get('plans/').data['count'], 0)
        for path in ['goals/not-an-id/', 'deadlines/123/', f'plans/{"f" * 24}/', 'plans/xyz/ics/']:
            self.assertEqual(self.get(path).status_code, 404, path)
        self.assertEqual(self.patch('tasks/zz/', {}).status_code, 404)
        self.assertTrue(StudyGoal.objects.filter(pk=goal.pk, title='Réussir Python').exists())
        self.assertTrue(RevisionTask.objects.filter(pk=task.pk).exists())

    def test_roles_anonymous_and_inactive(self):
        paths = ['goals/', 'deadlines/', 'availability/', 'groups/', 'context/', 'plans/', 'dashboard/']
        anonymous = APIClient()
        for path in paths:
            self.assertEqual(self.get(path, anonymous).status_code, 401, path)
            self.assertEqual(self.get(path, self.as_user(self.teacher)).status_code, 403, path)
        self.assertEqual(self.post('goals/', {'title': 'X'}, anonymous).status_code, 401)
        teacher = self.post('goals/', {'title': 'X'}, self.as_user(self.teacher))
        self.assertEqual(teacher.status_code, 403); self.assertEqual(teacher.data['error']['message'], 'Le planning de révision est réservé aux étudiants.')
        admin = User.objects.create_superuser('admin@planning.test', self.password)
        self.assertEqual(self.get('goals/', self.as_user(admin)).status_code, 403)
        client = self.as_user(self.student); self.student.is_active = False; self.student.save()
        self.assertEqual(self.get('goals/', client).status_code, 401)
        self.assertEqual(self.post('goals/', {'title': 'X'}, client).status_code, 401)

    def test_csrf_on_student_writes(self):
        client = APIClient(enforce_csrf_checks=True); client.force_login(self.student)
        goal = self.goal(); slot = self.slot(0, '09:00', '10:00'); plan = self.plan()
        for path in ['goals/', 'deadlines/', 'availability/', 'plans/generate/', f'plans/{plan.pk}/activate/', f'plans/{plan.pk}/archive/', f'plans/{plan.pk}/tasks/']:
            self.assertEqual(self.post(path, {}, client).status_code, 403, path)
        for path in [f'goals/{goal.pk}/', f'availability/{slot.pk}/', f'plans/{plan.pk}/']:
            self.assertEqual(self.patch(path, {}, client).status_code, 403, path)
            self.assertEqual(self.delete(path, client).status_code, 403, path)
        r = self.post('goals/', {}, client); self.assertEqual(r.json()['error']['code'], 'csrf_failed')
        token = client.get('/api/csrf/').data['csrfToken']
        r = client.post(API + 'goals/', {'title': 'Avec jeton'}, format='json', HTTP_X_CSRFTOKEN=token); self.assertEqual(r.status_code, 201, r.data)
