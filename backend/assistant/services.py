import hashlib
import logging
import re
import time
from datetime import timedelta
from bson import ObjectId
from django.conf import settings
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import DatabaseError, IntegrityError
from django.db.models import F, Q
from django.utils import timezone
from django_mongodb_backend import transaction
from rest_framework.exceptions import APIException, NotFound, Throttled, ValidationError
from rest_framework.fields import ChoiceField
from accounts.models import RateBucket, User
from accounts.services import limit
from classrooms.models import LearningGroup
from classrooms.services import Conflict, get_object
from .content import provider_for, providers
from .indexing import ensure_index
from .llm import LLMError, answer_schema, generate_answer
from .models import (DEFAULT_CONVERSATION_TITLE, AnswerFeedback, AssistantSettings, Conversation, Message, Mode,
    TeacherNote, ValidatedAnswer)
from .prompts import OUT_OF_SCOPE_MESSAGE, build_prompt, parse_answer, timestamp
from .retrieval import is_overview_question, overview_hits, retrieve

logger = logging.getLogger('assistant')

DAY = 86400
TRASH_DAYS = 30
MAX_PINNED = 5
SEND_PER_MINUTE = 12
SENDS_PER_DAY = 300
CONVERSATIONS_PER_HOUR = 60
MODE_LOCKED = 'Votre enseignant a fixé le mode de l’assistant pour ce cours.'
TRASH_LOCKED = 'Cette conversation est dans la corbeille : restaurez-la pour continuer.'
# Provider errors after which no model processed the request, whatever the question: the only ones given back.
UNSERVED_ERRORS = {'disabled', 'quota', 'auth'}


class ScopeUnavailable(APIException):
    status_code = 403
    default_detail = 'Ce cours n’est plus accessible : la conversation est en lecture seule.'
    default_code = 'scope_unavailable'


class AssistantDisabled(APIException):
    status_code = 403
    default_detail = 'L’assistant est désactivé pour ce cours par votre enseignant.'
    default_code = 'assistant_disabled'


class ConversationLocked(APIException):
    status_code = 409
    default_detail = 'Cette conversation est archivée : désarchivez-la pour poser une nouvelle question.'
    default_code = 'conversation_locked'


class NotInTrash(APIException):
    status_code = 409
    default_detail = 'Cette conversation n’est pas dans la corbeille.'
    default_code = 'conversation_not_deleted'


class QuizInProgress(APIException):
    status_code = 409
    default_detail = 'Terminez d’abord votre quiz en cours : l’assistant est suspendu pendant une évaluation.'
    default_code = 'quiz_in_progress'


class AnswerInProgress(APIException):
    status_code = 409
    default_detail = 'La réponse à cette question est encore en cours de rédaction. Patientez quelques secondes puis rechargez la conversation.'
    default_code = 'answer_in_progress'


class AlreadyReviewed(APIException):
    status_code = 409
    default_detail = 'Ce retour a déjà été traité par l’enseignant : il ne peut plus être modifié.'
    default_code = 'already_reviewed'


class QuotaExceeded(Throttled):
    default_code = 'quota_exceeded'

    def __init__(self, detail, seconds):
        super().__init__(detail=detail)
        # Set after the constructor so DRF does not append its own waiting sentence.
        self.wait = max(1, int(seconds - time.time() % seconds))


def mongo_now():
    now = timezone.now()
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


# Quotas -----------------------------------------------------------------------------------------

def bucket_key(name, identity, seconds):
    # Same key as accounts.services.limit, so a quota can be read without being consumed.
    return hashlib.sha256(f'{name}:{identity}:{int(time.time()) // seconds}'.encode()).hexdigest()


def remaining(name, identity, maximum, seconds):
    hits = RateBucket.objects.filter(key=bucket_key(name, identity, seconds)).values_list('hits', flat=True).first() or 0
    used = min(hits, maximum)
    return {'limit': maximum, 'used': used, 'remaining': maximum - used}


def refund(name, identity, seconds):
    RateBucket.objects.filter(key=bucket_key(name, identity, seconds), hits__gt=0).update(hits=F('hits') - 1)


def consume(request, name, maximum, seconds, identity, message, keep_rejected=False):
    try:
        limit(request, name, maximum=maximum, seconds=seconds, identity=identity)
    except Throttled:
        # A refused question is not an answered one: keep the counter equal to what was actually used.
        if not keep_rejected: refund(name, identity, seconds)
        raise QuotaExceeded(message, seconds)


