from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.db import IntegrityError, connections
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework.test import APIClient
from classrooms.services import Conflict
from planning import ics
from planning.services import activate_plan, archive_plan
from planning.models import StudyGoal, Deadline, StudyPlan, RevisionTask
from .base import PlanningTestCase, API, at

PLAN_KEYS = {'id', 'title', 'start_date', 'end_date', 'status', 'status_label', 'generator', 'generator_label', 'fallback_reason', 'provider',
    'model_name', 'latency_ms', 'prompt_tokens', 'output_tokens', 'tasks_count', 'done_count', 'planned_minutes', 'activated_at', 'created_at', 'updated_at'}
TASK_KEYS = {'id', 'plan_id', 'title', 'description', 'goal', 'deadline', 'starts_at', 'ends_at', 'minutes', 'status', 'status_label', 'source', 'completed_at'}
ARCHIVED = ['Ce planning est archivé.']


class PlanLifecycleTests(PlanningTestCase):
    def test_list_detail_shapes_and_filters(self):
        draft = self.plan(); active = self.plan(status='ACTIVE'); self.plan(status='ARCHIVED')
        self.task(draft, at(self.tomorrow, 9), status='DONE'); self.task(draft, at(self.tomorrow, 10), minutes=30)
        self.plan(student=self.other)
        listing = self.get('plans/').data
        self.assertEqual((listing['count'], listing['page'], listing['page_size']), (3, 1, 20))
        self.assertEqual(set(listing['results'][0]), PLAN_KEYS)
        item = next(p for p in listing['results'] if p['id'] == str(draft.pk))
        self.assertEqual((item['tasks_count'], item['done_count'], item['planned_minutes'], item['status_label'], item['generator']), (2, 1, 90, 'Brouillon', 'RULES'))
        self.assertEqual([p['id'] for p in self.get('plans/?status=ACTIVE').data['results']], [str(active.pk)])
        self.assertEqual(self.get('plans/?status=OLD').status_code, 400)
        self.assertEqual(self.get('plans/?page=x').data['error']['fields'], {'page': ['Page invalide.']})
        self.assertEqual(self.get('plans/?page=2').data['results'], [])
        detail = self.get(f'plans/{draft.pk}/').data
        self.assertEqual(set(detail), PLAN_KEYS | {'advice', 'tasks'})
        self.assertEqual([t['minutes'] for t in detail['tasks']], [60, 30]); self.assertEqual(set(detail['tasks'][0]), TASK_KEYS)

    def test_activate_archives_the_previous_active_plan(self):
        old = self.plan(status='ACTIVE'); draft = self.plan()
        r = self.post(f'plans/{draft.pk}/activate/'); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['status'], r.data['status_label']), ('ACTIVE', 'Actif')); self.assertIsNotNone(r.data['activated_at'])
        old.refresh_from_db(); self.assertEqual(old.status, 'ARCHIVED')
        self.assertEqual(StudyPlan.objects.filter(student=self.student, status='ACTIVE').count(), 1)
        r = self.post(f'plans/{draft.pk}/activate/'); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['fields'], {'status': ['Ce planning est déjà actif.']})
        self.assertEqual(self.post(f'plans/{old.pk}/activate/').data['error']['fields'], {'status': ARCHIVED})
        self.assertEqual(self.post(f'plans/{self.plan().pk}/activate/', {'force': True}).status_code, 400)
        # Another student's active plan is untouched.
        foreign = self.plan(student=self.other, status='ACTIVE')
        self.post(f'plans/{self.plan().pk}/activate/'); foreign.refresh_from_db(); self.assertEqual(foreign.status, 'ACTIVE')

    def test_one_active_plan_per_student_in_the_database(self):
        self.plan(status='ACTIVE')
        with self.assertRaises(IntegrityError): self.plan(status='ACTIVE')
        self.plan(student=self.other, status='ACTIVE')

    def test_concurrent_activations_keep_a_single_active_plan(self):
        first, second = self.plan(), self.plan()
        def activate(plan):
            try:
                client = APIClient(); client.force_login(self.student)
                return client.post(f'{API}plans/{plan.pk}/activate/', {}, format='json').status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(activate, [first, second]))
        self.assertIn(200, statuses); self.assertTrue(set(statuses) <= {200, 409}, statuses)
        self.assertEqual(StudyPlan.objects.filter(student=self.student, status='ACTIVE').count(), 1)

    def test_stale_lifecycle_changes_raise_a_conflict_and_roll_back(self):
        old = self.plan(status='ACTIVE'); stale = self.plan()
        # Archived meanwhile by another request: the copy in memory still says DRAFT.
        StudyPlan.objects.filter(pk=stale.pk).update(status='ARCHIVED')
        with self.assertRaises(Conflict): activate_plan(stale)
        old.refresh_from_db(); self.assertEqual(old.status, 'ACTIVE')
        with self.assertRaises(Conflict): archive_plan(stale)

    def test_archive_and_archived_plans_are_read_only(self):
        draft, active = self.plan(), self.plan(status='ACTIVE')
        task = self.task(active, at(self.tomorrow, 9))
        for plan in (draft, active):
            r = self.post(f'plans/{plan.pk}/archive/'); self.assertEqual(r.status_code, 200, r.data); self.assertEqual(r.data['status'], 'ARCHIVED')
        self.assertEqual(self.post(f'plans/{draft.pk}/archive/').data['error']['fields'], {'status': ARCHIVED})
        writes = [self.patch(f'plans/{active.pk}/', {'title': 'Nouveau'}), self.post(f'plans/{active.pk}/tasks/', {'title': 'X', 'starts_at': at(self.tomorrow, 14).isoformat(), 'ends_at': at(self.tomorrow, 15).isoformat()}),
            self.patch(f'tasks/{task.pk}/', {'title': 'Modifiée'}), self.patch(f'tasks/{task.pk}/', {'status': 'DONE'}), self.delete(f'tasks/{task.pk}/')]
        for r in writes:
            self.assertEqual(r.status_code, 400); self.assertEqual(r.data['error']['fields'], {'status': ARCHIVED})
        task.refresh_from_db(); self.assertEqual((task.title, task.status), ('Séance', 'TODO'))
        self.assertEqual(self.get(f'plans/{active.pk}/').status_code, 200)

    def test_rename_and_delete_rules(self):
        draft = self.plan(); active = self.plan(status='ACTIVE'); archived = self.plan(status='ARCHIVED')
        r = self.patch(f'plans/{draft.pk}/', {'title': 'Révisions de novembre'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['title'], 'Révisions de novembre')
        for data in ({'title': ' '}, {'title': 'x' * 121}, {'status': 'ACTIVE'}, {}):
            self.assertEqual(self.patch(f'plans/{draft.pk}/', data).status_code, 400, data)
        self.task(active, at(self.tomorrow, 9))
        r = self.delete(f'plans/{active.pk}/'); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['message'], 'Archivez d’abord ce planning.')
        for plan in (draft, archived):
            self.task(plan, at(self.tomorrow, 9))
            self.assertEqual(self.delete(f'plans/{plan.pk}/').status_code, 204)
            self.assertFalse(StudyPlan.objects.filter(pk=plan.pk).exists()); self.assertFalse(RevisionTask.objects.filter(plan_id=plan.pk).exists())
        self.assertEqual(RevisionTask.objects.filter(plan=active).count(), 1)

    def test_goal_deletion_rolls_back_when_a_task_appears_meanwhile(self):
        goal = self.goal(); deadline = self.deadline(goal=goal)
        with patch.object(StudyGoal, 'delete', side_effect=ProtectedError('protégé', set())):
            r = self.delete(f'goals/{goal.pk}/')
        self.assertEqual(r.status_code, 400); self.assertIn('marquez-le « Abandonné »', r.data['error']['message'])
        deadline.refresh_from_db(); self.assertEqual(deadline.goal_id, goal.pk)


