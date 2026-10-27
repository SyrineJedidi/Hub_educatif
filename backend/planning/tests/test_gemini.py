import http.client
import json
import logging
import types
import urllib.error
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from ai import gemini
from ai.gemini import GeminiError, generate_json

KEY = 'AIza-secret-test-key'
SCHEMA = gemini.object_schema({'advice': gemini.string_schema('Conseils.'), 'tasks': gemini.array_schema(gemini.string_schema(), max_items=3)}, required=['advice'])
LIVE_DATABASE = types.SimpleNamespace(settings_dict={'NAME': 'nexora_hub'})


class Reply:
    def __init__(self, body): self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


def answer(text, **extra):
    return {'candidates': [{'content': {'parts': [{'text': text}]}, 'finishReason': 'STOP'}],
        'usageMetadata': {'promptTokenCount': 120, 'candidatesTokenCount': 45}, **extra}


def http_error(code):
    return urllib.error.HTTPError('https://generativelanguage.googleapis.com', code, 'error', {}, None)


@override_settings(GEMINI_PROVIDER='gemini', GEMINI_API_KEY=KEY, GEMINI_MODEL='gemini-3.5-flash-lite',
    GEMINI_FALLBACK_MODEL='gemini-3.1-flash-lite', GEMINI_TIMEOUT_SECONDS=60)
