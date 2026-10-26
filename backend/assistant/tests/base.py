"""Shared fixtures: two teachers with one group each, an enrolled student per group, and short course notes."""
import secrets
import sys
from contextlib import ExitStack
from datetime import timedelta
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from bson import ObjectId
from django.apps import apps
from django.dispatch import Signal
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient
from accounts.models import User
from classrooms.models import Enrollment, LearningGroup
from assistant import retrieval
from assistant.content import current_group_ids
from assistant.models import Conversation, Message, TeacherNote

VECTORS = ('## Définition\nUn vecteur est défini par une direction, un sens et une norme. La norme d’un vecteur est sa longueur.\n\n'
    '## Addition\nLa somme de deux vecteurs se construit avec la relation de Chasles : on place les vecteurs bout à bout.\n\n'
    '## Colinéarité\nDeux vecteurs sont colinéaires lorsqu’ils ont la même direction. Leur déterminant est alors égal à zéro.')
ENERGY = ('## Énergie cinétique\nL’énergie cinétique d’un objet de masse m et de vitesse v vaut la moitié de m fois v au carré.\n\n'
    '## Conservation\nSans frottement, l’énergie mécanique d’un système se conserve.')
IN_SCOPE = 'Qu’est-ce que la norme d’un vecteur ?'
OUT_OF_SCOPE = 'Quelle est la capitale de l’Australie ?'
FIRST_SENTENCE = 'Un vecteur est défini par une direction, un sens et une norme.'
DAY = 86400


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], ASSISTANT_LLM_PROVIDER='fake', WHISPER_PROVIDER='fake',
    ASSISTANT_DAILY_QUESTIONS=30, ASSISTANT_GLOBAL_DAILY_BUDGET=400, ASSISTANT_MIN_SCORE=1.0, ASSISTANT_QUIZ_LOCK_HOURS=3)
