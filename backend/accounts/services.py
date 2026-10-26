import hashlib
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing, mail
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone
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


def send_link(user, kind='reset'):
    token = reset_token(user)
    url = f'{settings.FRONTEND_URL}/reinitialiser-mot-de-passe?token={token}'
    mail.send_mail('Réinitialisez votre mot de passe — Nexora',
        f'Bonjour {user.first_name},\n\nOuvrez ce lien pour réinitialiser votre mot de passe :\n{url}\n\nCe lien est à usage unique et expire dans une heure. Si vous n’êtes pas à l’origine de cette demande, ignorez ce message.\n\nÉquipe Nexora',
        settings.DEFAULT_FROM_EMAIL, [user.email])
