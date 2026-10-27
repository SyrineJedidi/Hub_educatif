"""Server-side clients for Gemini (summaries) and Hugging Face (illustrations).

Keys never leave Django. Both clients use the standard library only and raise
DRF exceptions with French messages so the frontend can display them as-is.
"""
import json
import re
import time
import urllib.error
import urllib.request
from django.conf import settings
from rest_framework.exceptions import APIException
from .metrics import LENGTH_TARGETS, target_words


class AIUnavailable(APIException):
    status_code = 503
    default_detail = 'Le service d’intelligence artificielle n’est pas configuré sur ce serveur.'
    default_code = 'ai_unavailable'


class AIServiceError(APIException):
    status_code = 502
    default_detail = 'Le service d’intelligence artificielle n’a pas pu répondre. Réessayez dans un instant.'
    default_code = 'ai_error'


LENGTH_GUIDE = {
    'SHORT': 'un résumé synthétique de 150 à 250 mots et 4 à 6 points clés',
    'STANDARD': 'un résumé structuré de 350 à 550 mots et 6 à 9 points clés',
    'DETAILED': 'un résumé approfondi de 700 à 1000 mots et 8 à 12 points clés',
}

SUMMARY_INSTRUCTIONS = """Tu es un assistant pédagogique francophone qui rédige des fiches de révision pour des étudiants.
Règles :
- Appuie-toi uniquement sur le contenu fourni ; n'invente ni chiffres, ni dates, ni références.
- Rédige en français clair, avec des phrases courtes et un ton neutre.
- Un résumé condense : s'il est court, reste nettement plus bref que le contenu fourni, même sous la longueur demandée.
- Le champ "summary" utilise un Markdown limité : titres "## ", listes "- ", gras "**texte**". Aucun lien, tableau, image ni HTML.
- "key_points" contient des phrases autonomes à retenir, sans puce.
- "glossary" définit les notions essentielles du cours (au plus 10 entrées).
- "tags" propose 2 à 5 mots-clés courts en minuscules.
- "illustration_prompt" décrit en anglais une illustration pédagogique sans texte qui aiderait à comprendre la notion centrale."""

SUMMARY_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'summary': {'type': 'STRING'},
        'key_points': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'glossary': {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
            'term': {'type': 'STRING'}, 'definition': {'type': 'STRING'}}, 'required': ['term', 'definition']}},
        'tags': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'illustration_prompt': {'type': 'STRING'},
    },
    'required': ['summary', 'key_points', 'glossary', 'tags', 'illustration_prompt'],
}

STYLE_PROMPTS = {
    'SCHEMA': 'clean educational diagram, labeled-free infographic style, flat vector shapes, white background',
    'FLAT': 'modern flat design illustration, soft pastel palette, minimal shapes, friendly educational style',
    'REALISTIC': 'high quality realistic educational photograph, natural light, sharp focus',
    'WATERCOLOR': 'delicate watercolor illustration, soft textures, educational book style',
}


RETRY_DELAYS = (2, 5)
HTTP_ERRORS = {
    401: 'La clé du service IA est refusée. Vérifiez la configuration du serveur.',
    403: 'La clé du service IA est refusée. Vérifiez la configuration du serveur.',
    402: 'Le quota du service IA est épuisé. Réessayez plus tard ou ajoutez des crédits au compte.',
    404: 'Le modèle IA configuré n’est plus disponible. Mettez à jour REVISIONS_GEMINI_MODEL ou HF_IMAGE_MODEL dans backend/.env.',
    410: 'Le modèle IA configuré n’est plus disponible. Mettez à jour REVISIONS_GEMINI_MODEL ou HF_IMAGE_MODEL dans backend/.env.',
    429: 'Le service IA reçoit trop de demandes. Patientez une minute puis réessayez.',
    503: 'Le service IA est momentanément surchargé. Réessayez dans quelques instants.',
}


def _post(url, headers, payload, timeout=None):
    return _http(url, headers, payload, timeout)


def _get(url, headers, timeout=None):
    return _http(url, headers, None, timeout)


def _http(url, headers, payload, timeout):
    if payload is None: request = urllib.request.Request(url, headers=headers)
    else: request = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST',
        headers={'Content-Type': 'application/json', **headers})
    # Overloaded (503) and rate-limited (429) answers are frequent on free tiers and
    # usually transient: retry twice before reporting the error to the user.
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout or settings.AI_TIMEOUT_SECONDS) as response:
                return response.read(), response.headers.get('Content-Type', '')
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt]); continue
            raise AIServiceError(HTTP_ERRORS.get(exc.code, AIServiceError.default_detail))
        except (urllib.error.URLError, TimeoutError, OSError):
            raise AIServiceError('Le service IA ne répond pas. Vérifiez la connexion du serveur puis réessayez.')