def question_identity(user, source_type, scope_id):
    return f'{user.pk}:{source_type}:{scope_id}'


def daily_limit(row):
    return min(row.daily_question_limit, settings.ASSISTANT_DAILY_QUESTIONS)


def question_quota(user, source_type, scope_id, row):
    return remaining('assistant-question', question_identity(user, source_type, scope_id), daily_limit(row), DAY)


def global_quota():
    return remaining('assistant-global', 'global', settings.ASSISTANT_GLOBAL_DAILY_BUDGET, DAY)


def check_spam(request):
    consume(request, 'assistant-send', SEND_PER_MINUTE, 60, str(request.user.pk),
        'Vous envoyez des questions trop rapidement. Patientez une minute avant de réessayer.', keep_rejected=True)
    # Questions refused outside the course cost no quota but are stored: this bounds what one account writes in a day.
    consume(request, 'assistant-day', SENDS_PER_DAY, DAY, str(request.user.pk),
        f'Vous avez envoyé {SENDS_PER_DAY} questions aujourd’hui, le maximum par jour. Revenez demain.', keep_rejected=True)


def check_conversation_rate(request):
    consume(request, 'assistant-conversation', CONVERSATIONS_PER_HOUR, 3600, str(request.user.pk),
        'Vous avez ouvert beaucoup de conversations en peu de temps. Réessayez dans une heure.', keep_rejected=True)


def consume_question(request, scope, row):
    maximum = daily_limit(row)
    consume(request, 'assistant-question', maximum, DAY, question_identity(request.user, scope.source_type, scope.scope_id),
        f'Vous avez atteint votre limite de {maximum} questions pour aujourd’hui dans ce cours. Revenez demain.')
    try:
        consume(request, 'assistant-global', settings.ASSISTANT_GLOBAL_DAILY_BUDGET, DAY, 'global',
            'L’assistant a atteint sa limite d’utilisation pour aujourd’hui. Réessayez demain.')
    except QuotaExceeded:
        refund('assistant-question', question_identity(request.user, scope.source_type, scope.scope_id), DAY)
        raise


# Scopes and settings ---------------------------------------------------------------------------

def parse_scope_key(value, field='scope_key'):
    match = re.fullmatch(r'([a-z]{1,10}):([0-9a-fA-F]{24})', str(value or '').strip())
    if not match: raise ValidationError({field: ['Sélectionnez un cours valide.']})
    return match.group(1), match.group(2).lower()


def settings_row(source_type, scope_id):
    """Stored settings, or unsaved defaults when the teacher never changed them."""
    return AssistantSettings.objects.filter(source_type=source_type, scope_id=str(scope_id)).first() or AssistantSettings(source_type=source_type, scope_id=str(scope_id))


def settings_for(scope):
    title = scope.title[:150]
    try:
        row, _ = AssistantSettings.objects.get_or_create(source_type=scope.source_type, scope_id=scope.scope_id, defaults={'scope_title': title})
    except IntegrityError:
        row = AssistantSettings.objects.get(source_type=scope.source_type, scope_id=scope.scope_id)
    if row.scope_title != title:
        AssistantSettings.objects.filter(pk=row.pk).update(scope_title=title); row.scope_title = title
    return row


def settings_rows(scopes):
    rows = {}
    for source_type in {s.source_type for s in scopes}:
        ids = [s.scope_id for s in scopes if s.source_type == source_type]
        for row in AssistantSettings.objects.filter(source_type=source_type, scope_id__in=ids): rows[f'{source_type}:{row.scope_id}'] = row
    for scope in scopes:
        if scope.key not in rows or rows[scope.key].scope_title != scope.title[:150]: rows[scope.key] = settings_for(scope)
    return rows


def apply_fixed_mode(scope, row):
    # Answers already follow a mode fixed by the teacher; open conversations must show it too.
    if not row.allow_mode_choice:
        Conversation.objects.filter(source_type=scope.source_type, scope_id=scope.scope_id).exclude(mode=row.default_mode).update(mode=row.default_mode)


def chat_scopes(user):
    return [scope for provider in providers().values() for scope in provider.scopes_for(user)]


def managed_scopes(user):
    return [scope for provider in providers().values() for scope in provider.managed_scopes(user)]