class TaskTests(PlanningTestCase):
    def setUp(self):
        super().setUp()
        self.draft = self.plan(); self.active = self.plan(status='ACTIVE')
        self.python = self.goal(title='Python'); self.exam = self.deadline(title='Partiel', goal=self.python)

    def task_data(self, day=0, start=(9, 0), end=(10, 0), **kwargs):
        moment = self.tomorrow + timedelta(days=day)
        return {'title': 'Lire le chapitre 2', 'starts_at': at(moment, *start).isoformat(), 'ends_at': at(moment, *end).isoformat(), **kwargs}

    def test_manual_task_creation(self):
        r = self.post(f'plans/{self.draft.pk}/tasks/', self.task_data(description='Avec fiches', goal_id=str(self.python.pk), deadline_id=str(self.exam.pk)))
        self.assertEqual(r.status_code, 201, r.data); self.assertEqual(set(r.data), TASK_KEYS)
        self.assertEqual((r.data['source'], r.data['status'], r.data['status_label'], r.data['minutes'], r.data['plan_id']), ('MANUAL', 'TODO', 'À faire', 60, str(self.draft.pk)))
        self.assertEqual((r.data['goal'], r.data['deadline']), ({'id': str(self.python.pk), 'title': 'Python'}, {'id': str(self.exam.pk), 'title': 'Partiel'}))
        self.assertEqual(r.data['starts_at'], at(self.tomorrow, 9)); self.assertIsNone(r.data['completed_at'])
        task = RevisionTask.objects.get(pk=r.data['id']); self.assertEqual(task.student_id, self.student.pk)
        self.assertEqual(self.post(f'plans/{self.active.pk}/tasks/', self.task_data()).status_code, 201)
        # Touching tasks are allowed.
        self.assertEqual(self.post(f'plans/{self.draft.pk}/tasks/', self.task_data(start=(10, 0), end=(10, 15))).status_code, 201)

    def test_task_validation(self):
        self.task(self.draft, at(self.tomorrow, 9))
        foreign_goal = self.goal(student=self.other); foreign_deadline = self.deadline(student=self.other)
        cases = {'starts_at': [self.task_data(start=(9, 30), end=(10, 30)), self.task_data(day=-1), self.task_data(day=7)],
            'ends_at': [self.task_data(start=(11, 0), end=(11, 10)), self.task_data(start=(11, 0), end=(15, 1)), self.task_data(start=(12, 0), end=(11, 0)),
                {**self.task_data(start=(23, 0)), 'ends_at': at(self.tomorrow + timedelta(days=1), 0, 30).isoformat()}, self.task_data(ends_at='demain')],
            'goal_id': [self.task_data(goal_id=str(foreign_goal.pk)), self.task_data(goal_id='a' * 24), self.task_data(goal_id='abc')],
            'deadline_id': [self.task_data(deadline_id=str(foreign_deadline.pk))],
            'title': [self.task_data(title='  '), self.task_data(title='x' * 121)],
            'status': [self.task_data(status='DONE')]}
        for field, payloads in cases.items():
            for data in payloads:
                r = self.post(f'plans/{self.draft.pk}/tasks/', data); self.assertEqual(r.status_code, 400, (data, r.data))
                self.assertIn(field, r.data['error']['fields'], (data, r.data))
        r = self.post(f'plans/{self.draft.pk}/tasks/', self.task_data(start=(9, 30), end=(10, 30)))
        self.assertEqual(r.data['error']['fields']['starts_at'], ['Cette tâche chevauche une autre tâche du planning.'])
        self.assertEqual(self.post(f'plans/{self.draft.pk}/tasks/', self.task_data(day=-1)).data['error']['fields']['starts_at'], ['Placez la tâche entre les dates du planning.'])
        self.assertEqual(self.post(f'plans/{self.draft.pk}/tasks/', self.task_data(start=(11, 0), end=(15, 1))).data['error']['fields']['ends_at'], ['Une tâche dure entre 15 minutes et 4 heures.'])
        # Another plan's task does not count as an overlap.
        self.assertEqual(self.post(f'plans/{self.active.pk}/tasks/', self.task_data(start=(9, 30), end=(10, 30))).status_code, 201)
        self.assertEqual(RevisionTask.objects.filter(plan=self.draft).count(), 1)

    def test_task_edit_and_delete(self):
        task = self.task(self.draft, at(self.tomorrow, 9), goal=self.python)
        other = self.task(self.draft, at(self.tomorrow, 11))
        r = self.patch(f'tasks/{task.pk}/', {'title': 'Exercices', 'ends_at': at(self.tomorrow, 10, 45).isoformat(), 'goal_id': None, 'deadline_id': str(self.exam.pk)})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['title'], r.data['minutes'], r.data['goal'], r.data['deadline']['id']), ('Exercices', 105, None, str(self.exam.pk)))
        self.assertEqual(self.patch(f'tasks/{task.pk}/', {'ends_at': at(self.tomorrow, 11, 30).isoformat()}).status_code, 400)
        self.assertEqual(self.patch(f'tasks/{task.pk}/', {'plan_id': str(self.active.pk)}).status_code, 400)
        self.assertEqual(self.delete(f'tasks/{other.pk}/').status_code, 204); self.assertFalse(RevisionTask.objects.filter(pk=other.pk).exists())
        self.assertEqual(self.patch(f'tasks/{task.pk}/', {'ends_at': at(self.tomorrow, 11, 30).isoformat()}).status_code, 200)

    def test_status_changes_only_in_active_plans_and_completed_at(self):
        draft_task = self.task(self.draft, at(self.tomorrow, 9))
        r = self.patch(f'tasks/{draft_task.pk}/', {'status': 'DONE'}); self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['error']['fields'], {'status': ['Activez le planning pour suivre vos tâches.']})
        task = self.task(self.active, at(self.tomorrow, 9))
        r = self.patch(f'tasks/{task.pk}/', {'status': 'DONE'}); self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['status_label'], 'Terminée'); done_at = r.data['completed_at']; self.assertIsNotNone(done_at)
        task.refresh_from_db(); self.assertEqual(task.completed_at, done_at)
        later = timezone.now() + timedelta(hours=1)
        with patch('planning.services.timezone.now', return_value=later):
            self.assertEqual(self.patch(f'tasks/{task.pk}/', {'status': 'DONE', 'title': 'Relue'}).data['completed_at'], done_at)
        r = self.patch(f'tasks/{task.pk}/', {'status': 'SKIPPED'}); self.assertEqual((r.data['status'], r.data['completed_at']), ('SKIPPED', None))
        self.assertEqual(self.patch(f'tasks/{task.pk}/', {'status': 'DONE'}).data['status'], 'DONE')
        r = self.patch(f'tasks/{task.pk}/', {'status': 'TODO'}); self.assertEqual((r.data['status'], r.data['completed_at']), ('TODO', None))
        self.assertEqual(self.patch(f'tasks/{task.pk}/', {'status': 'FINI'}).status_code, 400)

    def test_csrf_on_task_and_deadline_writes(self):
        client = APIClient(enforce_csrf_checks=True); client.force_login(self.student)
        task = self.task(self.active, at(self.tomorrow, 9))
        for path in [f'tasks/{task.pk}/', f'deadlines/{self.exam.pk}/']:
            self.assertEqual(self.patch(path, {'title': 'X'}, client).status_code, 403, path)
            self.assertEqual(self.delete(path, client).status_code, 403, path)
        self.assertTrue(RevisionTask.objects.filter(pk=task.pk, title='Séance').exists()); self.assertTrue(Deadline.objects.filter(pk=self.exam.pk).exists())


