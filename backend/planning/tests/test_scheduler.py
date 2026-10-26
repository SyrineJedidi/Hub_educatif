from datetime import timedelta, timezone as dt_timezone
from accounts.models import RateBucket
from planning import scheduler
from planning.generation import planner_inputs
from planning.models import StudyPlan, RevisionTask, LOCAL_TZ
from planning.services import availability_windows, next_quarter
from .base import PlanningTestCase, at


class SchedulerTests(PlanningTestCase):
    def setUp(self):
        super().setUp()
        self.monday = self.today + timedelta(days=(7 - self.today.weekday()) % 7 or 7)

    def rules(self, start=None, days=7, now=None):
        start = start or self.monday
        inputs = planner_inputs(self.student, start, start + timedelta(days=days - 1), now or at(start - timedelta(days=1), 12))
        return scheduler.rule_plan(inputs.goals, inputs.deadlines, inputs.done_minutes, inputs.weak_groups, inputs.windows, inputs.start_date, inputs.end_date)

    def layout(self, tasks):
        return [(t['title'], t['starts_at'].astimezone(LOCAL_TZ).strftime('%a %H:%M'), int((t['ends_at'] - t['starts_at']).total_seconds() // 60)) for t in tasks]


    def test_windows_are_local_and_cut_when_started(self):
        self.slot(0, '09:00', '11:00'); self.slot(0, '14:00', '15:00'); self.slot(2, '18:00', '19:30'); self.slot(3, '08:00', '09:00', self.other)
        end = self.monday + timedelta(days=6)
        windows = availability_windows(self.student, self.monday, end, now=at(self.monday - timedelta(days=1), 12))
        self.assertEqual(windows, [(at(self.monday, 9), at(self.monday, 11)), (at(self.monday, 14), at(self.monday, 15)),
            (at(self.monday + timedelta(days=2), 18), at(self.monday + timedelta(days=2), 19, 30))])
        # Africa/Tunis is UTC+1: 09:00 local is 08:00 UTC.
        self.assertEqual(windows[0][0].astimezone(dt_timezone.utc).hour, 8)
        cut = availability_windows(self.student, self.monday, end, now=at(self.monday, 9, 7))
        self.assertEqual(cut[0], (at(self.monday, 9, 15), at(self.monday, 11)))
        self.assertEqual(availability_windows(self.student, self.monday, end, now=at(self.monday, 10, 40))[0], (at(self.monday, 10, 45), at(self.monday, 11)))
        self.assertEqual(availability_windows(self.student, self.monday, end, now=at(self.monday, 10, 50))[0], (at(self.monday, 14), at(self.monday, 15)))
        self.assertEqual(availability_windows(self.student, self.monday + timedelta(days=1), self.monday + timedelta(days=1), now=at(self.monday, 12)), [])
        self.assertEqual(next_quarter(at(self.monday, 10)), at(self.monday, 10))
        self.assertEqual(next_quarter(at(self.monday, 10, 1)), at(self.monday, 10, 15))
        self.assertEqual(next_quarter(at(self.monday, 23, 50)), at(self.monday + timedelta(days=1), 0))

    def test_priorities_blocks_and_determinism(self):
        self.slot(0, '09:00', '12:00')
        self.goal(title='Algèbre', priority='LOW', estimated_hours=2, learning_group=self.math)
        self.goal(title='Python', priority='HIGH', estimated_hours=2)
        self.goal(title='Chimie', priority='MEDIUM', estimated_hours=2, learning_group=None)
        tasks, advice = self.rules()
        self.assertEqual(self.layout(tasks), [('Réviser : Python', 'Mon 09:00', 60), ('Réviser : Python', 'Mon 10:00', 60), ('Réviser : Chimie', 'Mon 11:00', 60)])
        self.assertEqual(self.rules(), (tasks, advice))
        self.assertTrue(all(t['source'] == 'RULES' and t['goal_id'] for t in tasks))
        self.assertIn('3 séances de révision prévues, 3 h au total.', advice)
        self.assertIn('• Python — temps planifié : 2 h.', advice)
        self.assertNotIn('insuffisant', advice)

    def test_block_lengths_and_leftovers(self):
        self.slot(0, '09:00', '11:30'); self.slot(1, '09:00', '11:15'); self.slot(2, '09:00', '09:15')
        self.goal(title='Python', estimated_hours=20)
        self.assertEqual([m for _, _, m in self.layout(self.rules()[0])], [60, 60, 30, 60, 60])
        windows = availability_windows(self.student, self.monday, self.monday + timedelta(days=6), now=at(self.monday, 8))
        self.assertIn((at(self.monday + timedelta(days=2), 9), at(self.monday + timedelta(days=2), 9, 15)), windows)

    def test_done_minutes_reduce_demand_and_shrink_the_last_block(self):
        self.every_day('09:00', '12:00')
        goal = self.goal(title='Python', estimated_hours=1)
        active = self.plan(status='ACTIVE', start=self.today - timedelta(days=3), days=3)
        self.task(active, at(self.today - timedelta(days=2), 9), minutes=40, goal=goal, status='DONE')
        self.task(active, at(self.today - timedelta(days=1), 9), minutes=60, goal=goal, status='SKIPPED')
        tasks, advice = self.rules()
        self.assertEqual(self.layout(tasks), [('Réviser : Python', 'Mon 09:00', 30)])
        self.task(active, at(self.today - timedelta(days=1), 11), minutes=20, goal=goal, status='DONE')
        tasks, advice = self.rules()
        self.assertEqual(tasks, []); self.assertIn('déjà couverts', advice)

    def test_weak_quiz_bonus_uses_the_latest_attempt(self):
        self.slot(0, '09:00', '10:00')
        self.goal(title='Python', estimated_hours=2)
        self.goal(title='Statistiques', estimated_hours=2, learning_group=self.math)
        self.assertEqual(self.rules()[0][0]['title'], 'Réviser : Python')
        self.attempt(self.math, earned=4, ended_at=at(self.today, 8) - timedelta(days=5))
        tasks, advice = self.rules()
        self.assertEqual(tasks[0]['title'], 'Réviser : Statistiques')
        self.assertIn('sous 60 %', tasks[0]['description']); self.assertIn('Priorité renforcée pour « Statistiques »', advice)
        self.attempt(self.math, earned=8, ended_at=at(self.today, 8) - timedelta(days=2))
        self.assertEqual(self.rules()[0][0]['title'], 'Réviser : Python')

    def test_deadline_is_respected_and_missing_time_reported(self):
        self.slot(0, '09:00', '12:00')
        goal = self.goal(title='Python', priority='HIGH', estimated_hours=10)
        deadline = self.deadline(title='Partiel', goal=goal, due_at=at(self.monday, 11))
        self.goal(title='Lecture', priority='LOW', estimated_hours=1, learning_group=None)
        tasks, advice = self.rules()
        self.assertEqual(self.layout(tasks), [('Réviser : Python', 'Mon 09:00', 60), ('Réviser : Python', 'Mon 10:00', 60), ('Réviser : Lecture', 'Mon 11:00', 60)])
        self.assertEqual(tasks[0]['deadline_id'], deadline.pk); self.assertIn('« Partiel »', tasks[0]['description'])
        self.assertIn(f'Temps disponible insuffisant pour « Python » avant le {self.monday:%d/%m} : il manque 8 h.', advice)

    def test_deadline_without_goal_and_urgency(self):
        self.slot(0, '09:00', '13:00')
        self.goal(title='Algèbre', priority='HIGH', estimated_hours=10, target_date=self.monday + timedelta(days=20))
        self.deadline(title='Oral d’anglais', kind='OTHER', due_at=at(self.monday + timedelta(days=1), 18))
        tasks, advice = self.rules()
        # MEDIUM (2) + due within three days (3) beats HIGH (3) without urgency.
        self.assertEqual(self.layout(tasks), [('Préparer : Oral d’anglais', 'Mon 09:00', 60), ('Préparer : Oral d’anglais', 'Mon 10:00', 60),
            ('Réviser : Algèbre', 'Mon 11:00', 60), ('Réviser : Algèbre', 'Mon 12:00', 60)])
        self.assertIsNone(tasks[0]['goal_id'])
        self.assertNotIn('insuffisant', advice)

    def test_target_dates_urgency_and_ties(self):
        self.slot(0, '09:00', '10:00')
        self.goal(title='Beta', priority='LOW', estimated_hours=1, target_date=self.monday + timedelta(days=5))
        self.goal(title='Alpha', priority='LOW', estimated_hours=1)
        self.assertEqual(self.rules()[0][0]['title'], 'Réviser : Beta')
        self.goal(title='Gamma', priority='LOW', estimated_hours=1, target_date=self.monday + timedelta(days=2))
        self.assertEqual(self.rules()[0][0]['title'], 'Réviser : Gamma')
        self.goal(title='Delta', priority='HIGH', estimated_hours=1, target_date=self.monday + timedelta(days=40))
        self.goal(title='Epsilon', priority='HIGH', estimated_hours=1, target_date=self.monday + timedelta(days=30))
        self.goal(title='Zeta', priority='HIGH', estimated_hours=1, target_date=self.monday + timedelta(days=30))
        # LOW 1 + due within three days (3) still beats HIGH goals without urgency (3).
        self.assertEqual(self.rules()[0][0]['title'], 'Réviser : Gamma')

    def test_ties_by_due_date_then_title(self):
        self.slot(0, '09:00', '12:00')
        self.goal(title='Zeta', priority='HIGH', estimated_hours=1, target_date=self.monday + timedelta(days=30))
        self.goal(title='Epsilon', priority='HIGH', estimated_hours=1, target_date=self.monday + timedelta(days=30))
        self.goal(title='Delta', priority='HIGH', estimated_hours=1, target_date=self.monday + timedelta(days=40))
        self.assertEqual([t for t, _, _ in self.layout(self.rules()[0])], ['Réviser : Epsilon', 'Réviser : Zeta', 'Réviser : Delta'])

    def test_nothing_fits_before_the_deadlines(self):
        self.slot(0, '09:00', '10:00')
        goal = self.goal(title='Python', estimated_hours=5)
        self.deadline(title='Partiel', goal=goal, due_at=at(self.monday, 8))
        tasks, advice = self.rules()
        self.assertEqual(tasks, [])
        self.assertTrue(advice.startswith('Aucune séance n’a pu être placée avant vos échéances'))
        self.assertIn(f'Temps disponible insuffisant pour « Python » avant le {self.monday:%d/%m} : il manque 5 h.', advice)

    def test_no_availability_advice(self):
        goal = self.goal()
        tasks, advice = scheduler.rule_plan([goal], [], {}, set(), [], self.monday, self.monday)
        self.assertEqual((tasks, advice), ([], 'Aucune disponibilité sur cette période : ajoutez des créneaux pour planifier vos révisions.'))
        self.assertEqual(scheduler.duration(45), '45 min'); self.assertEqual(scheduler.duration(90), '1 h 30'); self.assertEqual(scheduler.duration(120), '2 h')
        self.assertEqual(scheduler.clip('abcdef', 4), 'abc…')

    def test_generation_errors_and_validation(self):
        r = self.generate(); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Ajoutez au moins un objectif en cours ou une échéance avant de générer un planning.')
        self.goal()
        r = self.generate(); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Aucune disponibilité sur cette période : ajoutez des créneaux.')
        self.slot(self.tomorrow.weekday(), '09:00', '10:00')
        r = self.generate(start_date=(self.tomorrow + timedelta(days=1)).isoformat(), end_date=(self.tomorrow + timedelta(days=1)).isoformat())
        self.assertEqual(r.status_code, 400)
        for change in [dict(start_date=(self.today - timedelta(days=1)).isoformat()), dict(end_date=self.today.isoformat()),
                dict(end_date=(self.tomorrow + timedelta(days=28)).isoformat()), dict(mode='magic'), dict(title=' '), dict(student_id='x'), dict(end_date='demain')]:
            r = self.generate(**change); self.assertEqual(r.status_code, 400, (change, r.data))
        r = self.generate(end_date=(self.tomorrow + timedelta(days=28)).isoformat())
        self.assertEqual(r.data['error']['fields']['end_date'], ['Un planning couvre 28 jours au maximum.'])
        self.assertEqual(self.generate(start_date=(self.today - timedelta(days=1)).isoformat()).data['error']['fields']['start_date'],
            ['Choisissez une date de début à partir d’aujourd’hui.'])
        self.assertEqual(StudyPlan.objects.count(), 0)

    def test_rules_generation_creates_a_draft(self):
        self.every_day('18:00', '20:00')
        goal = self.goal(title='Python', estimated_hours=3)
        before = RateBucket.objects.count()
        r = self.generate(end_date=(self.tomorrow + timedelta(days=27)).isoformat())
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['status'], r.data['generator'], r.data['generator_label'], r.data['fallback_reason'], r.data['provider']), ('DRAFT', 'RULES', 'Règles', '', ''))
        self.assertEqual(r.data['title'], f'Planning du {self.tomorrow:%d/%m} au {self.tomorrow + timedelta(days=27):%d/%m}')
        self.assertEqual((r.data['tasks_count'], r.data['planned_minutes'], r.data['done_count']), (3, 180, 0))
        self.assertEqual([t['goal'] for t in r.data['tasks']], [{'id': str(goal.pk), 'title': 'Python'}] * 3)
        self.assertTrue(r.data['advice'])
        self.assertEqual(RevisionTask.objects.filter(plan_id=r.data['id'], source='RULES').count(), 3)
        self.assertEqual(RateBucket.objects.count(), before)
        self.assertEqual(self.generate(title='Semaine de partiels').data['title'], 'Semaine de partiels')