def managed_scope(user, source_type, scope_id):
    provider = provider_for(source_type, 'source_type')
    return provider, provider.get_managed_scope(user, scope_id)


def chat_scope(user, conversation):
    """The conversation's scope if its owner may still send messages in it, else None."""
    provider = providers().get(conversation.source_type)
    if not provider: return None
    try: return provider.get_scope(user, conversation.scope_id)
    except NotFound: return None


def teachers_by_id(scopes):
    ids = {ObjectId(s.teacher_id) for s in scopes if ObjectId.is_valid(s.teacher_id)}
    return {str(u.pk): u for u in User.objects.filter(pk__in=list(ids))}


class SendAccess:
    """Which of the user's conversations still accept a question, computed once per request."""
    def __init__(self, user):
        self.keys = {s.key for s in chat_scopes(user)}
        disabled = set()
        for source_type in {k.split(':', 1)[0] for k in self.keys}:
            ids = [k.split(':', 1)[1] for k in self.keys if k.startswith(source_type + ':')]
            disabled.update(f'{source_type}:{i}' for i in AssistantSettings.objects.filter(source_type=source_type, scope_id__in=ids, enabled=False).values_list('scope_id', flat=True))
        self.keys -= disabled

    def __call__(self, conversation):
        return f'{conversation.source_type}:{conversation.scope_id}' in self.keys


def can_send(user, conversation):
    if conversation.status != Conversation.Status.ACTIVE: return False
    scope = chat_scope(user, conversation)
    return bool(scope) and settings_row(scope.source_type, scope.scope_id).enabled


def quiz_in_progress(user, scope):
    """Read-only adapter over the quizzes: expiry there is lazy, so deadlines are checked instead of trusting the status."""
    if user.role != 'STUDENT' or not scope.group_ids: return False
    from quizzes.models import Attempt
    now = timezone.now()
    window = now - timedelta(hours=settings.ASSISTANT_QUIZ_LOCK_HOURS)
    groups = [ObjectId(g) for g in scope.group_ids if ObjectId.is_valid(g)]
    return Attempt.objects.filter(student=user, status='IN_PROGRESS', learning_group_id__in=groups).filter(
        Q(deadline__gt=now) | Q(deadline__isnull=True, started_at__gt=window)).exists()


# Conversations ---------------------------------------------------------------------------------

def expired(conversation):
    return conversation.status == Conversation.Status.DELETED and conversation.purge_at and conversation.purge_at <= timezone.now()


def own_conversation(user, uid):
    try: conversation = get_object(Conversation, uid)
    except NotFound: conversation = None
    if not conversation or conversation.owner_id != user.pk or expired(conversation): raise NotFound('Conversation introuvable.')
    return conversation


def auto_title(question):
    text = ' '.join(question.split())
    if len(text) <= 60: return text
    cut = text[:61].rsplit(' ', 1)[0] if ' ' in text[:61] else text[:60]
    return cut[:60].rstrip(' ,;:.!?') + '…'


def create_conversation(user, data):
    source_type, scope_id = parse_scope_key(data['scope_key'])
    provider = provider_for(source_type)
    try: scope = provider.get_scope(user, scope_id)
    except NotFound: raise ValidationError({'scope_key': ['Sélectionnez un cours disponible.']})
    row = settings_for(scope)
    if not row.enabled: raise AssistantDisabled()
    mode = data.get('mode') or row.default_mode
    if mode != row.default_mode and not row.allow_mode_choice: raise ValidationError({'mode': [MODE_LOCKED]})
    title = data.get('title', '').strip()
    return Conversation.objects.create(owner=user, source_type=scope.source_type, scope_id=scope.scope_id, scope_title=scope.title[:150],
        title=title or DEFAULT_CONVERSATION_TITLE, title_is_custom=bool(title), mode=mode, last_message_at=mongo_now())


def pinned_count(user):
    return Conversation.objects.filter(owner=user, pinned=True).exclude(status=Conversation.Status.DELETED).count()


def too_many_pinned():
    return ValidationError({'pinned': [f'Vous pouvez épingler au plus {MAX_PINNED} conversations.']})


