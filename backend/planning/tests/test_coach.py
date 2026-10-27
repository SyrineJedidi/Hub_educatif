from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import LearningGroup, Enrollment
from planning.models import StudyGoal, Deadline, StudyPlan, RevisionTask
from .base import PlanningTestCase, at

COACH = '/api/planning/students/'


class CoachTests(PlanningTestCase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.colleague = User.objects.create_user('colleague@planning.test', self.password, role='TEACHER', first_name='Karim', last_name='Collègue')
        self.chemistry = LearningGroup.objects.create(name='Chimie', code='PLAN3', teacher=self.colleague, level='L1', academic_year='2026')
        self.old_group = LearningGroup.objects.create(name='Ancien groupe', code='PLAN4', teacher=self.teacher, level='L1', academic_year='2025', archived=True)
        def student(email, first, last, group=None, **period):
            user = User.objects.create_user(email, self.password, first_name=first, last_name=last)
            if group: Enrollment.objects.create(student=user, group=group, **{'starts_at': now - timedelta(days=10), **period})
            return user
        Enrollment.objects.create(student=self.other, group=self.chemistry, starts_at=now - timedelta(days=10))
        Enrollment.objects.create(student=self.student, group=self.chemistry, starts_at=now - timedelta(days=10))
        self.ended = student('ended@planning.test', 'Inès', 'Ancienne', self.group, ends_at=now - timedelta(days=1))
        self.future = student('future@planning.test', 'Omar', 'Futur', self.group, starts_at=now + timedelta(days=2))
        self.archived = student('archived@planning.test', 'Sami', 'Archive', self.old_group)
        self.lonely = student('lonely@planning.test', 'Nour', 'Seule')
        self.admin = User.objects.create_superuser('admin@planning.test', self.password)
        self.coach = self.as_user(self.teacher)
        self.python = self.goal(title='Python', priority='HIGH', description='Notes personnelles')
        self.active = self.plan(status='ACTIVE', start=self.today, advice='Travaillez tôt.')
        self.task(self.active, at(self.today, 9), goal=self.python, status='DONE', completed_at=now - timedelta(hours=2))
        self.task(self.active, at(self.tomorrow, 9), goal=self.python)
        self.deadline(title='Partiel', due_at=now + timedelta(days=3)); self.deadline(title='Passé', due_at=now - timedelta(days=3))

    def names(self, response):
        return [row['student']['last_name'] for row in response.data['results']]

    def test_teacher_sees_current_students_of_active_groups_only(self):
        r = self.coach.get(COACH); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['count'], r.data['page'], r.data['page_size']), (1, 1, 20))
        row = r.data['results'][0]
        self.assertEqual(set(row), {'student', 'groups', 'active_plan', 'progress', 'last_done_at', 'next_deadline'})
        self.assertEqual(row['student'], {'id': str(self.student.pk), 'first_name': 'Élodie', 'last_name': 'Martin'})
        # Only the teacher's own groups are listed, never the email.
        self.assertEqual(row['groups'], [{'id': str(self.math.pk), 'name': 'Mathématiques'}, {'id': str(self.group.pk), 'name': 'Python'}])
        self.assertEqual(row['active_plan'], {'id': str(self.active.pk), 'title': 'Planning test', 'start_date': self.today.isoformat(),
            'end_date': (self.today + timedelta(days=6)).isoformat()})
        self.assertEqual((row['progress']['done'], row['progress']['todo'], row['progress']['planned_minutes']), (1, 1, 120))
        self.assertEqual(row['last_done_at'], RevisionTask.objects.get(status='DONE').completed_at)
        self.assertEqual(row['next_deadline']['title'], 'Partiel')
        self.assertNotIn('student@planning.test', str(r.data))
        self.assertEqual(self.names(self.as_user(self.colleague).get(COACH)), ['Martin', 'Zidane'])

    def test_group_filter_search_and_pagination(self):
        self.assertEqual(self.names(self.coach.get(COACH, {'group': str(self.math.pk)})), ['Martin'])
        for group in (str(self.chemistry.pk), str(self.old_group.pk), 'abc', '0' * 24):
            self.assertEqual(self.coach.get(COACH, {'group': group}).status_code, 404, group)
        admin = self.as_user(self.admin)
        self.assertEqual(self.names(admin.get(COACH, {'group': str(self.chemistry.pk)})), ['Martin', 'Zidane'])
        self.assertEqual(self.names(admin.get(COACH, {'group': str(self.group.pk)})), ['Martin'])
        self.assertEqual(self.names(admin.get(COACH, {'q': 'MART'})), ['Martin'])
        self.assertEqual(self.names(admin.get(COACH, {'q': 'nour seule'})), ['Seule'])
        self.assertEqual(self.names(admin.get(COACH, {'q': 'nour martin'})), [])
        self.assertEqual(self.names(self.coach.get(COACH, {'q': 'zidane'})), [])
        self.assertEqual(self.coach.get(COACH, {'page': 'deux'}).status_code, 400)
        self.assertEqual(self.coach.get(COACH, {'page': '2'}).data['results'], [])

    def test_admin_sees_every_student(self):
        admin = self.as_user(self.admin)
        r = admin.get(COACH)
        self.assertEqual(self.names(r), ['Ancienne', 'Archive', 'Futur', 'Martin', 'Seule', 'Zidane'])
        martin = next(row for row in r.data['results'] if row['student']['last_name'] == 'Martin')
        self.assertEqual([g['name'] for g in martin['groups']], ['Chimie', 'Mathématiques', 'Python'])
        lonely = next(row for row in r.data['results'] if row['student']['last_name'] == 'Seule')
        self.assertEqual((lonely['groups'], lonely['active_plan'], lonely['last_done_at'], lonely['next_deadline']), ([], None, None, None))
        self.assertEqual(admin.get(f'{COACH}{self.lonely.pk}/').status_code, 200)

    def test_student_detail(self):
        r = self.coach.get(f'{COACH}{self.student.pk}/'); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data), {'student', 'groups', 'progress', 'streak_days', 'goals', 'deadlines', 'active_plan'})
        self.assertEqual(r.data['goals'], [{'id': str(self.python.pk), 'title': 'Python', 'priority': 'HIGH', 'priority_label': 'Haute',
            'status': 'ACTIVE', 'status_label': 'En cours', 'planned_minutes': 120, 'done_minutes': 60}])
        self.assertEqual([(d['title'], d['kind_label']) for d in r.data['deadlines']], [('Partiel', 'Examen')])
        self.assertEqual(set(r.data['deadlines'][0]), {'id', 'title', 'kind_label', 'due_at'})
        self.assertEqual((r.data['active_plan']['advice'], len(r.data['active_plan']['tasks'])), ('Travaillez tôt.', 2))
        self.assertEqual(r.data['streak_days'], 1); self.assertEqual(r.data['progress']['completion_rate'], 100)
        self.assertNotIn('Notes personnelles', str(r.data)); self.assertNotIn('student@planning.test', str(r.data))
        other = self.as_user(self.other)
        self.assertIsNone(self.as_user(self.admin).get(f'{COACH}{self.other.pk}/').data['active_plan'])
        self.assertEqual(other.get(f'{COACH}{self.other.pk}/').status_code, 403)

    def test_out_of_scope_students_return_404(self):
        for user in (self.other, self.ended, self.future, self.archived, self.lonely, self.colleague, self.admin):
            r = self.coach.get(f'{COACH}{user.pk}/'); self.assertEqual(r.status_code, 404, user.email)
            self.assertEqual(r.data['error']['code'], 'not_found')
        for uid in ('abc', '0' * 24):
            self.assertEqual(self.coach.get(f'{COACH}{uid}/').status_code, 404)
        self.assertEqual(self.as_user(self.colleague).get(f'{COACH}{self.student.pk}/').status_code, 200)
        self.assertEqual(self.as_user(self.admin).get(f'{COACH}{self.teacher.pk}/').status_code, 404)

    def test_roles_and_read_only(self):
        anonymous = APIClient()
        for path in (COACH, f'{COACH}{self.student.pk}/'):
            self.assertEqual(anonymous.get(path).status_code, 401)
            r = self.client.get(path); self.assertEqual(r.status_code, 403)
            self.assertEqual(r.data['error']['message'], 'Le suivi des révisions est réservé aux enseignants et à l’administrateur.')
        before = [list(model.objects.order_by('id').values()) for model in (StudyGoal, Deadline, StudyPlan, RevisionTask)]
        for client in (self.coach, self.as_user(self.admin)):
            for path in (COACH, f'{COACH}{self.student.pk}/'):
                self.assertEqual(client.post(path, {'title': 'X'}, format='json').status_code, 405)
                self.assertEqual(client.patch(path, {'title': 'X'}, format='json').status_code, 405)
                self.assertEqual(client.delete(path).status_code, 405)
        self.assertEqual([list(model.objects.order_by('id').values()) for model in (StudyGoal, Deadline, StudyPlan, RevisionTask)], before)
        self.teacher.is_active = False; self.teacher.save()
        self.assertEqual(self.coach.get(COACH).status_code, 401)