class CalendarTests(PlanningTestCase):
    def test_ics_export(self):
        goal = self.goal(title='Python'); deadline = self.deadline(title='Partiel, session 1')
        plan = self.plan(status='ACTIVE')
        self.task(plan, at(self.tomorrow, 9), title='Révision ; chapitre 1, partie \\ fin', description='Ligne 1\nLigne 2', goal=goal, deadline=deadline)
        skipped = self.task(plan, at(self.tomorrow, 14), minutes=30, title='Lecture', status='SKIPPED')
        r = self.get(f'plans/{plan.pk}/ics/'); self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertEqual(r['Content-Disposition'], f'attachment; filename="planning-{plan.pk}.ics"')
        self.assertEqual(r['Cache-Control'], 'private, no-store')
        body = r.content.decode('utf-8')
        self.assertTrue(body.startswith('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Nexora//Hub Educatif//FR\r\n')); self.assertTrue(body.endswith('END:VCALENDAR\r\n'))
        self.assertNotIn('\n', body.replace('\r\n', ''))
        lines = body.split('\r\n')[:-1]
        self.assertTrue(all(len(line.encode('utf-8')) <= 75 for line in lines))
        unfolded = body.replace('\r\n ', '')
        self.assertEqual(unfolded.count('BEGIN:VEVENT'), 2)
        start = at(self.tomorrow, 9).astimezone(dt_timezone.utc)
        self.assertIn(f'DTSTART:{start:%Y%m%dT%H%M%S}Z\r\n', unfolded); self.assertIn(f'DTEND:{start + timedelta(hours=1):%Y%m%dT%H%M%S}Z\r\n', unfolded)
        self.assertIn(f'UID:{skipped.pk}@nexora\r\n', unfolded)
        self.assertIn('SUMMARY:Révision \\; chapitre 1\\, partie \\\\ fin\r\n', unfolded)
        self.assertIn('DESCRIPTION:Ligne 1\\nLigne 2\\nObjectif : Python\\nÉchéance : Partiel\\, session 1\r\n', unfolded)
        self.assertEqual((unfolded.count('STATUS:CONFIRMED'), unfolded.count('STATUS:CANCELLED')), (1, 1))
        self.assertRegex(unfolded, r'DTSTAMP:\d{8}T\d{6}Z\r\n')
        # Calendar clients that only accept text/calendar still get the file.
        self.assertEqual(self.client.get(f'{API}plans/{plan.pk}/ics/', HTTP_ACCEPT='text/calendar').status_code, 200)
        empty = self.get(f'plans/{self.plan().pk}/ics/').content.decode()
        self.assertNotIn('VEVENT', empty); self.assertIn('X-WR-CALNAME:Planning test\r\n', empty)

    def test_escaping_and_folding(self):
        self.assertEqual(ics.escape('a;b,c\\d\r\ne\rf\ng'), 'a\\;b\\,c\\\\d\\ne\\nf\\ng')
        line = 'DESCRIPTION:' + 'é' * 80
        folded = ics.fold(line)
        parts = folded.split('\r\n')
        self.assertTrue(all(len(p.encode('utf-8')) <= 75 for p in parts)); self.assertTrue(all(p.startswith(' ') for p in parts[1:]))
        self.assertEqual(folded.replace('\r\n ', ''), line)
        self.assertEqual(len(parts[0].encode('utf-8')), 74)  # 12 ASCII octets + 31 two-octet characters: never split a character.
        self.assertEqual(ics.fold('x' * 75), 'x' * 75); self.assertEqual(ics.fold('x' * 76), 'x' * 75 + '\r\n x')