def update_conversation(user, conversation, data):
    if conversation.status == Conversation.Status.DELETED: raise ConversationLocked(TRASH_LOCKED)
    changes = {}
    if 'title' in data: changes.update(title=data['title'], title_is_custom=True)
    if 'mode' in data and data['mode'] != conversation.mode:
        if not settings_row(conversation.source_type, conversation.scope_id).allow_mode_choice: raise ValidationError({'mode': [MODE_LOCKED]})
        changes['mode'] = data['mode']
    if 'status' in data: changes['status'] = data['status']
    if 'pinned' in data: changes['pinned'] = data['pinned']
    if changes.get('pinned') is True and not conversation.pinned and pinned_count(user) >= MAX_PINNED: raise too_many_pinned()
    if changes:
        # Written only while out of the trash: a change based on a stale read must not bring a trashed conversation back.
        writable = Conversation.objects.filter(pk=conversation.pk, status__in=[Conversation.Status.ACTIVE, Conversation.Status.ARCHIVED])
        # Two pins sent at once both pass the count above: a new pin is written first and alone, and undone past the limit.
        if changes.get('pinned') is True and writable.filter(pinned=False).update(pinned=True, updated_at=mongo_now()) and pinned_count(user) > MAX_PINNED:
            Conversation.objects.filter(pk=conversation.pk).update(pinned=False)
            raise too_many_pinned()
        if not writable.update(updated_at=mongo_now(), **changes): raise ConversationLocked(TRASH_LOCKED)
        conversation.refresh_from_db()
    return conversation


def set_purge(conversation, purge_at):
    Message.objects.filter(conversation=conversation).update(purge_at=purge_at)
    AnswerFeedback.objects.filter(conversation=conversation).update(purge_at=purge_at)


def trash(conversation):
    if conversation.status == Conversation.Status.DELETED: return conversation
    now = mongo_now()
    purge_at = now + timedelta(days=TRASH_DAYS)
    def write():
        Conversation.objects.filter(pk=conversation.pk).update(status=Conversation.Status.DELETED, pinned=False, deleted_at=now, purge_at=purge_at, updated_at=now)
        set_purge(conversation, purge_at)
    atomic_write(write)
    conversation.refresh_from_db()
    return conversation


def restore(conversation):
    if conversation.status != Conversation.Status.DELETED: raise NotInTrash()
    def write():
        Conversation.objects.filter(pk=conversation.pk).update(status=Conversation.Status.ACTIVE, deleted_at=None, purge_at=None, updated_at=mongo_now())
        set_purge(conversation, None)
    atomic_write(write)
    conversation.refresh_from_db()
    return conversation


ORDERINGS = {'-last_message_at': ('-pinned', '-last_message_at', '-id'), '-created_at': ('-created_at', '-id'), 'title': ('title', 'id')}
STATUS_FILTERS = {'active': Conversation.Status.ACTIVE, 'archived': Conversation.Status.ARCHIVED, 'deleted': Conversation.Status.DELETED}


def choice_param(request, name, choices, default=None):
    value = request.query_params.get(name)
    if value in (None, ''): return default
    try: return ChoiceField(choices=list(choices)).run_validation(value)
    except ValidationError: raise ValidationError({name: ['Sélectionnez une valeur autorisée.']})


def bool_param(request, name):
    value = request.query_params.get(name)
    if value in (None, ''): return None
    if value not in ('true', 'false'): raise ValidationError({name: ['Envoyez true ou false.']})
    return value == 'true'


def filtered_conversations(request):
    user = request.user
    status = STATUS_FILTERS[choice_param(request, 'status', STATUS_FILTERS, 'active')]
    queryset = Conversation.objects.filter(owner=user, status=status)
    if status == Conversation.Status.DELETED: queryset = queryset.filter(purge_at__gt=timezone.now())
    q = request.query_params.get('q', '').strip()[:100]
    if q:
        ids = set(Message.objects.filter(owner=user, content__icontains=q).values_list('conversation_id', flat=True))
        queryset = queryset.filter(Q(title__icontains=q) | Q(pk__in=list(ids)))
    if request.query_params.get('scope'):
        source_type, scope_id = parse_scope_key(request.query_params['scope'], 'scope')
        queryset = queryset.filter(source_type=source_type, scope_id=scope_id)
    pinned = bool_param(request, 'pinned')
    if pinned is not None: queryset = queryset.filter(pinned=pinned)
    return queryset.order_by(*ORDERINGS[choice_param(request, 'ordering', ORDERINGS, '-last_message_at')])


