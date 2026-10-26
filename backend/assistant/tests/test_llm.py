import http.client
import json
import urllib.error
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from assistant import llm
from assistant.llm import MESSAGES, LLMError, answer_schema, checked, generate_answer, provider_status

URLOPEN = 'urllib.request.urlopen'
KEY = 'test-gemini-key'
# A database name the test runner never uses, so the real client may run against the mocked network.
SERVER_DATABASE = SimpleNamespace(settings_dict={'NAME': 'nexora_hub'})
SYSTEM = 'Tu es l’assistant pédagogique du cours « Seconde A ».'
CONTENTS = [{'role': 'user', 'parts': [{'text': 'EXTRAITS:\n[S1] (Les vecteurs · Définition)\nUn vecteur a une norme. Elle est positive.\n\nQUESTION:\nQu’est-ce qu’une norme ?'}]}]


def reply(payload):
    """What urlopen() returns: a context manager whose read() gives the body."""
    return BytesIO(payload if isinstance(payload, bytes) else json.dumps(payload).encode())


def gemini(answer='La norme est une longueur [S1].', out_of_scope=False, follow_ups=('Un exemple ?',), **extra):
    text = json.dumps({'answer': answer, 'out_of_scope': out_of_scope, 'follow_ups': list(follow_ups)})
    return {'candidates': [{'content': {'parts': [{'text': text}], 'role': 'model'}, 'finishReason': 'STOP'}],
        'usageMetadata': {'promptTokenCount': 812, 'candidatesTokenCount': 64, 'totalTokenCount': 876}, **extra}


def http_error(code):
    # The body is the provider's: it must never reach a student or a log line.
    return urllib.error.HTTPError(llm.GEMINI_URL.format(model='m'), code, 'Error', {}, BytesIO(f'{{"error": "raw body {KEY}"}}'.encode()))


class BrokenReply(BytesIO):
    def __init__(self, error): super().__init__(b''); self.error = error
    def read(self, *args): raise self.error


@override_settings(ASSISTANT_LLM_PROVIDER='gemini', GEMINI_API_KEY=KEY, GEMINI_MODEL='gemini-3.5-flash-lite', GEMINI_FALLBACK_MODEL='gemini-3.1-flash-lite',
    GEMINI_TIMEOUT_SECONDS=45)
