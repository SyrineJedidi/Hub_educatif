import http.client
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
BLOCKED_FINISH_REASONS = {'SAFETY', 'PROHIBITED_CONTENT', 'BLOCKLIST', 'SPII'}
RETRYABLE = {'quota', 'unavailable'}
MESSAGES = {
    'disabled': 'L’IA n’est pas configurée sur ce serveur.',
    'quota': 'Le quota du service IA est atteint. Réessayez plus tard.',
    'unavailable': 'Le service IA ne répond pas pour le moment.',
    'auth': 'Clé Gemini invalide ou projet non autorisé.',
    'blocked': 'Le service IA a bloqué cette demande.',
    'invalid_response': 'La réponse du service IA est inexploitable.',
    'refused': 'Le service IA a refusé la demande.',
}


@dataclass
class GeminiResult:
    data: dict
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int | None
    output_tokens: int | None


class GeminiError(Exception):
    """Provider failure with a French message that is safe to show to users."""
    def __init__(self, code, message=None, retryable=None):
        self.code = code
        self.message = message or MESSAGES.get(code, MESSAGES['unavailable'])
        self.retryable = code in RETRYABLE if retryable is None else retryable
        super().__init__(self.message)


def string_schema(description=None):
    return {'type': 'STRING', **({'description': description} if description else {})}


def array_schema(items, max_items=None):
    return {'type': 'ARRAY', 'items': items, **({'maxItems': max_items} if max_items else {})}


def object_schema(properties, required=()):
    return {'type': 'OBJECT', 'properties': properties, 'required': list(required)}


def elapsed_ms(started):
    return max(0, round((time.monotonic() - started) * 1000))


def token_count(value):
    return value if type(value) is int and value >= 0 else None


def failure(model, code, status=None):
    # Only the error class is logged: never the key, the prompt or the provider body.
    logger.warning('Gemini %s: %s%s', model, code, f' (HTTP {status})' if status else '')
    return GeminiError(code)


def http_error(status):
    if status == 429: return 'quota'
    if status in (401, 403): return 'auth'
    if status >= 500: return 'unavailable'
    return 'refused'


def parse(payload, model, latency):
    if not isinstance(payload, dict): raise failure(model, 'invalid_response')
    feedback = payload.get('promptFeedback')
    if isinstance(feedback, dict) and feedback.get('blockReason'): raise failure(model, 'blocked')
    candidates = payload.get('candidates')
    candidate = candidates[0] if isinstance(candidates, list) and candidates else None
    if not isinstance(candidate, dict): raise failure(model, 'invalid_response')
    if candidate.get('finishReason') in BLOCKED_FINISH_REASONS: raise failure(model, 'blocked')
    content = candidate.get('content') if isinstance(candidate.get('content'), dict) else {}
    parts = content.get('parts') if isinstance(content.get('parts'), list) else []
    text = ''.join(part['text'] for part in parts
        if isinstance(part, dict) and not part.get('thought') and isinstance(part.get('text'), str))
    try: data = json.loads(text)
    except ValueError: raise failure(model, 'invalid_response') from None
    if not isinstance(data, dict): raise failure(model, 'invalid_response')
    usage = payload.get('usageMetadata') if isinstance(payload.get('usageMetadata'), dict) else {}
    return GeminiResult(data, 'gemini', model, latency, token_count(usage.get('promptTokenCount')), token_count(usage.get('candidatesTokenCount')))


def post(model, body):
    request = urllib.request.Request(ENDPOINT.format(model=urllib.parse.quote(model, safe='')),
        data=json.dumps(body).encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json', 'x-goog-api-key': settings.GEMINI_API_KEY})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=settings.GEMINI_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise failure(model, http_error(exc.code), exc.code) from None
    except (urllib.error.URLError, http.client.HTTPException, OSError):
        raise failure(model, 'unavailable') from None
    latency = elapsed_ms(started)
    try: payload = json.loads(raw.decode('utf-8'))
    except ValueError: raise failure(model, 'invalid_response') from None
    return parse(payload, model, latency)


def generate_json(system, prompt, schema, *, fake=None, max_output_tokens=8192):
    provider = settings.GEMINI_PROVIDER
    if provider == 'fake':
        started = time.monotonic()
        data = fake() if callable(fake) else {}
        if not isinstance(data, dict): raise GeminiError('invalid_response')
        return GeminiResult(data, 'fake', 'fake', elapsed_ms(started), None, None)
    if provider != 'gemini' or not settings.GEMINI_API_KEY: raise GeminiError('disabled')
    # A test run must never reach the network nor spend the shared free-tier quota.
    if str(connection.settings_dict.get('NAME') or '').startswith('test_'):
        raise GeminiError('disabled', 'Le fournisseur Gemini réel est désactivé sur une base de test.')
    # Sampling parameters are deliberately absent: they are deprecated on recent Gemini models.
    body = {
        'systemInstruction': {'parts': [{'text': system}]},
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': schema, 'maxOutputTokens': max_output_tokens},
    }
    try:
        return post(settings.GEMINI_MODEL, body)
    except GeminiError as exc:
        fallback = settings.GEMINI_FALLBACK_MODEL
        # Each model has its own free-tier quota, so one retry on the fallback model is worth it.
        if exc.code != 'quota' or not fallback or fallback == settings.GEMINI_MODEL: raise
        return post(fallback, body)
