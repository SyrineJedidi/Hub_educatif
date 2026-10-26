from datetime import timedelta
from accounts.models import User
from planning.services import streak_days, progress
from .base import PlanningTestCase, at


class DashboardTests(PlanningTestCase):
    def setUp(self):
        super().setUp()
        self.now = at(self.today, 12)
        day = lambda offset: self.today + timedelta(days=offset)
        self.python = self.goal(title='Python')
        self.stats = self.goal(title='Statistiques', learning_group=self.math)
        self.old = self.goal(title='Ancien objectif', status='ACHIEVED')
        self.goal(title='Abandonné sans tâche', status='ABANDONED')
        self.active = self.plan(status='ACTIVE', start=day(-5), days=16)
        task = lambda offset, hour, minutes=60, **kw: self.task(self.active, at(day(offset), hour), minutes, **kw)
        task(-5, 9, goal=self.python, status='DONE', completed_at=at(day(-5), 10))
        task(-3, 9, 45, goal=self.stats, status='DONE', completed_at=at(day(-3), 10))
        task(-2, 9, goal=self.python, status='DONE', completed_at=at(day(-2), 10))
        task(-1, 22, 30, status='DONE', completed_at=at(day(-1), 22, 30))
        task(-1, 9, status='SKIPPED')
        task(-1, 11)
        self.overdue_today = task(0, 9, title='Matin')
        self.afternoon = task(0, 14, goal=self.python, title='Après-midi')
        task(1, 10, 90, title='Demain')
        task(7, 10, title='Dans une semaine')
        task(8, 10, goal=self.old, title='Plus tard')
        # Another plan and another student never change these numbers, except the streak, which counts every DONE task.
        archived = self.plan(status='ARCHIVED', start=day(-6), days=3)
        self.task(archived, at(day(-4), 9), status='DONE')
        foreign = self.plan(student=self.other, status='ACTIVE', start=day(-1), days=3)
        # 00:30 in Tunis is still the previous day in UTC.
        self.task(foreign, at(day(0), 0, 30), status='DONE')
        for offset, title in [(4, 'Projet'), (2, 'Partiel'), (9, 'Oral'), (3, 'Quiz final'), (-1, 'Passé')]:
            self.deadline(title=title, due_at=at(day(offset), 10))

    def test_dashboard_numbers(self):
        with self.frozen(self.now):
            data = self.get('dashboard/').data
            goals = {g['title']: g for g in self.get('goals/').data['results']}
        self.assertEqual(set(data), {'active_plan', 'today', 'upcoming', 'progress', 'streak_days', 'next_deadlines', 'goals'})
        self.assertEqual((data['active_plan']['id'], data['active_plan']['tasks_count'], data['active_plan']['done_count'], data['active_plan']['planned_minutes']),
            (str(self.active.pk), 11, 4, 645))
        self.assertEqual([t['title'] for t in data['today']], ['Matin', 'Après-midi'])
        self.assertEqual([t['title'] for t in data['upcoming']], ['Demain', 'Dans une semaine'])
        self.assertEqual(data['progress'], {'done': 4, 'skipped': 1, 'todo': 4, 'overdue': 2, 'planned_minutes': 645, 'done_minutes': 195, 'completion_rate': 57})
        self.assertEqual(data['streak_days'], 5)
        self.assertEqual([d['title'] for d in data['next_deadlines']], ['Partiel', 'Quiz final', 'Projet'])
        self.assertEqual(data['goals'], [{'id': str(self.python.pk), 'title': 'Python', 'planned_minutes': 180, 'done_minutes': 120},
            {'id': str(self.stats.pk), 'title': 'Statistiques', 'planned_minutes': 45, 'done_minutes': 45},
            {'id': str(self.old.pk), 'title': 'Ancien objectif', 'planned_minutes': 60, 'done_minutes': 0}])
        self.assertEqual((goals['Python']['planned_minutes'], goals['Python']['done_minutes'], goals['Abandonné sans tâche']['planned_minutes']), (180, 120, 0))

    def test_streak_counts_today_once_something_is_done(self):
        with self.frozen(self.now):
            r = self.patch(f'tasks/{self.afternoon.pk}/', {'status': 'DONE'}); self.assertEqual(r.status_code, 200, r.data)
            data = self.get('dashboard/').data
        self.assertEqual(data['streak_days'], 6)
        self.assertEqual((data['progress']['done'], data['progress']['todo'], data['progress']['completion_rate']), (5, 3, 62))
        # A gap breaks the streak, and days are local days, not UTC days.
        self.assertEqual(streak_days(self.student, at(self.today + timedelta(days=2), 8)), 0)
        self.assertEqual(streak_days(self.other, at(self.today + timedelta(days=1), 12)), 1)
        self.assertEqual(streak_days(self.other, at(self.today + timedelta(days=2), 12)), 0)

    def test_empty_dashboard_and_roles(self):
        self.assertEqual(self.get('dashboard/', self.as_user(self.teacher)).status_code, 403)
        lonely = User.objects.create_user('lonely@planning.test', self.password, first_name='Nour', last_name='Ben Ali')
        self.assertEqual(self.get('dashboard/', self.as_user(lonely)).data, {'active_plan': None, 'today': [], 'upcoming': [],
            'progress': {'done': 0, 'skipped': 0, 'todo': 0, 'overdue': 0, 'planned_minutes': 0, 'done_minutes': 0, 'completion_rate': None},
            'streak_days': 0, 'next_deadlines': [], 'goals': []})
        self.assertIsNone(progress([])['completion_rate'])