def int_param(request, name, default, minimum, maximum):
    value = request.query_params.get(name)
    if value in (None, ''): return default
    if not re.fullmatch(r'[0-9]+', value) or not minimum <= int(value) <= maximum:
        raise ValidationError({name: [f'Saisissez un entier entre {minimum} et {maximum}.']})
    return int(value)


def message_page(request, conversation):
    size = int_param(request, 'limit', 30, 1, 100)
    queryset = Message.objects.filter(conversation=conversation, owner=conversation.owner_id)
    before = request.query_params.get('before')
    if before:
        try: anchor = get_object(Message, before)
        except NotFound: anchor = None
        if not anchor or anchor.conversation_id != conversation.pk: raise NotFound('Message introuvable.')
        queryset = queryset.filter(Q(created_at__lt=anchor.created_at) | Q(created_at=anchor.created_at, pk__lt=anchor.pk))
    items = list(queryset.order_by('-created_at', '-id')[:size + 1])
    return items[:size][::-1], len(items) > size


def feedback_by_message(messages):
    ids = [m.pk for m in messages if m.role == Message.Role.ASSISTANT]
    return {f.message_id: f for f in AnswerFeedback.objects.filter(message_id__in=ids)} if ids else {}


# Ask flow --------------------------------------------------------------------------------------

def atomic_write(function):
    """Short write transaction, retried on write conflicts; never wraps a provider call."""
    for attempt in range(3):
        try:
            with transaction.atomic():
                return function()
        except IntegrityError:
            raise
        except DatabaseError:
            if attempt == 2: raise Conflict()


def replayed_pair(conversation, client_id):
    question = Message.objects.filter(conversation=conversation, has_client_id=True, client_id=client_id).first()
    if not question: return None
    answer = Message.objects.filter(conversation=conversation, reply_to=question).first()
    if not answer: raise AnswerInProgress()
    return question, answer


def ensure_open(conversation):
    if conversation.status == Conversation.Status.ARCHIVED: raise ConversationLocked()
    if conversation.status == Conversation.Status.DELETED: raise ConversationLocked(TRASH_LOCKED)


def save_question(conversation, user, content, input_mode, client_id):
    def write():
        now = mongo_now()
        # The status is checked again inside the transaction: the conversation may have been archived or trashed since it was read,
        # and a question saved into the trash would escape its purge.
        if not Conversation.objects.filter(pk=conversation.pk, status=Conversation.Status.ACTIVE).update(
                message_count=F('message_count') + 1, last_message_at=now, updated_at=now):
            current = Conversation.objects.filter(pk=conversation.pk).first()
            if not current: raise NotFound('Conversation introuvable.')
            raise ConversationLocked() if current.status == Conversation.Status.ARCHIVED else ConversationLocked(TRASH_LOCKED)
        return Message.objects.create(conversation=conversation, owner=user, source_type=conversation.source_type, scope_id=conversation.scope_id,
            role=Message.Role.USER, content=content, input_mode=input_mode, client_id=client_id or None, has_client_id=bool(client_id))
    return atomic_write(write)


def save_answer(conversation, question, **fields):
    def write():
        now = mongo_now()
        purge_at = Conversation.objects.filter(pk=conversation.pk).values_list('purge_at', flat=True).first()
        answer = Message.objects.create(conversation=conversation, owner_id=question.owner_id, source_type=conversation.source_type,
            scope_id=conversation.scope_id, role=Message.Role.ASSISTANT, reply_to=question, purge_at=purge_at, **fields)
        Conversation.objects.filter(pk=conversation.pk).update(message_count=F('message_count') + 1, last_message_at=now, updated_at=now)
        Conversation.objects.filter(pk=conversation.pk, title_is_custom=False, title=DEFAULT_CONVERSATION_TITLE).update(title=auto_title(question.content))
        return answer
    return atomic_write(write)


def recent_history(conversation):
    """The last answered exchanges, oldest first, as question/answer pairs."""
    recent = list(Message.objects.filter(conversation=conversation).order_by('-created_at', '-id')[:12])[::-1]
    questions = {m.pk: m for m in recent if m.role == Message.Role.USER}
    history = []
    for message in recent:
        if message.role == Message.Role.ASSISTANT and message.status in (Message.Status.COMPLETE, Message.Status.OUT_OF_SCOPE) and message.reply_to_id in questions:
            history += [questions[message.reply_to_id], message]
    return history[-6:]


