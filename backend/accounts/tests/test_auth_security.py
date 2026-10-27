import base64
import hashlib
import json
import re
import secrets
from unittest.mock import patch
from django.core import mail, signing
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import User
from accounts.services import VERIFY_SALT, verification_token


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   EMAIL_VERIFICATION_REQUIRED=True, CAPTCHA_ENABLED=True, ALTCHA_HMAC_KEY='test-hmac-key', ALTCHA_MAX_NUMBER=2000)
class AuthSecurityTests(TransactionTestCase):
    """ALTCHA on the public account forms and confirmation of the address by email."""
    def setUp(self):
        self.password = secrets.token_urlsafe(16)
        self.client = APIClient()

    def solve(self, action, tamper=None):
        """Solve a challenge exactly like the browser widget does (protocol v1, SHA-256)."""
        response = self.client.get(f'/api/auth/captcha/?action={action}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        challenge = response.data
        number = next(n for n in range(challenge['maxnumber'] + 1)
                      if hashlib.sha256(f'{challenge["salt"]}{n}'.encode()).hexdigest() == challenge['challenge'])
        payload = {'algorithm': 'SHA-256', 'challenge': challenge['challenge'], 'number': number, 'salt': challenge['salt'],
                   'signature': challenge['signature'], 'took': 12, **(tamper or {})}
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def post(self, path, data, token=None, action=None):
        token = self.solve(action or path.split('/')[0].replace('email', 'verify').replace('password', 'reset')) if token is None else token
        headers = {'HTTP_X_CAPTCHA_TOKEN': token} if token else {}
        return self.client.post('/api/auth/' + path, data, format='json', **headers)

    def register(self, email='nouveau@example.test', token=None):
        return self.post('register/', dict(email=email, role='STUDENT', first_name='Nina', last_name='Nouvelle',
                                           password=self.password, confirmation=self.password), token, 'register')

    def link(self, email):
        return re.search(r'verifier-email\?token=(\S+)', [m for m in mail.outbox if email in m.to][-1].body).group(1)

    def test_proof_of_work_is_required_and_checked_by_the_server(self):
        self.assertEqual(self.register(token='').data['error']['code'], 'captcha_failed')
        self.assertEqual(self.register(token='pas-du-base64').data['error']['code'], 'captcha_failed')
        # Wrong number, forged signature, or a challenge issued for the login form: refused.
        for tamper in ({'number': 2001}, {'signature': '0' * 64}):
            self.assertEqual(self.register(token=self.solve('register', tamper)).status_code, 400)
        self.assertEqual(self.register(token=self.solve('login')).status_code, 400)
        self.assertFalse(User.objects.exists())
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.client.get('/api/auth/captcha/?action=autre').status_code, 400)

    def test_a_solution_works_once_and_expires(self):
        token = self.solve('register')
        self.assertEqual(self.register(token=token).status_code, 201)
        self.assertEqual(self.register('autre@example.test', token=token).data['error']['code'], 'captcha_failed')
        with override_settings(ALTCHA_EXPIRES=-1):
            expired = self.solve('register')
        self.assertEqual(self.register('tard@example.test', token=expired).status_code, 400)

    def test_account_is_usable_only_after_the_emailed_link(self):
        response = self.register()
        self.assertEqual((response.status_code, response.data['verification']), (201, True))
        message = mail.outbox[-1]
        self.assertEqual(message.subject, 'Confirmez votre adresse email — Nexora')
        self.assertIn('Confirmer mon adresse', message.alternatives[0][0])
        login = dict(email='nouveau@example.test', password=self.password)
        self.assertEqual(self.post('login/', login).data['error']['code'], 'email_not_verified')
        # A wrong password answers as for any address: the confirmation state is not revealed.
        self.assertEqual(self.post('login/', dict(login, password='mauvais')).status_code, 401)
        self.assertEqual(self.post('email/verify/', dict(token=self.link('nouveau@example.test')), token='').status_code, 200)
        self.assertTrue(User.objects.get(email='nouveau@example.test').email_verified)
        self.assertEqual(self.post('login/', login).status_code, 200)

    def test_invalid_expired_and_outdated_links_are_refused(self):
        self.register()
        user = User.objects.get(email='nouveau@example.test')
        verify = lambda token: self.post('email/verify/', dict(token=token), token='')
        self.assertEqual(verify('abc').data['error']['fields']['token'], ['Lien de confirmation invalide.'])
        with patch('accounts.views.VERIFY_MAX_AGE', -1):
            self.assertIn('expiré', verify(verification_token(user)).data['error']['fields']['token'][0])
        old = verification_token(user)
        User.objects.filter(pk=user.pk).update(email='change@example.test')
        self.assertEqual(verify(old).status_code, 400)
        self.assertEqual(verify(signing.dumps({'uid': 'not-an-id', 'email': 'change@example.test'}, salt=VERIFY_SALT)).status_code, 400)
        self.assertFalse(User.objects.get(pk=user.pk).email_verified)

    def test_resend_reaches_only_unconfirmed_accounts_with_the_same_answer(self):
        self.register()
        User.objects.create_user('deja@example.test', self.password, email_verified=True)
        mail.outbox.clear()
        answers = {self.post('email/resend/', dict(email=email), action='verify').data['message']
                   for email in ('nouveau@example.test', 'deja@example.test', 'inconnu@example.test')}
        self.assertEqual(len(answers), 1)
        self.assertEqual([m.to for m in mail.outbox], [['nouveau@example.test']])

    def test_public_configuration(self):
        self.assertEqual(self.client.get('/api/auth/config/').data,
                         {'captcha': {'enabled': True, 'provider': 'altcha'}, 'email_verification': True})
        challenge = self.client.get('/api/auth/captcha/?action=login').data
        self.assertNotIn('test-hmac-key', json.dumps(challenge))
        self.assertIn('action=login', challenge['salt'])

    @override_settings(CAPTCHA_ENABLED=False, EMAIL_VERIFICATION_REQUIRED=False)
    def test_both_checks_can_be_switched_off(self):
        response = self.register(token='')
        self.assertEqual((response.status_code, response.data['verification']), (201, False))
        self.assertEqual(self.post('login/', dict(email='nouveau@example.test', password=self.password), token='').status_code, 200)