def _clean_list(values, limit, size):
    if not isinstance(values, list): return []
    return [' '.join(str(v).split())[:size] for v in values if isinstance(v, str) and v.strip()][:limit]


def _prompt(text, title, course, length):
    # The target adapts to the source: a summary of a short extract must stay shorter than it.
    low, high = target_words(length, len(text.split()))
    points = f'{LENGTH_TARGETS[length][2]} à {LENGTH_TARGETS[length][3]}'
    return (f'Fiche : {title}\nCours : {course}\n'
            f'Produis {LENGTH_GUIDE[length].split(" de ")[0]} de {low} à {high} mots (sans dépasser cette limite) et {points} points clés.\n\n'
            f'Contenu du cours :\n"""\n{text}\n"""')


def _clean_summary(result, engine):
    if not isinstance(result, dict): raise AIServiceError(f'La réponse de {engine} est incomplète. Relancez la génération.')
    summary = result.get('summary') if isinstance(result.get('summary'), str) else ''
    # Models sometimes double-escape line breaks inside the JSON string.
    if '\\n' in summary and summary.count('\n') < summary.count('\\n'):
        summary = summary.replace('\\r', '').replace('\\n', '\n')
    if not summary.strip(): raise AIServiceError(f'{engine} n’a pas produit de résumé exploitable. Relancez la génération.')
    glossary, seen = [], set()
    for entry in result.get('glossary') or []:
        if not isinstance(entry, dict): continue
        term = ' '.join(str(entry.get('term', '')).split())[:80]
        definition = str(entry.get('definition', '')).strip()[:400]
        if term and definition and term.casefold() not in seen:
            seen.add(term.casefold()); glossary.append({'term': term, 'definition': definition})
    prompt_hint = result.get('illustration_prompt') if isinstance(result.get('illustration_prompt'), str) else ''
    return {
        'summary': summary.strip()[:20000],
        'key_points': _clean_list(result.get('key_points'), 15, 300),
        'glossary': glossary[:20],
        'tags': [t.lower().lstrip('#') for t in _clean_list(result.get('tags'), 5, 30)],
        'illustration_prompt': ' '.join(prompt_hint.split())[:600],
    }


def gemini_models():
    """The configured model, then a lighter one: each has its own free quota, and it answers in seconds
    where the local model needs about a minute."""
    return list(dict.fromkeys(m for m in (settings.REVISIONS_GEMINI_MODEL, settings.REVISIONS_GEMINI_FALLBACK_MODEL) if m))


def gemini_summary(text, *, title, course, length):
    """Return a dict {summary, key_points, glossary, tags, illustration_prompt, model, duration_ms}."""
    if not settings.GEMINI_API_KEY: raise AIUnavailable('Gemini n’est pas configuré : ajoutez GEMINI_API_KEY dans backend/.env.')
    models = gemini_models()
    for position, model in enumerate(models):
        try:
            return _gemini_summary_with(model, text, title, course, length)
        except AIServiceError:
            if position + 1 == len(models): raise


def _gemini_summary_with(model, text, title, course, length):
    payload = {
        'systemInstruction': {'parts': [{'text': SUMMARY_INSTRUCTIONS}]},
        'contents': [{'role': 'user', 'parts': [{'text': _prompt(text, title, course, length)}]}],
        'generationConfig': {'temperature': 0.35, 'responseMimeType': 'application/json', 'responseSchema': SUMMARY_SCHEMA},
    }
    started = time.monotonic()
    body, _ = _post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                    {'x-goog-api-key': settings.GEMINI_API_KEY}, payload)
    try:
        data = json.loads(body)
        if data.get('promptFeedback', {}).get('blockReason'):
            raise AIServiceError('Gemini a refusé ce contenu. Reformulez ou raccourcissez le texte source.')
        candidate = data['candidates'][0]
        if candidate.get('finishReason') in ('SAFETY', 'RECITATION', 'PROHIBITED_CONTENT'):
            raise AIServiceError('Gemini a refusé ce contenu. Reformulez ou raccourcissez le texte source.')
        result = json.loads(''.join(part.get('text', '') for part in candidate['content']['parts']))
    except (ValueError, KeyError, IndexError, TypeError):
        raise AIServiceError('La réponse de Gemini est incomplète. Relancez la génération.')
    return {**_clean_summary(result, 'Gemini'), 'model': model, 'duration_ms': int((time.monotonic() - started) * 1000)}