class GeminiClientTests(SimpleTestCase):
    def setUp(self):
        database = patch('assistant.llm.connection', SERVER_DATABASE); database.start(); self.addCleanup(database.stop)

    def call(self, *responses):
        with patch(URLOPEN, side_effect=list(responses)) as urlopen:
            try: return generate_answer(SYSTEM, CONTENTS, answer_schema()), urlopen
            except LLMError as exc: return exc, urlopen

    def failure(self, *responses):
        error, urlopen = self.call(*responses)
        self.assertIsInstance(error, LLMError)
        self.assertNotIn(KEY, f'{error} {error.message} {error.code} {error.model}')
        self.assertNotIn('raw body', error.message)
        return error, urlopen

    def test_success_parses_json_answer_and_token_counts(self):
        result, urlopen = self.call(reply(gemini()))
        self.assertEqual(result.data, {'answer': 'La norme est une longueur [S1].', 'out_of_scope': False, 'follow_ups': ['Un exemple ?']})
        self.assertEqual((result.provider, result.model, result.prompt_tokens, result.output_tokens), ('gemini', 'gemini-3.5-flash-lite', 812, 64))
        self.assertIsInstance(result.latency_ms, int)
        request, timeout = urlopen.call_args.args[0], urlopen.call_args.kwargs['timeout']
        self.assertEqual((request.full_url, request.get_method(), timeout),
            ('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent', 'POST', 45))
        self.assertEqual((request.get_header('X-goog-api-key'), request.get_header('Content-type')), (KEY, 'application/json'))
        self.assertNotIn(KEY, request.full_url)
        # Sampling parameters are deprecated on current Gemini models and never sent.
        self.assertEqual(json.loads(request.data), {'systemInstruction': {'parts': [{'text': SYSTEM}]}, 'contents': CONTENTS,
            'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': answer_schema(), 'maxOutputTokens': 2048}})

    def test_thought_parts_are_ignored_and_split_text_is_joined(self):
        payload = gemini()
        text = payload['candidates'][0]['content']['parts'][0]['text']
        payload['candidates'][0]['content']['parts'] = [{'text': 'Je réfléchis…', 'thought': True}, {'text': text[:10]}, {'text': text[10:]}, 'ignoré']
        del payload['usageMetadata']
        result, _ = self.call(reply(payload))
        self.assertEqual((result.data['answer'], result.prompt_tokens, result.output_tokens), ('La norme est une longueur [S1].', None, None))

    def test_quota_on_the_main_model_falls_back_once(self):
        result, urlopen = self.call(http_error(429), reply(gemini()))
        self.assertEqual(result.model, 'gemini-3.1-flash-lite')
        self.assertEqual([c.args[0].full_url.split('/')[-1] for c in urlopen.call_args_list], ['gemini-3.5-flash-lite:generateContent', 'gemini-3.1-flash-lite:generateContent'])
        self.assertEqual(json.loads(urlopen.call_args_list[0].args[0].data), json.loads(urlopen.call_args_list[1].args[0].data))
        error, urlopen = self.failure(http_error(429), http_error(429))
        self.assertEqual((error.code, error.message, error.retryable, error.model, error.provider), ('quota', MESSAGES['quota'], True, 'gemini-3.1-flash-lite', 'gemini'))
        self.assertEqual(urlopen.call_count, 2)

    def test_without_a_distinct_fallback_quota_is_reported_at_once(self):
        for fallback in ('', 'gemini-3.5-flash-lite'):
            with self.subTest(fallback=fallback), self.settings(GEMINI_FALLBACK_MODEL=fallback):
                error, urlopen = self.failure(http_error(429), reply(gemini()))
                self.assertEqual((error.code, urlopen.call_count), ('quota', 1))

    def test_http_errors_map_to_safe_codes(self):
        cases = [(401, 'auth', False), (403, 'auth', False), (400, 'refused', False), (404, 'refused', False), (408, 'unavailable', True),
            (500, 'unavailable', True), (503, 'unavailable', True)]
        for status, code, retryable in cases:
            with self.subTest(status=status):
                error, urlopen = self.failure(http_error(status))
                self.assertEqual((error.code, error.message, error.retryable, error.model), (code, MESSAGES[code], retryable, 'gemini-3.5-flash-lite'))
                # Only a quota error tries the second model.
                self.assertEqual(urlopen.call_count, 1)

    def test_network_failures_are_unavailable(self):
        failures = [TimeoutError('timed out'), urllib.error.URLError('Name or service not known'), ConnectionResetError(104, 'reset'),
            http.client.RemoteDisconnected('closed')]
        for failure in failures:
            with self.subTest(failure=repr(failure)):
                self.assertEqual(self.failure(failure)[0].code, 'unavailable')
        for failure in (TimeoutError('The read operation timed out'), http.client.IncompleteRead(b'{"candi'), http.client.BadStatusLine('HTTP/1.1 ???')):
            with self.subTest(failure=repr(failure)):
                self.assertEqual(self.failure(BrokenReply(failure))[0].code, 'unavailable')

    def test_blocked_prompt_or_answer(self):
        for payload in ({'promptFeedback': {'blockReason': 'SAFETY'}}, gemini(promptFeedback={'blockReason': 'PROHIBITED_CONTENT'}),
                {'candidates': [{'finishReason': 'SAFETY'}]}, {'candidates': [{'finishReason': 'BLOCKLIST', 'content': {'parts': [{'text': '{}'}]}}]}):
            with self.subTest(payload=payload):
                error, _ = self.failure(reply(payload))
                self.assertEqual((error.code, error.message, error.retryable), ('blocked', MESSAGES['blocked'], False))

    def test_invalid_responses(self):
        bodies = [b'<html>502</html>', b'\xff\xfe', b'[]', {'candidates': []}, {'candidates': ['texte']}, {'candidates': [{'finishReason': 'STOP'}]},
            {'candidates': [{'content': {'parts': [{'text': 'pas du JSON'}]}, 'finishReason': 'MAX_TOKENS'}]},
            gemini(answer=3), gemini(out_of_scope='non'), gemini(answer='   '), {'candidates': [{'content': {'parts': [{'text': '[1, 2]'}]}}]}]
        for body in bodies:
            with self.subTest(body=body):
                error, _ = self.failure(reply(body))
                self.assertEqual((error.code, error.message, error.retryable), ('invalid_response', MESSAGES['invalid_response'], True))

    def test_test_database_is_refused_before_the_key_is_read(self):
        for key in (KEY, ''):
            with self.subTest(key=bool(key)), self.settings(GEMINI_API_KEY=key), patch('assistant.llm.connection', SimpleNamespace(settings_dict={'NAME': 'test_nexora'})):
                error, urlopen = self.failure(reply(gemini()))
                self.assertEqual((error.code, error.message), ('disabled', 'Le fournisseur Gemini réel est désactivé sur une base de test.'))
                self.assertFalse(urlopen.called)

    def test_missing_key_disables_the_client(self):
        with self.settings(GEMINI_API_KEY=''):
            error, urlopen = self.failure(reply(gemini()))
        self.assertEqual((error.code, error.message, error.retryable, error.provider), ('disabled', MESSAGES['disabled'], False, 'gemini'))
        self.assertFalse(urlopen.called)


