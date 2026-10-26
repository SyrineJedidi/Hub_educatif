import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('Définissez DJANGO_SECRET_KEY dans backend/.env.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = [
    'config.apps.MongoAuthConfig', 'config.apps.MongoContentTypesConfig',
    'django.contrib.sessions', 'django.contrib.staticfiles',
    'django_mongodb_backend', 'rest_framework', 'accounts', 'classrooms', 'attendance', 'quizzes', 'assistant',
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
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 60 * 60 * 8
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'accounts.errors.csrf_failure'
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
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
VERIFICATION_TIMEOUT = 86400
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_URL = '/static/'
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
# Voice questions: Whisper transcription (disabled, fake, local or groq), shared with the course resources.
WHISPER_PROVIDER = os.getenv('WHISPER_PROVIDER', 'disabled').strip().lower()
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'small')
WHISPER_LANGUAGE = os.getenv('WHISPER_LANGUAGE', '').strip()
WHISPER_CPU_THREADS = int(os.getenv('WHISPER_CPU_THREADS', '2'))
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_WHISPER_MODEL = os.getenv('GROQ_WHISPER_MODEL', 'whisper-large-v3-turbo')
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
