import os
from pathlib import Path
from django.contrib.messages import constants as message_constants
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _require_env(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"Wymagana zmienna środowiskowa '{name}' nie jest ustawiona.")
    return value


SECRET_KEY = _require_env('DJANGO_SECRET_KEY')
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['fc.sudomie.pl', 'localhost', '127.0.0.1', '0.0.0.0', '.trycloudflare.com']

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', 'https://fc.sudomie.pl').split(',')
    if origin.strip()
]

# OCR faktur (Faza 3) — funkcja płatna (plan Pro), pusty klucz = feature po prostu
# nie zadziała dla organizacji z dostępem, nie blokuje startu reszty aplikacji.
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_OCR_MODEL = os.environ.get('OPENAI_OCR_MODEL', 'gpt-4.1-mini')
# Feature flag: puste = brak tagu GA4 na stronie.
GA_MEASUREMENT_ID = os.environ.get('GA_MEASUREMENT_ID', '').strip()

INSTALLED_APPS = [
    'jazzmin',  # MUSI być przed django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'simple_history',
    'apps.core',
    'apps.accounts',
    'apps.ingredients',
    'apps.recipes',
    'apps.offers',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.analytics',
                'apps.core.context_processors.features',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'fc'),
        'USER': os.environ.get('DB_USER', 'fc'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'postgres'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pl'
TIME_ZONE = 'Europe/Warsaw'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

MESSAGE_TAGS = {message_constants.ERROR: 'danger'}

# Security — hardcoded, nie z env
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

if DEBUG:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

JAZZMIN_SETTINGS = {
    'site_title': 'FoodCost Admin',
    'site_header': 'FoodCost',
    'site_brand': 'FC',
    'site_logo': None,
    'welcome_sign': 'Panel administracyjny FoodCost',
    'copyright': 'sudomie.pl',
    'search_model': ['accounts.User', 'accounts.Organization'],
    'show_sidebar': True,
    'navigation_expanded': True,
    'icons': {
        'accounts.User': 'fas fa-user',
        'accounts.Organization': 'fas fa-building',
        'accounts.LoginEvent': 'fas fa-sign-in-alt',
        'ingredients.Ingredient': 'fas fa-carrot',
        'ingredients.Supplier': 'fas fa-truck',
        'ingredients.Category': 'fas fa-tags',
        'recipes.Recipe': 'fas fa-utensils',
    },
    'default_icon_parents': 'fas fa-chevron-circle-right',
    'default_icon_children': 'fas fa-circle',
}


# Feature flags (CLAUDE.md: new code ships switched off, turned on per deployment in .env).
# Oferty: moduł gotowy, ale bez akceptacji — kod i tabela są na produkcji, menu i adresy dopiero po włączeniu.
OFFERS_ENABLED = os.environ.get('OFFERS_ENABLED', 'False') == 'True'
# „Wypróbuj demo” (apps.core.demo): najwyżej DEMO_MAX piaskownic naraz, każda znika po DEMO_HOURS;
# DEMO_PER_HOUR nowych na godzinę łącznie (bez śledzenia IP). DEMO_MAX=0 ukrywa przycisk.
DEMO_MAX = int(os.environ.get('DEMO_MAX', '0'))
DEMO_HOURS = int(os.environ.get('DEMO_HOURS', '24'))
DEMO_PER_HOUR = int(os.environ.get('DEMO_PER_HOUR', '60'))

# Newsletter sudomie: pusty klucz = funkcja wyłączona (flaga). Klucz per aplikacja, nadany w sudomie.pl.
NEWSLETTER_URL = os.environ.get('NEWSLETTER_URL', 'https://sudomie.pl/chat-api/newsletter')
NEWSLETTER_KLUCZ = os.environ.get('NEWSLETTER_KLUCZ', '')
NEWSLETTER_TIMEOUT = float(os.environ.get('NEWSLETTER_TIMEOUT', '5'))
