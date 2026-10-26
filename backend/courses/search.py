import unicodedata
from rest_framework.exceptions import ValidationError
from classrooms.services import get_object
from .models import Chapter, Resource, ResourceSegment, Subject, normalized_text
from .services import get_visible_course, paged_list, resource_url, visible_courses

SNIPPET_LENGTH = 220
SNIPPET_CONTEXT = 60
MAX_WORDS = 6
MAX_CANDIDATES = 500
HITS_PER_RESOURCE = 3
TYPE_ORDER = {'course': 0, 'chapter': 1, 'resource': 2, 'segment': 3}


def normalized_map(text):
    """Same result as normalized_text, plus the original index of every normalised character."""
    chars, origin = [], []
    for index, char in enumerate(text):
        for part in unicodedata.normalize('NFKD', char):
            if unicodedata.combining(part): continue
            for folded in part.casefold():
                if folded.isspace():
                    if not chars or chars[-1] == ' ': continue
                    folded = ' '
                chars.append(folded); origin.append(index)
    if chars and chars[-1] == ' ': chars.pop(); origin.pop()
    return ''.join(chars), origin


def query_terms(request):
    raw = request.query_params.get('q', '').strip()[:100]
    words = normalized_text(raw).split()[:MAX_WORDS]
    if len(raw) < 2 or len(' '.join(words)) < 2: raise ValidationError({'q': ['Saisissez au moins 2 caractères.']})
    return list(dict.fromkeys(words)), ' '.join(words)


def score(fields, words, phrase):
    """fields: [(weight, normalised text)]. Every word must occur in at least one field."""
    total = 0
    for word in words:
        weight = max((w for w, text in fields if word in text), default=0)
        if not weight: return 0
        total += weight
    if len(words) > 1 and any(phrase in text for _, text in fields): total += 1
    return total


def merged(spans):
    result = []
    for start, end in sorted(spans):
        if result and start <= result[-1][1]: result[-1][1] = max(result[-1][1], end)
        else: result.append([start, end])
    return result


def snippet(text, words):
    """Up to SNIPPET_LENGTH characters of the original text around the first hit, with highlight offsets inside it."""
    normalized, origin = normalized_map(text)
    spans = []
    for word in words:
        start = normalized.find(word)
        while start != -1:
            end = start + len(word)
            first, last = origin[start], origin[end - 1] + 1
            while last < len(text) and unicodedata.combining(text[last]): last += 1
            spans.append((first, last))
            start = normalized.find(word, end)
    if len(text) <= SNIPPET_LENGTH: begin, finish = 0, len(text)
    else:
        budget = SNIPPET_LENGTH - 2
        anchor = min(spans)[0] - SNIPPET_CONTEXT if spans else 0
        begin = max(0, min(anchor, len(text) - budget))
        finish = begin + budget
    prefix, suffix = ('…' if begin else ''), ('…' if finish < len(text) else '')
    shift = len(prefix) - begin
    highlights = merged([[max(s, begin) + shift, min(e, finish) + shift] for s, e in spans if s < finish and e > begin])
    return prefix + text[begin:finish] + suffix, highlights


def best_text(texts, words):
    """The original text containing the most query words; earlier texts win ties."""
    counts = [sum(word in normalized_text(text) for word in words) for text in texts]
    return texts[counts.index(max(counts))]


def search(request):
    words, phrase = query_terms(request)
    courses = visible_courses(request.user)
    if request.query_params.get('subject'):
        courses = courses.filter(subject=get_object(Subject, request.query_params['subject']))
    if request.query_params.get('course'):
        courses = courses.filter(pk=get_visible_course(request.user, request.query_params['course']).pk)
    kind = request.query_params.get('kind')
    if kind and kind not in Resource.Kind.values: raise ValidationError({'kind': ['Sélectionnez un type de ressource valide.']})
    courses = {c.pk: c for c in courses}
    subjects = {s.pk: s for s in Subject.objects.filter(pk__in=[c.subject_id for c in courses.values()])}
    chapters = {c.pk: c for c in Chapter.objects.filter(course_id__in=list(courses))}
    resources = Resource.objects.filter(course_id__in=list(courses))
    resources = {r.pk: r for r in (resources.filter(kind=kind) if kind else resources)}
    found = []

    def add(kind_name, points, course, chapter=None, resource=None, text='', segment=None):
        excerpt, highlights = snippet(text, words)
        page = segment.page if segment else None
        start_seconds = segment.start_seconds if segment else None
        if resource: link = resource_url(course.pk, resource.pk, page=page, start_seconds=start_seconds)
        elif chapter: link = f'/espace/cours/{course.pk}#chapitre-{chapter.pk}'
        else: link = f'/espace/cours/{course.pk}'
        position = (chapter.position if chapter else 0, resource.position if resource else 0, segment.order if segment else 0)
        found.append(((-points, normalized_text(course.title), str(course.pk), *position, TYPE_ORDER[kind_name]), {
            'type': kind_name, 'score': points, 'course': {'id': str(course.pk), 'title': course.title},
            'chapter': {'id': str(chapter.pk), 'title': chapter.title} if chapter else None,
            'resource': {'id': str(resource.pk), 'title': resource.title, 'kind': resource.kind} if resource else None,
            'snippet': excerpt, 'highlights': highlights, 'page': page, 'start_seconds': start_seconds, 'link': link}))

    if not kind:
        for course in courses.values():
            subject_name = subjects[course.subject_id].name if course.subject_id in subjects else ''
            points = score([(3, normalized_text(course.title)), (2, normalized_text(course.description)), (1, normalized_text(subject_name))], words, phrase)
            if points: add('course', points, course, text=best_text([course.description, course.title, subject_name], words))
        for chapter in chapters.values():
            points = score([(3, normalized_text(chapter.title)), (2, normalized_text(chapter.description))], words, phrase)
            if points: add('chapter', points, courses[chapter.course_id], chapter, text=best_text([chapter.description, chapter.title], words))
    for resource in resources.values():
        points = score([(3, normalized_text(resource.title)), (2, normalized_text(resource.description))], words, phrase)
        if points: add('resource', points, courses[resource.course_id], chapters[resource.chapter_id], resource,
            text=best_text([resource.description, resource.title], words))
    ready = [pk for pk, r in resources.items() if r.processing_status == Resource.ProcessingStatus.READY]
    segments = ResourceSegment.objects.filter(resource_id__in=ready)
    for word in words: segments = segments.filter(search_text__icontains=word)
    by_resource = {}
    for segment in segments.order_by('resource', 'order')[:MAX_CANDIDATES]:
        points = score([(1, segment.search_text)], words, phrase)
        by_resource.setdefault(segment.resource_id, []).append((points, segment))
    for resource_id, hits in by_resource.items():
        resource = resources[resource_id]
        for points, segment in sorted(hits, key=lambda hit: (-hit[0], hit[1].order))[:HITS_PER_RESOURCE]:
            add('segment', points, courses[resource.course_id], chapters[resource.chapter_id], resource, segment.text, segment)
    found.sort(key=lambda item: item[0])
    return paged_list(request, [item for _, item in found], lambda item: item)
