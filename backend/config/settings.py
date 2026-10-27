import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3:8b')
OLLAMA_TIMEOUT_SECONDS = os.getenv('OLLAMA_TIMEOUT_SECONDS', '180')
# Quiz question generation runs in the background (AI_JOB_BACKEND) unless this is false.
QUIZ_GENERATION_ASYNC = os.getenv('QUIZ_GENERATION_ASYNC', 'true').lower() == 'true'
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('Définissez DJANGO_SECRET_KEY dans backend/.env.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = [
    'config.apps.MongoAuthConfig', 'config.apps.MongoContentTypesConfig',
    'django.contrib.sessions', 'django.contrib.staticfiles',
    'django_mongodb_backend', 'rest_framework', 'accounts', 'classrooms', 'attendance', 'quizzes', 'courses', 'revisions', 'assistant', 'planning',
]
MIGRATION_MODULES = {'auth': 'mongo_migrations.auth', 'contenttypes': 'mongo_migrations.contenttypes'}
DATABASE_ROUTERS = ['django_mongodb_backend.routers.MongoRouter']
DEFAULT_AUTO_FIELD = 'django_mongodb_backend.fields.ObjectIdAutoField'
DATABASES = {'default': {
    'ENGINE': 'django_mongodb_backend',
    'HOST': os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27019/?replicaSet=nexora'),
    'NAME': os.getenv('MONGODB_DATABASE', 'hub_educatif'),
    'TEST': {'NAME': 'test_nexora_hub_isolated'},
}}
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Tunis'
USE_I18N = True
USE_TZ = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# Secure cookies by default outside debug; DJANGO_SECURE_COOKIES=false only for a local HTTP trial.
SECURE_COOKIES = os.getenv('DJANGO_SECURE_COOKIES', str(not DEBUG)).lower() == 'true'
SESSION_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_AGE = 60 * 60 * 8
CSRF_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'accounts.errors.csrf_failure'
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', str(not DEBUG)).lower() == 'true'
# Behind the HTTPS reverse proxy (nginx, load balancer), trust its X-Forwarded-Proto header.
if os.getenv('DJANGO_BEHIND_PROXY', 'false').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
SECURE_HSTS_PRELOAD = SECURE_SSL_REDIRECT
# The container health check calls the API over plain HTTP from inside.
SECURE_REDIRECT_EXEMPT = [r'^api/health/$']
X_FRAME_OPTIONS = 'DENY'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['accounts.permissions.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['accounts.permissions.ActiveAccount'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'EXCEPTION_HANDLER': 'accounts.errors.exception_handler',
    'UNAUTHENTICATED_USER': 'django.contrib.auth.models.AnonymousUser',
}
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '127.0.0.1')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '1025'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'false').lower() == 'true'
EMAIL_TIMEOUT = 5
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Nexora <noreply@hub.local>')
PASSWORD_RESET_TIMEOUT = 3600
# Accounts: a new account signs in once its address is confirmed by the emailed link.
EMAIL_VERIFICATION_REQUIRED = os.getenv('EMAIL_VERIFICATION_REQUIRED', 'true').lower() == 'true'
# ALTCHA proof of work on registration, login and email requests (self-hosted, no third party).
CAPTCHA_ENABLED = os.getenv('CAPTCHA_ENABLED', 'true').lower() == 'true'
ALTCHA_HMAC_KEY = os.getenv('ALTCHA_HMAC_KEY', '')
ALTCHA_MAX_NUMBER = int(os.getenv('ALTCHA_MAX_NUMBER', '100000'))
ALTCHA_EXPIRES = int(os.getenv('ALTCHA_EXPIRES', '600'))
VERIFICATION_TIMEOUT = 86400
MEDIA_ROOT = Path(os.getenv('DJANGO_MEDIA_ROOT', BASE_DIR / 'media'))
STATIC_URL = '/static/'
STATIC_ROOT = Path(os.getenv('DJANGO_STATIC_ROOT', BASE_DIR / 'staticfiles'))
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
# AI services (module « Résumés et illustrations »). Keys stay server-side only.
# GEMINI_API_KEY is shared with the teaching assistant (defined below); each module picks its own model.
REVISIONS_GEMINI_MODEL = os.getenv('REVISIONS_GEMINI_MODEL', 'gemini-3.5-flash')
# Tried before the local model when the first one is out of quota (empty = straight to Ollama).
REVISIONS_GEMINI_FALLBACK_MODEL = os.getenv('REVISIONS_GEMINI_FALLBACK_MODEL', 'gemini-3.5-flash-lite')
HF_TOKEN = os.getenv('HF_TOKEN', '')
HF_IMAGE_MODEL = os.getenv('HF_IMAGE_MODEL', 'stabilityai/stable-diffusion-3-medium-diffusers')
# Public Gradio Space running the image model (free GPU quota); empty = Inference Providers API.
HF_IMAGE_SPACE = os.getenv('HF_IMAGE_SPACE', 'black-forest-labs/FLUX.1-schnell')
AI_TIMEOUT_SECONDS = int(os.getenv('AI_TIMEOUT_SECONDS', '90'))
# Optional local fallback for summaries when Gemini is unavailable (empty = disabled).
# OLLAMA_MODEL and OLLAMA_TIMEOUT_SECONDS belong to the quiz generator (defined at the top); this module has its own,
# which still follow OLLAMA_MODEL when it is set in .env.
OLLAMA_URL = os.getenv('OLLAMA_URL', os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'))
REVISIONS_OLLAMA_MODEL = os.getenv('REVISIONS_OLLAMA_MODEL', os.getenv('OLLAMA_MODEL', ''))
REVISIONS_OLLAMA_TIMEOUT_SECONDS = int(os.getenv('REVISIONS_OLLAMA_TIMEOUT_SECONDS', '300'))
# AI generations run in the background: Celery + Redis when a broker is configured,
# otherwise an in-process thread pool ("sync" is reserved for automated tests).
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', '')
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
AI_JOB_BACKEND = os.getenv('AI_JOB_BACKEND', 'celery' if CELERY_BROKER_URL else 'thread')
AI_JOB_WORKERS = int(os.getenv('AI_JOB_WORKERS', '2'))

# Course resources and voice questions: PDF text extraction and Whisper transcription (disabled, fake, local or groq).
WHISPER_PROVIDER = os.getenv('WHISPER_PROVIDER', 'disabled').strip().lower()
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'small')
WHISPER_LANGUAGE = os.getenv('WHISPER_LANGUAGE', '').strip()
WHISPER_CPU_THREADS = int(os.getenv('WHISPER_CPU_THREADS', '2'))
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_WHISPER_MODEL = os.getenv('GROQ_WHISPER_MODEL', 'whisper-large-v3-turbo')
COURSES_PROCESS_INLINE = os.getenv('COURSES_PROCESS_INLINE', 'false').lower() == 'true'
COURSES_MAX_PDF_MB = float(os.getenv('COURSES_MAX_PDF_MB', '20'))
COURSES_MAX_AUDIO_MB = float(os.getenv('COURSES_MAX_AUDIO_MB', '25'))
COURSES_MAX_PDF_PAGES = int(os.getenv('COURSES_MAX_PDF_PAGES', '300'))
COURSES_MAX_AUDIO_SECONDS = int(os.getenv('COURSES_MAX_AUDIO_SECONDS', '7200'))
# Teaching assistant: Gemini answers (disabled, fake or gemini) and usage limits.
ASSISTANT_LLM_PROVIDER = os.getenv('ASSISTANT_LLM_PROVIDER', 'disabled').strip().lower()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite').strip()
GEMINI_FALLBACK_MODEL = os.getenv('GEMINI_FALLBACK_MODEL', 'gemini-3.1-flash-lite').strip()
GEMINI_TIMEOUT_SECONDS = int(os.getenv('GEMINI_TIMEOUT_SECONDS', '45'))
ASSISTANT_MIN_SCORE = float(os.getenv('ASSISTANT_MIN_SCORE', '1.0'))
ASSISTANT_DAILY_QUESTIONS = int(os.getenv('ASSISTANT_DAILY_QUESTIONS', '30'))
ASSISTANT_GLOBAL_DAILY_BUDGET = int(os.getenv('ASSISTANT_GLOBAL_DAILY_BUDGET', '400'))
ASSISTANT_VOICE_PER_HOUR = int(os.getenv('ASSISTANT_VOICE_PER_HOUR', '20'))
ASSISTANT_MAX_AUDIO_SECONDS = int(os.getenv('ASSISTANT_MAX_AUDIO_SECONDS', '60'))
ASSISTANT_MAX_AUDIO_MB = float(os.getenv('ASSISTANT_MAX_AUDIO_MB', '5'))
ASSISTANT_QUIZ_LOCK_HOURS = float(os.getenv('ASSISTANT_QUIZ_LOCK_HOURS', '3'))
# Revision planning: Gemini switch ('disabled', 'fake' or 'gemini') and limits; it shares the Gemini settings above.
GEMINI_PROVIDER = (os.getenv('GEMINI_PROVIDER') or 'disabled').strip().lower()
PLANNING_AI_DAILY_LIMIT = int(os.getenv('PLANNING_AI_DAILY_LIMIT') or '10')
PLANNING_AI_DAILY_BUDGET = int(os.getenv('PLANNING_AI_DAILY_BUDGET') or '400')

# Production logs go to the container output.
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.getenv('DJANGO_LOG_LEVEL', 'WARNING')},
}