class GeminiClientTests(SimpleTestCase):
    def setUp(self):
        # Failures are logged on purpose; keep the test output readable.
        self.enterContext(patch.object(gemini.logger, 'handlers', [logging.NullHandler()]))
        self.enterContext(patch.object(gemini.logger, 'propagate', False))

    def call(self, *replies):
        with patch('ai.gemini.connection', LIVE_DATABASE), patch('ai.gemini.urllib.request.urlopen', side_effect=list(replies)) as urlopen:
            try: return generate_json('Consigne système', 'Données', SCHEMA, max_output_tokens=2048), urlopen
            except GeminiError as exc: return exc, urlopen

    def assertFailure(self, outcome, code, retryable):
        error, _ = outcome
        self.assertIsInstance(error, GeminiError)
        self.assertEqual((error.code, error.retryable), (code, retryable))
        self.assertEqual(str(error), error.message)
        self.assertNotIn(KEY, error.message)

    def test_success_parses_parts_tokens_and_sends_the_documented_request(self):
        payload = answer('{"advice": "Révisez', usageMetadata={'promptTokenCount': 812, 'candidatesTokenCount': 64})
        payload['candidates'][0]['content']['parts'] = [{'text': 'brouillon', 'thought': True}, {'text': '{"advice": "Révisez'}, {'text': ' tôt", "tasks": []}'}]
        result, urlopen = self.call(Reply(payload))
        self.assertEqual(result.data, {'advice': 'Révisez tôt', 'tasks': []})
        self.assertEqual((result.provider, result.model, result.prompt_tokens, result.output_tokens), ('gemini', 'gemini-3.5-flash-lite', 812, 64))
        self.assertIsInstance(result.latency_ms, int)
        request = urlopen.call_args.args[0]
        self.assertEqual(urlopen.call_args.kwargs, {'timeout': 60})
        self.assertEqual(request.full_url, 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent')
        self.assertEqual((request.get_method(), request.get_header('X-goog-api-key'), request.get_header('Content-type')), ('POST', KEY, 'application/json'))
        body = json.loads(request.data)
        self.assertEqual(body, {'systemInstruction': {'parts': [{'text': 'Consigne système'}]}, 'contents': [{'role': 'user', 'parts': [{'text': 'Données'}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': SCHEMA, 'maxOutputTokens': 2048}})
        for deprecated in ('temperature', 'topP', 'topK'): self.assertNotIn(deprecated, json.dumps(body))
        self.assertNotIn(KEY, json.dumps(body))

    def test_missing_or_invalid_token_counts_become_none(self):
        payload = answer('{}'); payload['usageMetadata'] = {'promptTokenCount': '12', 'candidatesTokenCount': -1}
        result, _ = self.call(Reply(payload))
        self.assertEqual((result.prompt_tokens, result.output_tokens), (None, None))
        payload.pop('usageMetadata')
        self.assertIsNone(self.call(Reply(payload))[0].prompt_tokens)

    def test_quota_retries_once_on_the_fallback_model(self):
        result, urlopen = self.call(http_error(429), Reply(answer('{"advice": "ok"}')))
        self.assertEqual((result.model, result.data), ('gemini-3.1-flash-lite', {'advice': 'ok'}))
        self.assertEqual([c.args[0].full_url.split('/models/')[1] for c in urlopen.call_args_list],
            ['gemini-3.5-flash-lite:generateContent', 'gemini-3.1-flash-lite:generateContent'])
        outcome = self.call(http_error(429), http_error(429))
        self.assertFailure(outcome, 'quota', True); self.assertEqual(outcome[1].call_count, 2)
        # The fallback model only replaces a quota failure.
        outcome = self.call(http_error(503), Reply(answer('{}')))
        self.assertFailure(outcome, 'unavailable', True); self.assertEqual(outcome[1].call_count, 1)
        with override_settings(GEMINI_FALLBACK_MODEL='gemini-3.5-flash-lite'):
            outcome = self.call(http_error(429), Reply(answer('{}')))
        self.assertFailure(outcome, 'quota', True); self.assertEqual(outcome[1].call_count, 1)
        with override_settings(GEMINI_FALLBACK_MODEL=''):
            self.assertEqual(self.call(http_error(429), Reply(answer('{}')))[1].call_count, 1)

    def test_http_and_network_errors_are_mapped(self):
        self.assertFailure(self.call(http_error(401)), 'auth', False)
        outcome = self.call(http_error(403)); self.assertFailure(outcome, 'auth', False)
        self.assertEqual(outcome[0].message, 'Clé Gemini invalide ou projet non autorisé.')
        self.assertFailure(self.call(http_error(400)), 'refused', False)
        self.assertFailure(self.call(http_error(404)), 'refused', False)
        for error in (http_error(500), http_error(503), urllib.error.URLError('dns'), TimeoutError('slow'), ConnectionResetError(), http.client.IncompleteRead(b'{')):
            self.assertFailure(self.call(error), 'unavailable', True)

    def test_blocked_and_invalid_responses(self):
        self.assertFailure(self.call(Reply({'promptFeedback': {'blockReason': 'SAFETY'}})), 'blocked', False)
        payload = answer('{}'); payload['candidates'][0]['finishReason'] = 'SAFETY'
        self.assertFailure(self.call(Reply(payload)), 'blocked', False)
        for body in (b'<html>erreur</html>', b'\xff\xfe', [], {'candidates': []}, {'candidates': ['texte']}, answer('pas du JSON'),
                answer('["une", "liste"]'), answer(''), {'candidates': [{'content': 'texte'}]}):
            self.assertFailure(self.call(Reply(body)), 'invalid_response', False)

    def test_logs_never_contain_the_key_or_the_provider_body(self):
        with self.assertLogs('ai.gemini', level='WARNING') as logs:
            self.call(http_error(401)); self.call(Reply(answer('secret du fournisseur')))
        output = '\n'.join(logs.output)
        self.assertIn('auth (HTTP 401)', output); self.assertIn('invalid_response', output)
        self.assertNotIn(KEY, output); self.assertNotIn('secret du fournisseur', output)

    def test_test_database_guard_and_missing_configuration(self):
        with patch('ai.gemini.urllib.request.urlopen') as urlopen:
            # A test database name starts with test_: the real provider is refused.
            with patch('ai.gemini.connection', types.SimpleNamespace(settings_dict={'NAME': 'test_nexora_hub_isolated'})):
                with self.assertRaises(GeminiError) as caught: generate_json('s', 'p', SCHEMA)
            self.assertEqual(caught.exception.code, 'disabled'); self.assertIn('base de test', caught.exception.message)
            with override_settings(GEMINI_API_KEY=''), patch('ai.gemini.connection', LIVE_DATABASE):
                with self.assertRaises(GeminiError) as caught: generate_json('s', 'p', SCHEMA)
            self.assertEqual((caught.exception.code, caught.exception.message), ('disabled', 'L’IA n’est pas configurée sur ce serveur.'))
            for provider in ('disabled', 'openai', ''):
                with override_settings(GEMINI_PROVIDER=provider), patch('ai.gemini.connection', LIVE_DATABASE):
                    with self.assertRaises(GeminiError) as caught: generate_json('s', 'p', SCHEMA)
                self.assertEqual((caught.exception.code, caught.exception.retryable), ('disabled', False))
            urlopen.assert_not_called()

    @override_settings(GEMINI_PROVIDER='fake')
    def test_fake_provider(self):
        with patch('ai.gemini.urllib.request.urlopen') as urlopen:
            result = generate_json('s', 'p', SCHEMA, fake=lambda: {'advice': 'Démonstration'})
            self.assertEqual((result.data, result.provider, result.model, result.prompt_tokens, result.output_tokens),
                ({'advice': 'Démonstration'}, 'fake', 'fake', None, None))
            self.assertEqual(generate_json('s', 'p', SCHEMA).data, {})
            with self.assertRaises(GeminiError) as caught: generate_json('s', 'p', SCHEMA, fake=lambda: 'texte')
            self.assertEqual(caught.exception.code, 'invalid_response')
            urlopen.assert_not_called()

    def test_schema_helpers_and_error_defaults(self):
        self.assertEqual(SCHEMA, {'type': 'OBJECT', 'required': ['advice'], 'properties': {
            'advice': {'type': 'STRING', 'description': 'Conseils.'}, 'tasks': {'type': 'ARRAY', 'items': {'type': 'STRING'}, 'maxItems': 3}}})
        self.assertEqual(gemini.array_schema(gemini.string_schema()), {'type': 'ARRAY', 'items': {'type': 'STRING'}})
        error = GeminiError('mystery')
        self.assertEqual((error.message, error.retryable), ('Le service IA ne répond pas pour le moment.', False))
        self.assertTrue(GeminiError('refused', retryable=True).retryable)
        self.assertEqual(GeminiError('disabled', 'Message précis.').message, 'Message précis.')