def _lowercase_schema(schema):
    # Ollama expects standard JSON Schema types ("object"), Gemini uses OpenAPI ones ("OBJECT").
    if isinstance(schema, dict):
        return {k: (v.lower() if k == 'type' else _lowercase_schema(v)) for k, v in schema.items()}
    return [_lowercase_schema(v) for v in schema] if isinstance(schema, list) else schema


def ollama_summary(text, *, title, course, length):
    """Same contract as gemini_summary, using a local Ollama model."""
    if not settings.REVISIONS_OLLAMA_MODEL: raise AIUnavailable('Ollama n’est pas configuré : ajoutez REVISIONS_OLLAMA_MODEL (ou OLLAMA_MODEL) dans backend/.env.')
    model = settings.REVISIONS_OLLAMA_MODEL
    payload = {
        'model': model, 'stream': False, 'think': False,
        'format': _lowercase_schema(SUMMARY_SCHEMA),
        'options': {'temperature': 0.35, 'num_ctx': 16384},
        'messages': [{'role': 'system', 'content': SUMMARY_INSTRUCTIONS},
                     # A local 8B model cannot hold the full 60 000 characters in its context.
                     {'role': 'user', 'content': _prompt(text[:30000], title, course, length)}],
    }
    started = time.monotonic()
    try:
        body, _ = _post(settings.OLLAMA_URL.rstrip('/') + '/api/chat', {}, payload, timeout=settings.REVISIONS_OLLAMA_TIMEOUT_SECONDS)
    except AIServiceError as exc:
        if 'ne répond pas' in str(exc.detail):
            raise AIServiceError('Ollama ne répond pas : vérifiez qu’il est lancé sur ce serveur.')
        raise
    try:
        result = json.loads(json.loads(body)['message']['content'])
    except (ValueError, KeyError, TypeError):
        raise AIServiceError('La réponse d’Ollama est incomplète. Relancez la génération.')
    return {**_clean_summary(result, 'Ollama'), 'model': f'ollama/{model}', 'duration_ms': int((time.monotonic() - started) * 1000)}


def generate_summary(text, *, title, course, length):
    """Gemini first; the local Ollama model takes over when Gemini is missing or failing."""
    kwargs = dict(title=title, course=course, length=length)
    if not settings.GEMINI_API_KEY:
        return {**ollama_summary(text, **kwargs), 'fallback': False}
    try:
        return {**gemini_summary(text, **kwargs), 'fallback': False}
    except AIServiceError as gemini_error:
        if not settings.REVISIONS_OLLAMA_MODEL: raise
        try:
            return {**ollama_summary(text, **kwargs), 'fallback': True}
        except AIServiceError:
            raise gemini_error


def hf_illustration(prompt, style):
    """Return (image_bytes, model, duration_ms) from a Hugging Face text-to-image model.

    With HF_IMAGE_SPACE set, the model runs on its public Hugging Face Space (free GPU
    quota attached to the token); otherwise the paid Inference Providers API is used.
    """
    if not settings.HF_TOKEN: raise AIUnavailable('Hugging Face n’est pas configuré : ajoutez HF_TOKEN dans backend/.env.')
    full_prompt = f'{prompt}. {STYLE_PROMPTS[style]}, no text, no letters, no watermark'
    started = time.monotonic()
    if settings.HF_IMAGE_SPACE:
        body, model = _space_image(full_prompt), settings.HF_IMAGE_SPACE
    else:
        model = settings.HF_IMAGE_MODEL
        body, content_type = _post(f'https://router.huggingface.co/hf-inference/models/{model}',
            {'Authorization': f'Bearer {settings.HF_TOKEN}', 'Accept': 'image/png'}, {'inputs': full_prompt})
        if not content_type.startswith('image/'):
            raise AIServiceError('Le modèle Hugging Face n’a pas renvoyé d’image. Réessayez ou changez de modèle.')
    return body, model, int((time.monotonic() - started) * 1000)


def space_url(space):
    # "black-forest-labs/FLUX.1-schnell" -> "https://black-forest-labs-flux-1-schnell.hf.space"
    return 'https://' + re.sub(r'[^a-z0-9]+', '-', space.lower()).strip('-') + '.hf.space'


