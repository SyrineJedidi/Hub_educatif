from .settings import *
DATABASES['default']['NAME'] = 'test_nexora_browser_isolated'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