class AssistantTestCase(TransactionTestCase):
    def setUp(self):
        # The corpus cache lives in the process: one test's index must never answer the next one.
        cache = patch.dict(retrieval._cache, clear=True); cache.start(); self.addCleanup(cache.stop)
        password = secrets.token_urlsafe(24)
        self.admin = User.objects.create_superuser('admin@assistant.test', password, first_name='Admin', last_name='Nexora')
        self.teacher = User.objects.create_user('teacher@assistant.test', password, role='TEACHER', first_name='Claire', last_name='Martin')
        self.other_teacher = User.objects.create_user('other.teacher@assistant.test', password, role='TEACHER', first_name='Paul', last_name='Durand')
        self.student = User.objects.create_user('lea.bernard@assistant.test', password, first_name='Léa', last_name='Bernard')
        self.other_student = User.objects.create_user('yanis.petit@assistant.test', password, first_name='Yanis', last_name='Petit')
        self.group = LearningGroup.objects.create(name='Seconde A', code='SECA', teacher=self.teacher, level='Seconde', academic_year='2026')
        self.other_group = LearningGroup.objects.create(name='Terminale B', code='TERMB', teacher=self.other_teacher, level='Terminale', academic_year='2026')
        now = timezone.now()
        self.enrollment = Enrollment.objects.create(student=self.student, group=self.group, starts_at=now - timedelta(days=1))
        Enrollment.objects.create(student=self.other_student, group=self.other_group, starts_at=now - timedelta(days=1))
        self.note = TeacherNote.objects.create(group=self.group, teacher=self.teacher, title='Les vecteurs', body=VECTORS)
        self.other_note = TeacherNote.objects.create(group=self.other_group, teacher=self.other_teacher, title='L’énergie', body=ENERGY)
        self.scope_key = f'group:{self.group.pk}'
        self.other_scope_key = f'group:{self.other_group.pk}'
        self.student_client, self.teacher_client = self.as_user(self.student), self.as_user(self.teacher)

    def as_user(self, user):
        client = APIClient(); client.force_login(user); return client

    def start(self, client=None, **data):
        response = (client or self.student_client).post('/api/assistant/conversations/', {'scope_key': self.scope_key, **data}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def ask(self, conversation_id, content=IN_SCOPE, client=None, **extra):
        return (client or self.student_client).post(f'/api/assistant/conversations/{conversation_id}/messages/', {'content': content, **extra}, format='json')

    def answered(self, conversation_id, content=IN_SCOPE, client=None, **extra):
        response = self.ask(conversation_id, content, client, **extra)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def refused(self, response, status, code):
        self.assertEqual(response.status_code, status, getattr(response, 'data', response))
        self.assertEqual(response.data['error']['code'], code, response.data)
        return response.data['error']

    def conversation_row(self, owner=None, group=None, **fields):
        """A conversation written directly, for lists whose order or dates must be controlled."""
        owner, group = owner or self.student, group or self.group
        return Conversation.objects.create(owner=owner, source_type='group', scope_id=str(group.pk), scope_title=group.name, **fields)

    def message_row(self, conversation, role='USER', **fields):
        return Message.objects.create(conversation=conversation, owner_id=conversation.owner_id, source_type=conversation.source_type,
            scope_id=conversation.scope_id, role=role, **fields)


def resource_url(course_id, resource_id, *, page=None, start_seconds=None):
    # Same contract as the courses module.
    url = f'/espace/cours/{course_id}/ressources/{resource_id}'
    if page: return f'{url}?page={int(page)}'
    if start_seconds is not None: return f'{url}?t={int(start_seconds)}'
    return url


class CoursesStub:
    """Stand-in for the public contract of the courses module, which this branch does not contain.

    Visibility follows that module's rules: the administrator sees every course, a teacher their own courses,
    a student the published courses linked to one of their current groups."""

    def __init__(self):
        self.courses, self.segments, self.versions = {}, {}, {}
        self.signal = Signal()
        services = ModuleType('courses.services')
        services.visible_courses = self.visible_courses
        services.get_visible_course = self.get_visible_course
        services.course_segments = lambda course_id: iter(self.segments.get(str(course_id), []))
        services.course_content_version = self.course_content_version
        services.resource_url = resource_url
        signals = ModuleType('courses.signals'); signals.course_content_changed = self.signal
        package = ModuleType('courses'); package.services, package.signals = services, signals
        self.modules = {'courses': package, 'courses.services': services, 'courses.signals': signals}

    def add(self, title, teacher, groups=(), status='PUBLISHED', segments=()):
        course_id = str(ObjectId())
        group_ids = [ObjectId(str(g.pk)) for g in groups]
        self.courses[course_id] = SimpleNamespace(pk=ObjectId(course_id), title=title, teacher_id=teacher.pk, status=status,
            group_links=SimpleNamespace(values_list=lambda *fields, flat=False, ids=group_ids: list(ids)))
        self.segments[course_id] = list(segments)
        self.versions[course_id] = 1
        return course_id

    def visible_courses(self, user, *, at=None):
        if user.role == 'ADMIN': return list(self.courses.values())
        if user.role == 'TEACHER': return [c for c in self.courses.values() if c.teacher_id == user.pk]
        groups = set(current_group_ids(user))
        return [c for c in self.courses.values() if c.status == 'PUBLISHED' and groups & set(c.group_links.values_list('group_id', flat=True))]

    def get_visible_course(self, user, course_id):
        course = next((c for c in self.visible_courses(user) if str(c.pk) == str(course_id)), None)
        if not course: raise NotFound('Cours introuvable.')
        return course

    def course_content_version(self, course_id):
        if str(course_id) not in self.versions: raise NotFound('Cours introuvable.')
        return str(self.versions[str(course_id)])

    def changed(self, course_id):
        """What the courses module does after a content change: bump the version, then send the signal."""
        self.versions[course_id] += 1
        self.signal.send(sender=None, course_id=course_id, resource_id=None, reason='resource_updated')

    def installed(self):
        stack, real = ExitStack(), apps.is_installed
        stack.enter_context(patch.dict(sys.modules, self.modules))
        stack.enter_context(patch.object(apps, 'is_installed', lambda name: name == 'courses' or real(name)))
        return stack


def segment(text, resource_id, title='Cours de physique', chapter='Chapitre 1', page=None, start_seconds=None):
    return {'resource_id': resource_id, 'resource_title': title, 'kind': 'PDF' if page else 'AUDIO', 'chapter_id': 'c' * 24,
        'chapter_title': chapter, 'order': 1, 'text': text, 'page': page, 'start_seconds': start_seconds, 'end_seconds': None}
