"""Answer generation behind one function: disabled (default), a deterministic fake, or Gemini over its REST API."""
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from django.conf import settings
from django.db import connection

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
BLOCKED_FINISH_REASONS = {'SAFETY', 'PROHIBITED_CONTENT', 'BLOCKLIST', 'SPII', 'IMAGE_SAFETY'}

MESSAGES = {
    'disabled': 'L’assistant n’est pas encore configuré sur ce serveur. Prévenez l’administrateur.',
    'quota': 'Le service d’IA a atteint sa limite d’utilisation. Réessayez plus tard.',
    'unavailable': 'Le service d’IA est momentanément indisponible. Réessayez dans un instant.',
    'auth': 'L’assistant n’est pas correctement configuré : la clé d’accès au service d’IA est refusée. Prévenez l’administrateur.',
    'blocked': 'Je ne peux pas répondre à cette demande. Reformulez votre question en lien avec le cours.',
    'invalid_response': 'La réponse générée était invalide. Réessayez.',
    'refused': 'Le service d’IA a refusé la demande. Reformulez votre question.',
}
RETRYABLE = {'quota', 'unavailable', 'invalid_response'}


class LLMError(Exception):
    def __init__(self, code, message=None, retryable=None, model=''):
        self.code = code
        self.message = message or MESSAGES[code]
        self.retryable = code in RETRYABLE if retryable is None else retryable
        self.model = model
        self.provider = ''
        self.latency_ms = None
        super().__init__(self.message)


@dataclass
class LLMResult:
    data: dict
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    output_tokens: int | None = None


def answer_schema():
    return {'type': 'OBJECT', 'properties': {
        'answer': {'type': 'STRING'},
        'out_of_scope': {'type': 'BOOLEAN'},
        'follow_ups': {'type': 'ARRAY', 'items': {'type': 'STRING'}, 'maxItems': 3},
    }, 'required': ['answer', 'out_of_scope'], 'propertyOrdering': ['answer', 'out_of_scope', 'follow_ups']}


def checked(data, model=''):
    if not isinstance(data, dict) or not isinstance(data.get('answer'), str) or not isinstance(data.get('out_of_scope'), bool):
        raise LLMError('invalid_response', model=model)
    follow_ups = data.get('follow_ups') or []
    if not isinstance(follow_ups, list): follow_ups = []
    answer = data['answer'].strip()
    if not answer and not data['out_of_scope']: raise LLMError('invalid_response', model=model)
    return {'answer': answer, 'out_of_scope': data['out_of_scope'], 'follow_ups': [f for f in follow_ups if isinstance(f, str)]}


def last_user_text(contents):
    for content in reversed(contents):
        if content.get('role') == 'user':
            return '\n'.join(part.get('text', '') for part in content.get('parts', []))
    return ''


class FakeProvider:
    """Deterministic answers for tests and browser scenarios; markers in the question select the failure paths."""
    name = 'fake'
    model = 'fake-gemini'

    def generate(self, system, contents, schema, max_output_tokens):
        text = last_user_text(contents)
        question = text.rsplit('QUESTION:\n', 1)[-1]
        if '#lent' in question: time.sleep(2)
        if '#erreur' in question: raise LLMError('unavailable', model=self.model)
        if '#quota' in question: raise LLMError('quota', model=self.model)
        if '#bloque' in question: raise LLMError('blocked', model=self.model)
        if '#horscours' in question:
            data = {'answer': 'Les extraits du cours ne traitent pas de cette question.', 'out_of_scope': True, 'follow_ups': []}
        else:
            excerpt = re.search(r'\[S1\][^\n]*\n(.+?)(?:\n\n\[S\d+\]|\n\nQUESTION:|\Z)', text, re.S)
            body = ' '.join(excerpt.group(1).split()) if excerpt else ''
            sentence = re.split(r'(?<=[.!?])\s', body, maxsplit=1)[0][:400] if body else 'Le cours ne donne pas de détail à ce sujet.'
            data = {'answer': f'D’après le cours : {sentence} [S1]', 'out_of_scope': False,
                'follow_ups': ['Peux-tu donner un exemple ?', 'Quels sont les points essentiels à retenir ?']}
        prompt_tokens = (len(system) + sum(len(p.get('text', '')) for c in contents for p in c.get('parts', []))) // 4
        return data, self.model, prompt_tokens, len(data['answer']) // 4


