"""
sam-yosh tadbirkor.uz — Django settings.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(env(key, default)).lower() in ('1', 'true', 'yes', 'on')


SECRET_KEY = env('SECRET_KEY', 'django-insecure-dev-only-change-me')
DEBUG = env_bool('DEBUG', True)
ALLOWED_HOSTS = [h.strip() for h in env('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

# Docker ichida Next server tomonda `http://web:8000` ga murojaat qiladi —
# `Host` sarlavhasi `web` bo'lib keladi. Ro'yxatda bo'lmasa Django 400
# qaytaradi va front hech qanday ma'lumot ololmaydi.
if 'web' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('web')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]


# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

# Next.js frontend uchun REST API
THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.core',
    'apps.content',
    'apps.business',
    'apps.startups',
    'apps.initiatives',
    'apps.cabinet',
    'apps.panel',
    'apps.abroad',
    'apps.api',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if env_bool('USE_WHITENOISE', False):
    # Docker'da statik fayllarni Django ham bera oladi (nginx bilan birga)
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# Database — PostgreSQL. Postgres hali o'rnatilmagan bo'lsa .env da USE_SQLITE=1 qo'ying.

if env_bool('USE_SQLITE', False):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME', 'samyosh'),
            'USER': env('DB_USER', 'postgres'),
            'PASSWORD': env('DB_PASSWORD', 'postgres'),
            'HOST': env('DB_HOST', '127.0.0.1'),
            'PORT': env('DB_PORT', '5432'),
            'CONN_MAX_AGE': 60,
        }
    }


# Auth

AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.EmailOrPhoneBackend']
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'cabinet:dashboard'
LOGOUT_REDIRECT_URL = 'core:home'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Telegram bot orqali kirish

TELEGRAM_BOT_USERNAME = env('TELEGRAM_BOT_USERNAME', 'yoshtadbirkorlarbot')
TELEGRAM_API_SECRET = env('TELEGRAM_API_SECRET', '')

# Tashqi manzil (https://mentadbirkor.uz). API rasm havolalarini shu bilan
# yasaydi — sayt Django'ga ichki `web:8000` orqali murojaat qilsa ham
# brauzerga to'g'ri manzil boradi. Lokalda bo'sh qoladi.
SITE_URL = env('SITE_URL', '').rstrip('/')


# Internationalization

LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / 'locale']


# Static & media

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'
                    if env_bool('USE_WHITENOISE', False)
                    else 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'


# Email (dev — konsolga chiqadi)

EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'sam-yosh tadbirkor <info@mentadbirkor.uz>')


# Xavfsizlik (production)

if not DEBUG:
    # nginx HTTPS ni o'zi hal qiladi, Django faqat sarlavhaga ishonadi
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', False)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# REST API (Next.js frontend uchun)
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    # Ko'rish hamma uchun ochiq; yozish amallari view darajasida yopiladi
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'UNAUTHENTICATED_USER': 'django.contrib.auth.models.AnonymousUser',
    'DEFAULT_THROTTLE_CLASSES': [],
    # Parol tanlashga urinishni cheklaymiz
    'DEFAULT_THROTTLE_RATES': {'login': '10/min'},
}

# Brauzerda API'ni ko'rib chiqish faqat dev rejimida
if DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'].append(
        'rest_framework.renderers.BrowsableAPIRenderer')

# Kirish 24 soat amal qiladi, keyin qayta kirish so'raladi. Token
# yangilanganda muddat uzaymasin — shuning uchun aylantirish o'chiq.
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=24),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Frontend qaysi manzillardan murojaat qila oladi
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in
    env('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