def ask(request, conversation, data):
    """Returns (question, answer, replayed)."""
    started = time.monotonic()
    user = request.user
    client_id = data.get('client_id')
    if client_id:
        pair = replayed_pair(conversation, client_id)
        if pair: return pair[0], pair[1], True
    ensure_open(conversation)
    scope = chat_scope(user, conversation)
    if not scope: raise ScopeUnavailable()
    row = settings_for(scope)
    if not row.enabled: raise AssistantDisabled()
    if row.block_during_quiz and quiz_in_progress(user, scope): raise QuizInProgress()
    provider = providers()[scope.source_type]
    index = ensure_index(provider, scope.scope_id)
    previous = Message.objects.filter(conversation=conversation, role=Message.Role.USER).order_by('-created_at', '-id').values_list('content', flat=True).first() or ''
    history = recent_history(conversation)
    retrieval_started = time.monotonic()
    hits = retrieve(scope.source_type, scope.scope_id, index.content_version, data['content'], previous)
    if not hits and is_overview_question(data['content']):
        hits = overview_hits(scope.source_type, scope.scope_id)
    retrieval_ms = int((time.monotonic() - retrieval_started) * 1000)
    quota_used = bool(hits)
    if quota_used: consume_question(request, scope, row)
    try:
        question = save_question(conversation, user, data['content'], data.get('input_mode') or Message.InputMode.TEXT, client_id)
    except (IntegrityError, APIException) as exc:
        # The question was not saved, so it is not counted.
        if quota_used:
            refund_question(user, scope); refund('assistant-global', 'global', DAY)
        if not isinstance(exc, IntegrityError): raise
        # Same client_id sent twice at once: the other request owns the answer.
        pair = replayed_pair(conversation, client_id)
        if not pair: raise Conflict()
        return pair[0], pair[1], True
    metrics = {'retrieval_ms': retrieval_ms, 'top_score': hits[0].score if hits else None}
    if not hits:
        answer = save_answer(conversation, question, content=OUT_OF_SCOPE_MESSAGE, status=Message.Status.OUT_OF_SCOPE,
            latency_ms=int((time.monotonic() - started) * 1000), **metrics)
        log_answer(answer)
        return question, answer, False
    mode = conversation.mode if row.allow_mode_choice else row.default_mode
    system, contents, used = build_prompt(scope.title, mode, history, hits, data['content'])
    try:
        result = generate_answer(system, contents, answer_schema())
    except LLMError as exc:
        # Only a request no model processed is given back, to the student and to the shared budget. Any other failure may
        # come from the question itself (a reply cut by the token limit, a blocked request): giving it back would make
        # such questions free and unlimited.
        if exc.code in UNSERVED_ERRORS:
            refund_question(user, scope); refund('assistant-global', 'global', DAY)
        answer = save_answer(conversation, question, content=exc.message, status=Message.Status.BLOCKED if exc.code == 'blocked' else Message.Status.FAILED,
            error_code=exc.code, provider=exc.provider, model_name=exc.model or '', chunks_used=len(used),
            latency_ms=int((time.monotonic() - started) * 1000), **metrics)
        log_answer(answer)
        return question, answer, False
    content, citations, follow_ups, unsourced, out_of_scope = parse_answer(result.data, used)
    answer = save_answer(conversation, question, content=content, citations=citations, follow_ups=follow_ups, unsourced=unsourced,
        status=Message.Status.OUT_OF_SCOPE if out_of_scope else Message.Status.COMPLETE, provider=result.provider, model_name=result.model,
        prompt_tokens=result.prompt_tokens, output_tokens=result.output_tokens, chunks_used=len(used),
        latency_ms=int((time.monotonic() - started) * 1000), **metrics)
    log_answer(answer)
    return question, answer, False


def refund_question(user, scope):
    refund('assistant-question', question_identity(user, scope.source_type, scope.scope_id), DAY)


def log_answer(answer):
    # Identifiers and measurements only: questions and answers stay out of the logs.
    logger.info('assistant answer message=%s conversation=%s scope=%s:%s status=%s provider=%s model=%s latency_ms=%s retrieval_ms=%s '
        'prompt_tokens=%s output_tokens=%s top_score=%s chunks=%s citations=%s error=%s', answer.pk, answer.conversation_id,
        answer.source_type, answer.scope_id, answer.status, answer.provider or '-', answer.model_name or '-', answer.latency_ms,
        answer.retrieval_ms, answer.prompt_tokens, answer.output_tokens, answer.top_score, answer.chunks_used, len(answer.citations or []),
        answer.error_code or '-')


