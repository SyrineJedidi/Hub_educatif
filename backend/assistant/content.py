"""Where the assistant's knowledge comes from: teacher notes per group, and course resources when that module is installed."""
import hashlib
import re
from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Protocol
from bson import ObjectId
from django.apps import apps
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from classrooms.models import Enrollment, LearningGroup
from .models import ScopeIndex, TeacherNote, ValidatedAnswer
from .retrieval import forget

NOT_FOUND = 'Ressource introuvable.'
VALIDATED_TITLE = 'Réponse validée par l’enseignant'


@dataclass
class Scope:
    source_type: str
    scope_id: str
    title: str
    teacher_id: str
    group_ids: list = field(default_factory=list)

    @property
    def key(self):
        return f'{self.source_type}:{self.scope_id}'


@dataclass
class Segment:
    source_kind: str
    source_id: str
    source_title: str
    chapter_title: str
    page: int | None
    start_seconds: float | None
    url: str
    text: str


class ContentProvider(Protocol):
    source_type: str
    def scopes_for(self, user) -> list[Scope]: ...
    def get_scope(self, user, scope_id) -> Scope: ...
    def managed_scopes(self, user) -> list[Scope]: ...
    def get_managed_scope(self, user, scope_id) -> Scope: ...
    def segments(self, scope_id) -> Iterable[Segment]: ...
    def version(self, scope_id) -> str: ...


def validated_segments(source_type, scope_id):
    for answer in ValidatedAnswer.objects.filter(source_type=source_type, scope_id=str(scope_id)).order_by('created_at', 'id'):
        yield Segment('VALIDATED', str(answer.pk), VALIDATED_TITLE, answer.question[:200], None, None, '', f'{answer.question}\n\n{answer.answer}')


def validated_fingerprint(source_type, scope_id):
    ids = ValidatedAnswer.objects.filter(source_type=source_type, scope_id=str(scope_id)).order_by('id').values_list('id', flat=True)
    return ','.join(str(pk) for pk in ids)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def current_group_ids(student):
    # Same current-period rule as the quizzes: start included, end excluded, archived groups hidden.
    now = timezone.now()
    ids = list(Enrollment.objects.filter(student=student, starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).values_list('group_id', flat=True))
    return list(LearningGroup.objects.filter(pk__in=ids, archived=False).values_list('id', flat=True))


def note_blocks(note):
    """One segment per paragraph; a Markdown heading names the section of the paragraphs that follow it."""
    section = ''
    for block in re.split(r'\n\s*\n', note.body.replace('\r\n', '\n')):
        lines = [line for line in block.strip().split('\n') if line.strip()]
        while lines and re.match(r'#{1,6}\s', lines[0].strip()):
            section = lines.pop(0).strip().lstrip('#').strip()[:200]
        if lines: yield section, '\n'.join(lines)


class NotesProvider:
    source_type = 'group'

    def scope(self, group):
        return Scope(self.source_type, str(group.pk), group.name, str(group.teacher_id), [str(group.pk)])

    def group(self, scope_id):
        if not ObjectId.is_valid(str(scope_id)): raise NotFound(NOT_FOUND)
        group = LearningGroup.objects.filter(pk=ObjectId(str(scope_id))).first()
        if not group: raise NotFound(NOT_FOUND)
        return group

    def scopes_for(self, user):
        if user.role == 'TEACHER':
            groups = LearningGroup.objects.filter(teacher=user, archived=False)
        elif user.role == 'STUDENT':
            with_notes = set(TeacherNote.objects.filter(group_id__in=current_group_ids(user)).values_list('group_id', flat=True))
            groups = LearningGroup.objects.filter(pk__in=list(with_notes), archived=False)
        else:
            return []
        return [self.scope(g) for g in groups.order_by('name', 'id')]

    def get_scope(self, user, scope_id):
        group = self.group(scope_id)
        if group.archived: raise NotFound(NOT_FOUND)
        if user.role == 'TEACHER' and group.teacher_id == user.pk: return self.scope(group)
        if user.role == 'STUDENT' and group.pk in current_group_ids(user) and TeacherNote.objects.filter(group=group).exists():
            return self.scope(group)
        raise NotFound(NOT_FOUND)

    def managed_scopes(self, user):
        groups = LearningGroup.objects.filter(archived=False)
        if user.role == 'TEACHER': groups = groups.filter(teacher=user)
        elif user.role != 'ADMIN': return []
        return [self.scope(g) for g in groups.order_by('name', 'id')]

    def get_managed_scope(self, user, scope_id):
        group = self.group(scope_id)
        if user.role == 'ADMIN' or (user.role == 'TEACHER' and group.teacher_id == user.pk): return self.scope(group)
        raise NotFound(NOT_FOUND)

    def segments(self, scope_id):
        for note in TeacherNote.objects.filter(group_id=ObjectId(str(scope_id))).order_by('created_at', 'id'):
            for section, text in note_blocks(note):
                yield Segment('NOTE', str(note.pk), note.title, section, None, None, '', text)
        yield from validated_segments(self.source_type, scope_id)

    def version(self, scope_id):
        notes = TeacherNote.objects.filter(group_id=ObjectId(str(scope_id))).order_by('id').values_list('id', 'version')
        return digest(';'.join(f'{pk}:{version}' for pk, version in notes) + '|' + validated_fingerprint(self.source_type, scope_id))


