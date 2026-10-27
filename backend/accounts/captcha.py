"""ALTCHA: invisible, self-hosted bot check on the public account forms.

The browser solves a small proof of work (find ``number`` such that SHA-256(salt + number) equals the
challenge) without any puzzle for people (WCAG 2.2, criterion 3.3.8), and no third-party service is
called. Django signs every challenge with an HMAC key, binds it to one form and an expiry date in the
salt, and accepts each solution once. The solution travels in the ``X-Captcha-Token`` header so the
strict form serializers stay unchanged. With CAPTCHA_ENABLED=false the check is off (tests, CI).
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from urllib.parse import parse_qs
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import APIException
from .models import RateBucket

ACTIONS = ('login', 'register', 'reset', 'verify')


class CaptchaFailed(APIException):
    status_code = 400
    default_code = 'captcha_failed'
    default_detail = 'La vérification anti-robot a échoué. Rechargez la page puis réessayez.'


def captcha_enabled():
    return settings.CAPTCHA_ENABLED


def hmac_key():
    # A dedicated key may be set; otherwise one is derived from the secret key, never the secret itself.
    key = settings.ALTCHA_HMAC_KEY or hashlib.sha256(('altcha:' + settings.SECRET_KEY).encode()).hexdigest()
    return key.encode()


def sign(challenge):
    return hmac.new(hmac_key(), challenge.encode(), hashlib.sha256).hexdigest()


def create_challenge(action):
    """A signed challenge for one form, valid ALTCHA_EXPIRES seconds (protocol v1, SHA-256)."""
    expires = int(time.time()) + settings.ALTCHA_EXPIRES
    salt = f'{secrets.token_hex(12)}?expires={expires}&action={action}'
    number = secrets.randbelow(settings.ALTCHA_MAX_NUMBER + 1)
    challenge = hashlib.sha256(f'{salt}{number}'.encode()).hexdigest()
    return {'algorithm': 'SHA-256', 'challenge': challenge, 'salt': salt, 'signature': sign(challenge),
            'maxnumber': settings.ALTCHA_MAX_NUMBER}


def check_payload(token, action):
    """The challenge of a valid solution for this form, or None."""
    try:
        data = json.loads(base64.b64decode(token, validate=True))
        salt, number, challenge, signature = str(data['salt']), int(data['number']), str(data['challenge']), str(data['signature'])
    except (ValueError, KeyError, TypeError):
        return None
    params = parse_qs(salt.partition('?')[2])
    try: expires = int(params.get('expires', ['0'])[0])
    except ValueError: return None
    valid = (data.get('algorithm') == 'SHA-256' and 0 <= number <= settings.ALTCHA_MAX_NUMBER
            and params.get('action', [''])[0] == action and expires >= time.time()
            and hmac.compare_digest(hashlib.sha256(f'{salt}{number}'.encode()).hexdigest(), challenge)
            and hmac.compare_digest(sign(challenge), signature))
    return challenge if valid else None


def verify_captcha(request, action):
    if not captcha_enabled(): return
    token = request.headers.get('X-Captcha-Token', '').strip()
    if not token or len(token) > 4096: raise CaptchaFailed()
    challenge = check_payload(token, action)
    if not challenge: raise CaptchaFailed()
    # Single use, shared by every server process: a solved challenge is recorded until it expires.
    try:
        RateBucket.objects.create(key='altcha:' + hashlib.sha256(challenge.encode()).hexdigest()[:57],  # Field limited to 64.
                                  expires_at=timezone.now() + timedelta(seconds=settings.ALTCHA_EXPIRES), hits=1)
    except IntegrityError:
        raise CaptchaFailed()