# Feedback and reviews --------------------------------------------------------------------------

def own_message(user, uid):
    try: message = get_object(Message, uid)
    except NotFound: message = None
    if not message or message.owner_id != user.pk: raise NotFound('Message introuvable.')
    return message, own_conversation(user, message.conversation_id)


def put_feedback(user, message, conversation, data):
    if message.role != Message.Role.ASSISTANT: raise ValidationError({'detail': 'Seules les réponses de l’assistant peuvent être évaluées.'})
    if message.status == Message.Status.FAILED: raise ValidationError({'detail': 'Une réponse en échec ne peut pas être évaluée : posez de nouveau la question.'})
    if conversation.status == Conversation.Status.DELETED: raise ConversationLocked(TRASH_LOCKED)
    values = {'rating': data['rating'], 'reasons': data.get('reasons', []), 'comment': data.get('comment', '').strip(),
        'shared_with_teacher': data.get('shared_with_teacher', False)}
    for attempt in range(2):
        existing = AnswerFeedback.objects.filter(message=message).first()
        if existing:
            if not AnswerFeedback.objects.filter(pk=existing.pk, status=AnswerFeedback.Status.NEW).update(updated_at=mongo_now(), **values):
                raise AlreadyReviewed()
            break
        try:
            AnswerFeedback.objects.create(message=message, conversation=conversation, student=user, source_type=message.source_type,
                scope_id=message.scope_id, purge_at=conversation.purge_at, **values)
            break
        except IntegrityError:
            if attempt: raise Conflict()
    return AnswerFeedback.objects.get(message=message)


def delete_feedback(message):
    feedback = AnswerFeedback.objects.filter(message=message).first()
    if not feedback: raise NotFound('Aucun retour sur cette réponse.')
    deleted, _ = AnswerFeedback.objects.filter(pk=feedback.pk, status=AnswerFeedback.Status.NEW).delete()
    if not deleted: raise AlreadyReviewed()


def scope_filter(user):
    """Feedback of the scopes this manager follows; None means every scope (administrator)."""
    if user.role == 'ADMIN': return None
    query, scopes = None, managed_scopes(user)
    for source_type in {s.source_type for s in scopes}:
        part = Q(source_type=source_type, scope_id__in=[s.scope_id for s in scopes if s.source_type == source_type])
        query = part if query is None else query | part
    return query if query is not None else Q(pk__in=[])


def review_queryset(user):
    queryset = AnswerFeedback.objects.filter(shared_with_teacher=True)
    query = scope_filter(user)
    return queryset if query is None else queryset.filter(query)


def filtered_reviews(request):
    queryset = review_queryset(request.user)
    status = choice_param(request, 'status', AnswerFeedback.Status.values)
    if status: queryset = queryset.filter(status=status)
    if request.query_params.get('scope'):
        source_type, scope_id = parse_scope_key(request.query_params['scope'], 'scope')
        queryset = queryset.filter(source_type=source_type, scope_id=scope_id)
    queryset = queryset.order_by('-created_at', '-id')
    reason = choice_param(request, 'reason', AnswerFeedback.Reason.values)
    if not reason: return queryset
    # Reasons live in a JSON list, which the MongoDB backend cannot filter reliably: only ids and reasons are read to pick them.
    ids = [pk for pk, reasons in queryset.values_list('id', 'reasons') if reason in (reasons or [])]
    return AnswerFeedback.objects.filter(pk__in=ids).order_by('-created_at', '-id')


def managed_review(user, uid):
    try: feedback = get_object(AnswerFeedback, uid)
    except NotFound: feedback = None
    if not feedback or not review_queryset(user).filter(pk=feedback.pk).exists(): raise NotFound('Retour introuvable.')
    return feedback


def review_parts(feedback):
    answer = Message.objects.filter(pk=feedback.message_id).first()
    question = Message.objects.filter(pk=answer.reply_to_id).first() if answer and answer.reply_to_id else None
    scope_title = Conversation.objects.filter(pk=feedback.conversation_id).values_list('scope_title', flat=True).first() \
        or settings_row(feedback.source_type, feedback.scope_id).scope_title
    return question, answer, scope_title


REVIEW_STATUSES = {'CONFIRM': AnswerFeedback.Status.CONFIRMED, 'CORRECT': AnswerFeedback.Status.CORRECTED, 'DISMISS': AnswerFeedback.Status.DISMISSED}