class ProviderChoiceTests(SimpleTestCase):
    def test_disabled_by_default_and_for_unknown_names(self):
        for name in ('disabled', '', 'openai'):
            with self.subTest(name=name), self.settings(ASSISTANT_LLM_PROVIDER=name), patch(URLOPEN) as urlopen:
                with self.assertRaises(LLMError) as caught: generate_answer(SYSTEM, CONTENTS, answer_schema())
                self.assertEqual((caught.exception.code, caught.exception.message, caught.exception.provider, caught.exception.model),
                    ('disabled', MESSAGES['disabled'], 'disabled', ''))
                self.assertIsInstance(caught.exception.latency_ms, int); self.assertFalse(urlopen.called)

    def test_provider_status(self):
        cases = [({'ASSISTANT_LLM_PROVIDER': 'disabled'}, ('disabled', False, '', '')), ({'ASSISTANT_LLM_PROVIDER': 'mistral'}, ('disabled', False, '', '')),
            ({'ASSISTANT_LLM_PROVIDER': 'fake'}, ('fake', True, 'fake-gemini', '')),
            ({'ASSISTANT_LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': ''}, ('gemini', False, 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite')),
            ({'ASSISTANT_LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': KEY, 'GEMINI_MODEL': 'gemini-x'}, ('gemini', True, 'gemini-x', 'gemini-3.1-flash-lite'))]
        for overrides, (name, configured, model, fallback) in cases:
            values = {'GEMINI_MODEL': 'gemini-3.5-flash-lite', 'GEMINI_FALLBACK_MODEL': 'gemini-3.1-flash-lite', 'GEMINI_API_KEY': KEY, **overrides}
            with self.subTest(**overrides), self.settings(**values):
                status = provider_status()
                self.assertEqual(status, {'provider': name, 'configured': configured, 'model': model, 'fallback_model': fallback})
                self.assertNotIn(KEY, json.dumps(status))

    def test_answer_schema_is_the_gemini_subset(self):
        self.assertEqual(answer_schema(), {'type': 'OBJECT', 'properties': {'answer': {'type': 'STRING'}, 'out_of_scope': {'type': 'BOOLEAN'},
            'follow_ups': {'type': 'ARRAY', 'items': {'type': 'STRING'}, 'maxItems': 3}}, 'required': ['answer', 'out_of_scope'],
            'propertyOrdering': ['answer', 'out_of_scope', 'follow_ups']})

    def test_checked_keeps_only_the_expected_shape(self):
        self.assertEqual(checked({'answer': '  Réponse  ', 'out_of_scope': False, 'follow_ups': ['a', 2, None, 'b'], 'extra': 1}),
            {'answer': 'Réponse', 'out_of_scope': False, 'follow_ups': ['a', 'b']})
        self.assertEqual(checked({'answer': '', 'out_of_scope': True, 'follow_ups': 'pas une liste'}), {'answer': '', 'out_of_scope': True, 'follow_ups': []})
        for data in (None, [], {'answer': 'x'}, {'answer': None, 'out_of_scope': False}, {'answer': 'x', 'out_of_scope': 0}, {'answer': ' ', 'out_of_scope': False}):
            with self.subTest(data=data), self.assertRaises(LLMError) as caught: checked(data, 'm')
            self.assertEqual((caught.exception.code, caught.exception.model), ('invalid_response', 'm'))


@override_settings(ASSISTANT_LLM_PROVIDER='fake')
class FakeProviderTests(SimpleTestCase):
    def ask(self, question, excerpts='[S1] (Les vecteurs · Définition)\nUn vecteur a une norme. Elle est positive.\n\n[S2] (Les vecteurs)\nAutre extrait.'):
        return generate_answer(SYSTEM, [{'role': 'user', 'parts': [{'text': f'EXTRAITS:\n{excerpts}\n\nQUESTION:\n{question}'}]}], answer_schema())

    def test_answers_with_the_first_sentence_of_the_first_excerpt(self):
        result = self.ask('Qu’est-ce qu’une norme ?')
        self.assertEqual(result.data, {'answer': 'D’après le cours : Un vecteur a une norme. [S1]', 'out_of_scope': False,
            'follow_ups': ['Peux-tu donner un exemple ?', 'Quels sont les points essentiels à retenir ?']})
        self.assertEqual((result.provider, result.model), ('fake', 'fake-gemini'))
        # Token counts are estimated at four characters per token.
        prompt = SYSTEM + f'EXTRAITS:\n[S1] (Les vecteurs · Définition)\nUn vecteur a une norme. Elle est positive.\n\n[S2] (Les vecteurs)\nAutre extrait.\n\nQUESTION:\nQu’est-ce qu’une norme ?'
        self.assertEqual((result.prompt_tokens, result.output_tokens), (len(prompt) // 4, len(result.data['answer']) // 4))
        self.assertEqual(self.ask('Sans extrait', excerpts='').data['answer'], 'D’après le cours : Le cours ne donne pas de détail à ce sujet. [S1]')

    def test_markers_in_the_question_select_the_failure(self):
        for marker, code in (('#erreur', 'unavailable'), ('#quota', 'quota'), ('#bloque', 'blocked')):
            with self.subTest(marker=marker), self.assertRaises(LLMError) as caught: self.ask(f'Une norme ? {marker}')
            self.assertEqual((caught.exception.code, caught.exception.provider, caught.exception.model), (code, 'fake', 'fake-gemini'))
        self.assertEqual(self.ask('La capitale ? #horscours').data, {'answer': 'Les extraits du cours ne traitent pas de cette question.', 'out_of_scope': True, 'follow_ups': []})
        # A marker inside the course excerpts is content, not a command.
        self.assertFalse(self.ask('Une norme ?', excerpts='[S1] (x)\nLe mot #erreur est écrit ici.').data['out_of_scope'])

    def test_slow_marker_waits_before_answering(self):
        with patch('assistant.llm.time.sleep') as sleep: self.ask('Une norme ? #lent')
        sleep.assert_called_once_with(2)

    def test_without_a_user_turn_there_is_nothing_to_quote(self):
        model_only = [{'role': 'model', 'parts': [{'text': 'EXTRAITS:\n[S1] (x)\nTexte.\n\nQUESTION:\n#erreur'}]}]
        for contents in ([], model_only):
            with self.subTest(contents=contents):
                self.assertEqual(generate_answer(SYSTEM, contents, answer_schema()).data['answer'], 'D’après le cours : Le cours ne donne pas de détail à ce sujet. [S1]')