def _space_image(prompt):
    base = space_url(settings.HF_IMAGE_SPACE)
    auth = {'Authorization': f'Bearer {settings.HF_TOKEN}'}
    # Gradio API: queue the job, then read its server-sent events until "complete" or "error".
    body, _ = _post(f'{base}/gradio_api/call/infer', auth, {'data': [prompt, 0, True, 1024, 768, 4]})
    try: event_id = json.loads(body)['event_id']
    except (ValueError, KeyError, TypeError): raise AIServiceError('Le Space Hugging Face n’a pas accepté la demande.')
    stream, _ = _get(f'{base}/gradio_api/call/infer/{event_id}', auth)
    event, data = None, None
    for line in stream.decode('utf-8', 'replace').splitlines():
        if line.startswith('event:'): event = line[6:].strip()
        elif line.startswith('data:') and event in ('complete', 'error'): data = line[5:].strip(); break
    if event == 'error':
        message = (data or '').strip('"')
        # An error without details is what ZeroGPU Spaces return once the free daily quota is used.
        if 'quota' in message.lower() or data in (None, '', 'null'):
            raise AIServiceError('Le quota GPU gratuit Hugging Face du jour est atteint. Réessayez plus tard ou importez une image.')
        raise AIServiceError('Le modèle Hugging Face n’a pas pu créer l’image. Reformulez la description puis réessayez.')
    try: url = json.loads(data)[0]['url']
    except (TypeError, ValueError, KeyError, IndexError): raise AIServiceError('Le Space Hugging Face n’a pas renvoyé d’image.')
    # Only download from the Space itself: the URL comes from a third-party response.
    if not url.startswith(base + '/'): raise AIServiceError('Le Space Hugging Face a renvoyé une adresse inattendue.')
    image, _ = _get(url, auth)
    return image


def _gemini_json(instructions, prompt, schema, temperature):
    if not settings.GEMINI_API_KEY: raise AIUnavailable('Gemini n’est pas configuré : ajoutez GEMINI_API_KEY dans backend/.env.')
    models = gemini_models()
    for position, model in enumerate(models):
        try:
            return _gemini_json_with(model, instructions, prompt, schema, temperature)
        except AIServiceError:
            if position + 1 == len(models): raise


def _gemini_json_with(model, instructions, prompt, schema, temperature):
    payload = {'systemInstruction': {'parts': [{'text': instructions}]},
               'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
               'generationConfig': {'temperature': temperature, 'responseMimeType': 'application/json', 'responseSchema': schema}}
    body, _ = _post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                    {'x-goog-api-key': settings.GEMINI_API_KEY}, payload)
    try:
        data = json.loads(body)
        candidate = data['candidates'][0]
        if data.get('promptFeedback', {}).get('blockReason') or candidate.get('finishReason') in ('SAFETY', 'RECITATION', 'PROHIBITED_CONTENT'):
            raise AIServiceError('Gemini a refusé ce contenu.')
        return json.loads(''.join(part.get('text', '') for part in candidate['content']['parts'])), model
    except (ValueError, KeyError, IndexError, TypeError):
        raise AIServiceError('La réponse de Gemini est incomplète. Réessayez.')


def _ollama_json(instructions, prompt, schema, temperature):
    if not settings.REVISIONS_OLLAMA_MODEL: raise AIUnavailable('Aucun modèle d’IA n’est disponible sur ce serveur.')
    model = settings.REVISIONS_OLLAMA_MODEL
    payload = {'model': model, 'stream': False, 'think': False, 'format': _lowercase_schema(schema),
               'options': {'temperature': temperature, 'num_ctx': 8192},
               'messages': [{'role': 'system', 'content': instructions}, {'role': 'user', 'content': prompt}]}
    body, _ = _post(settings.OLLAMA_URL.rstrip('/') + '/api/chat', {}, payload, timeout=settings.REVISIONS_OLLAMA_TIMEOUT_SECONDS)
    try:
        return json.loads(json.loads(body)['message']['content']), f'ollama/{model}'
    except (ValueError, KeyError, TypeError):
        raise AIServiceError('La réponse d’Ollama est incomplète. Réessayez.')


def generate_json(instructions, prompt, schema, *, temperature=0.3):
    """Any structured answer, by the same path as summaries: Gemini first, the local model if it fails.

    Returns (data, model, fallback, duration_ms)."""
    started = time.monotonic()
    if not settings.GEMINI_API_KEY:
        data, model = _ollama_json(instructions, prompt, schema, temperature)
        return data, model, False, int((time.monotonic() - started) * 1000)
    try:
        data, model = _gemini_json(instructions, prompt, schema, temperature)
        return data, model, False, int((time.monotonic() - started) * 1000)
    except (AIServiceError, AIUnavailable) as gemini_error:
        if not settings.REVISIONS_OLLAMA_MODEL: raise
        try:
            data, model = _ollama_json(instructions, prompt, schema, temperature)
        except APIException:
            raise gemini_error
        return data, model, True, int((time.monotonic() - started) * 1000)
