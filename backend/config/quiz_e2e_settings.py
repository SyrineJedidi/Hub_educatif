import os
import re
from django.core.exceptions import ImproperlyConfigured
from .roles_e2e_settings import *

run = os.getenv('QUIZ_TEST_RUN', 'local')
if not re.fullmatch(r'[a-z0-9_]{1,24}', run):
    raise ImproperlyConfigured('QUIZ_TEST_RUN doit contenir 1 à 24 lettres minuscules, chiffres ou soulignés.')
DATABASES['default']['NAME'] = 'test_nexora_quiz_' + run
