import hashlib
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing, mail
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone
from django.utils.html import escape
from rest_framework.exceptions import Throttled
from .models import RateBucket


def limit(request, scope, maximum=5, seconds=300, identity=''):
    # REMOTE_ADDR only: forwarded headers must not allow a client to bypass limits.
    subject = identity or request.META.get('REMOTE_ADDR', '')
    key = hashlib.sha256(f'{scope}:{subject}:{int(time.time()) // seconds}'.encode()).hexdigest()
    try:
        bucket, _ = RateBucket.objects.get_or_create(key=key, defaults={'expires_at': timezone.now() + timedelta(seconds=seconds * 2)})
    except IntegrityError:
        bucket = RateBucket.objects.get(key=key)
    RateBucket.objects.filter(pk=bucket.pk).update(hits=F('hits') + 1)
    bucket.refresh_from_db()
    if bucket.hits > maximum:
        raise Throttled(wait=seconds, detail='Trop de demandes. Veuillez patienter avant de réessayer.')


def reset_token(user):
    return signing.dumps({'uid': str(user.pk), 'value': default_token_generator.make_token(user)}, salt='reset-password')


VERIFY_SALT = 'verify-email'
VERIFY_MAX_AGE = 3 * 24 * 3600


def verification_token(user):
    # Bound to the address: a link sent before an email change no longer verifies the new one.
    return signing.dumps({'uid': str(user.pk), 'email': user.email}, salt=VERIFY_SALT)


def send_verification(user):
    url = f'{settings.FRONTEND_URL}/verifier-email?token={verification_token(user)}'
    text = (f'Bonjour {user.first_name},\n\nBienvenue sur le Hub Éducatif Multimodal. Confirmez votre adresse en ouvrant ce lien :\n{url}\n\n'
            'Le lien est valable trois jours. Si vous n’avez pas créé de compte, ignorez ce message.\n\nÉquipe Nexora')
    html = (f'<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#1f3b36">'
            f'<h1 style="font-size:22px;color:#0f5c52">Bienvenue, {escape(user.first_name)} !</h1>'
            '<p>Votre compte sur le Hub Éducatif Multimodal est presque prêt. Confirmez votre adresse email pour vous connecter.</p>'
            f'<p style="margin:28px 0"><a href="{escape(url)}" style="background:#17786a;color:#fff;padding:12px 22px;border-radius:999px;'
            'text-decoration:none;font-weight:bold">Confirmer mon adresse</a></p>'
            '<p style="font-size:13px;color:#55635f">Le lien est valable trois jours. Si vous n’avez pas créé de compte, ignorez ce message.</p>'
            '<p style="font-size:13px;color:#55635f">Équipe Nexora</p></div>')
    mail.send_mail('Confirmez votre adresse email — Nexora', text, settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html)


def send_link(user, kind='reset'):
    if kind == 'verify': return send_verification(user)
    token = reset_token(user)
    url = f'{settings.FRONTEND_URL}/reinitialiser-mot-de-passe?token={token}'
    mail.send_mail('Réinitialisez votre mot de passe — Nexora',
        f'Bonjour {user.first_name},\n\nOuvrez ce lien pour réinitialiser votre mot de passe :\n{url}\n\nCe lien est à usage unique et expire dans une heure. Si vous n’êtes pas à l’origine de cette demande, ignorez ce message.\n\nÉquipe Nexora',
        settings.DEFAULT_FROM_EMAIL, [user.email])