class GeminiProvider:
    name = 'gemini'

    @property
    def model(self):
        return settings.GEMINI_MODEL

    def post(self, model, body):
        request = urllib.request.Request(GEMINI_URL.format(model=model), data=json.dumps(body).encode('utf-8'), method='POST',
            headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'x-goog-api-key': settings.GEMINI_API_KEY})
        with urllib.request.urlopen(request, timeout=settings.GEMINI_TIMEOUT_SECONDS) as response:
            return response.read(MAX_RESPONSE_BYTES)

    def call(self, model, body):
        try:
            raw = self.post(model, body)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status == 429: raise LLMError('quota', model=model)
            if status in (401, 403): raise LLMError('auth', model=model)
            if status == 408 or status >= 500: raise LLMError('unavailable', model=model)
            raise LLMError('refused', model=model)
        # A reply cut off mid-body raises http.client errors, which are not OSError.
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError):
            raise LLMError('unavailable', model=model)
        try: return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError): raise LLMError('invalid_response', model=model)

    def parse(self, payload, model):
        if not isinstance(payload, dict): raise LLMError('invalid_response', model=model)
        if (payload.get('promptFeedback') or {}).get('blockReason'): raise LLMError('blocked', model=model)
        candidates = payload.get('candidates') or []
        if not candidates or not isinstance(candidates[0], dict): raise LLMError('invalid_response', model=model)
        candidate = candidates[0]
        if candidate.get('finishReason') in BLOCKED_FINISH_REASONS: raise LLMError('blocked', model=model)
        parts = (candidate.get('content') or {}).get('parts') or []
        text = ''.join(p.get('text', '') for p in parts if isinstance(p, dict) and not p.get('thought'))
        try: data = json.loads(text)
        except ValueError: raise LLMError('invalid_response', model=model)
        usage = payload.get('usageMetadata') or {}
        return data, usage.get('promptTokenCount'), usage.get('candidatesTokenCount')

    def generate(self, system, contents, schema, max_output_tokens):
        # Test databases must never reach the real service.
        if str(connection.settings_dict['NAME']).startswith('test_'):
            raise LLMError('disabled', 'Le fournisseur Gemini réel est désactivé sur une base de test.')
        if not settings.GEMINI_API_KEY: raise LLMError('disabled')
        # Sampling parameters are left out: Gemini 3.6 and later ignore them.
        body = {'systemInstruction': {'parts': [{'text': system}]}, 'contents': contents,
            'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': schema, 'maxOutputTokens': max_output_tokens}}
        models = [settings.GEMINI_MODEL]
        if settings.GEMINI_FALLBACK_MODEL and settings.GEMINI_FALLBACK_MODEL != settings.GEMINI_MODEL:
            models.append(settings.GEMINI_FALLBACK_MODEL)
        for position, model in enumerate(models):
            try:
                payload = self.call(model, body)
            except LLMError as exc:
                # The fallback model has its own free-tier quota.
                if exc.code == 'quota' and position + 1 < len(models): continue
                raise
            data, prompt_tokens, output_tokens = self.parse(payload, model)
            return data, model, prompt_tokens, output_tokens


class DisabledProvider:
    name = 'disabled'
    model = ''

    def generate(self, system, contents, schema, max_output_tokens):
        raise LLMError('disabled')


PROVIDERS = {'disabled': DisabledProvider, 'fake': FakeProvider, 'gemini': GeminiProvider}


def get_provider():
    return PROVIDERS.get(settings.ASSISTANT_LLM_PROVIDER, DisabledProvider)()


def generate_answer(system, contents, schema, *, max_output_tokens=2048):
    provider = get_provider()
    started = time.monotonic()
    try:
        data, model, prompt_tokens, output_tokens = provider.generate(system, contents, schema, max_output_tokens)
        data = checked(data, model)
    except LLMError as exc:
        exc.model, exc.provider = exc.model or provider.model, provider.name
        exc.latency_ms = int((time.monotonic() - started) * 1000)
        raise
    return LLMResult(data, provider.name, model, int((time.monotonic() - started) * 1000), prompt_tokens, output_tokens)


def provider_status():
    name = settings.ASSISTANT_LLM_PROVIDER if settings.ASSISTANT_LLM_PROVIDER in PROVIDERS else 'disabled'
    configured = {'disabled': False, 'fake': True, 'gemini': bool(settings.GEMINI_API_KEY)}[name]
    model = {'disabled': '', 'fake': FakeProvider.model, 'gemini': settings.GEMINI_MODEL}[name]
    return {'provider': name, 'configured': configured, 'model': model,
        'fallback_model': settings.GEMINI_FALLBACK_MODEL if name == 'gemini' else ''}