def apply_review(user, feedback, data):
    now = mongo_now()
    note = data['correction'].strip() if data['action'] == 'CORRECT' else data.get('note', '').strip()
    changed = AnswerFeedback.objects.filter(pk=feedback.pk, status=AnswerFeedback.Status.NEW).update(
        status=REVIEW_STATUSES[data['action']], teacher_note=note, reviewed_by=user, reviewed_at=now, updated_at=now)
    if not changed: raise AlreadyReviewed('Ce retour a déjà été traité.')
    if data['action'] == 'CORRECT':
        # Every student of the scope can read a validated answer: it carries the question as the teacher chose to publish it,
        # never a copy of the student's text made here. The scope's content version includes validated answers, so the next
        # question rebuilds the index with it.
        ValidatedAnswer.objects.create(source_type=feedback.source_type, scope_id=feedback.scope_id,
            question=data.get('question', '').strip(), answer=note, teacher=user, feedback=feedback)
    feedback.refresh_from_db()
    return feedback


# Teacher notes ---------------------------------------------------------------------------------

def manager_notes(user):
    if user.role == 'ADMIN': return TeacherNote.objects.all()
    return TeacherNote.objects.filter(group_id__in=list(LearningGroup.objects.filter(teacher=user).values_list('id', flat=True)))


def managed_note(user, uid):
    try: note = get_object(TeacherNote, uid)
    except NotFound: note = None
    if not note or (user.role != 'ADMIN' and note.group.teacher_id != user.pk): raise NotFound('Note introuvable.')
    return note


def note_group(user, uid, field='group_id'):
    try: group = get_object(LearningGroup, uid)
    except NotFound: group = None
    if not group or (user.role != 'ADMIN' and group.teacher_id != user.pk):
        raise ValidationError({field: ['Sélectionnez un de vos groupes.']})
    return group


def note_errors(note):
    try: note.full_clean(validate_unique=False, validate_constraints=False)
    except ModelValidationError as exc:
        errors = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
        raise ValidationError({('group_id' if k == 'group' else k): v for k, v in errors.items()})


def filtered_notes(request):
    queryset = manager_notes(request.user)
    if request.query_params.get('group'):
        group = get_object(LearningGroup, request.query_params['group'])
        if request.user.role != 'ADMIN' and group.teacher_id != request.user.pk: raise NotFound('Ressource introuvable.')
        queryset = queryset.filter(group=group)
    q = request.query_params.get('q', '').strip()[:100]
    if q: queryset = queryset.filter(title__icontains=q)
    return queryset.order_by('-updated_at', '-id')


# Export ----------------------------------------------------------------------------------------

def local(value):
    return timezone.localtime(value).strftime('%d/%m/%Y à %H:%M')


def source_line(citation):
    parts = [citation.source_title]
    if citation.chapter_title and citation.chapter_title != citation.source_title: parts.append(citation.chapter_title)
    if citation.page: parts.append(f'page {citation.page}')
    elif citation.start_seconds is not None: parts.append(f'à {timestamp(citation.start_seconds)}')
    return ' — '.join(parts)


def export_markdown(conversation):
    messages = list(Message.objects.filter(conversation=conversation, owner=conversation.owner_id).order_by('created_at', 'id'))
    answers = {m.reply_to_id: m for m in messages if m.role == Message.Role.ASSISTANT}
    lines = [f'# {conversation.title}', '', f'- Cours : {conversation.scope_title}', f'- Mode : {Mode(conversation.mode).label}',
        f'- Créée le {local(conversation.created_at)}', f'- Exportée le {local(timezone.now())}', '']
    for number, question in enumerate((m for m in messages if m.role == Message.Role.USER), 1):
        lines += [f'## Question {number}', '', question.content, '']
        answer = answers.get(question.pk)
        if not answer:
            lines += ['_Aucune réponse enregistrée._', '']; continue
        status = '' if answer.status == Message.Status.COMPLETE else f' ({Message.Status(answer.status).label})'
        lines += [f'### Réponse{status}', '', answer.content, '']
        if answer.unsourced: lines += ['_Réponse non sourcée._', '']
        if answer.citations:
            lines += ['Sources :', ''] + [f'{c.number}. {source_line(c)}' for c in answer.citations] + ['']
    return '\n'.join(lines).rstrip() + '\n'