class CoursesProvider:
    """Adapter over the public contract of the courses module, imported lazily so the assistant runs without it."""
    source_type = 'course'

    def scope(self, course):
        links = getattr(course, 'group_links', None)
        group_ids = [str(g) for g in links.values_list('group_id', flat=True)] if links is not None else []
        return Scope(self.source_type, str(course.pk), course.title, str(course.teacher_id), group_ids)

    def visible(self, user):
        from courses.services import visible_courses
        return [c for c in visible_courses(user) if getattr(c, 'status', '') != 'ARCHIVED']

    def course(self, user, scope_id):
        from courses.services import get_visible_course
        try: return get_visible_course(user, scope_id)
        except NotFound: raise NotFound(NOT_FOUND)

    def scopes_for(self, user):
        if user.role not in ('STUDENT', 'TEACHER'): return []
        return sorted((self.scope(c) for c in self.visible(user)), key=lambda s: (s.title.casefold(), s.scope_id))

    def get_scope(self, user, scope_id):
        if user.role not in ('STUDENT', 'TEACHER'): raise NotFound(NOT_FOUND)
        course = self.course(user, scope_id)
        if getattr(course, 'status', '') == 'ARCHIVED': raise NotFound(NOT_FOUND)
        return self.scope(course)

    def managed_scopes(self, user):
        if user.role not in ('TEACHER', 'ADMIN'): return []
        return sorted((self.scope(c) for c in self.visible(user)), key=lambda s: (s.title.casefold(), s.scope_id))

    def get_managed_scope(self, user, scope_id):
        if user.role not in ('TEACHER', 'ADMIN'): raise NotFound(NOT_FOUND)
        return self.scope(self.course(user, scope_id))

    def segments(self, scope_id):
        from courses.services import course_segments, resource_url
        for item in course_segments(scope_id):
            url = resource_url(str(scope_id), item['resource_id'], page=item.get('page'), start_seconds=item.get('start_seconds'))
            yield Segment('RESOURCE', item['resource_id'], item['resource_title'], item.get('chapter_title') or '',
                item.get('page'), item.get('start_seconds'), url, item['text'])
        yield from validated_segments(self.source_type, scope_id)

    def version(self, scope_id):
        from courses.services import course_content_version
        return f'{course_content_version(scope_id)}:{digest(validated_fingerprint(self.source_type, scope_id))}'


def course_changed(sender=None, course_id=None, **kwargs):
    # The version check catches every change anyway; this only frees memory and forces the rebuild early.
    if not course_id: return
    ScopeIndex.objects.filter(source_type='course', scope_id=str(course_id)).update(content_version='')
    forget('course', str(course_id))


def connect_course_signal():
    from courses.signals import course_content_changed
    course_content_changed.connect(course_changed, dispatch_uid='assistant.course_content_changed')


def providers():
    registry = {'group': NotesProvider()}
    if apps.is_installed('courses'):
        connect_course_signal()
        registry['course'] = CoursesProvider()
    return registry


def provider_for(source_type, field='scope_key'):
    provider = providers().get(source_type)
    if not provider: raise ValidationError({field: ['Sélectionnez un type de contenu disponible.']})
    return provider
