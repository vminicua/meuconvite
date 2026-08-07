"""
Base settings shared by every environment.

Nothing secret lives here: every credential is read from the environment
(`.env` locally or platform environment variables). Environment specific overrides live in
`development.py` and `production.py`.
"""

from __future__ import annotations

from pathlib import Path

import environ

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
# base.py -> settings/ -> config/ -> project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# Read `.env` when present. Absent in some deployments (cPanel can inject
# real environment variables instead), which is fine.
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    environ.Env.read_env(str(ENV_FILE))

# ---------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

SITE_ID = 1
SITE_NAME = env("SITE_NAME", default="MeuConvite")
SITE_DOMAIN = env("SITE_DOMAIN", default="meuconvite.co.mz")
SITE_BASE_URL = env("SITE_BASE_URL", default="https://meuconvite.co.mz").rstrip("/")

# Twilio Programmable Messaging. Credenciais nunca são guardadas no código.
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_API_KEY_SID = env("TWILIO_API_KEY_SID", default="")
TWILIO_API_KEY_SECRET = env("TWILIO_API_KEY_SECRET", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_SMS_FROM = env("TWILIO_SMS_FROM", default="")
TWILIO_STATUS_CALLBACK_URL = env("TWILIO_STATUS_CALLBACK_URL", default="")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "django_filters",
]

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "audit.apps.AuditConfig",
    "weddings.apps.WeddingsConfig",
    "events.apps.EventsConfig",
    "guests.apps.GuestsConfig",
    "templates_manager.apps.TemplatesManagerConfig",
    "subscriptions.apps.SubscriptionsConfig",
    "platform_admin.apps.PlatformAdminConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.RequestContextMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.site_settings",
                "core.context_processors.staff_badges",
                "subscriptions.context_processors.upgrade_modal",
            ],
        },
    },
]

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
# A aplicação usa exclusivamente a base MariaDB remota configurada no `.env`.
# Não existe fallback SQLite: credenciais em falta devem falhar cedo e de forma visível.
DB_ENGINE = env("DB_ENGINE", default="django.db.backends.mysql")
_options: dict = {}
if "mysql" in DB_ENGINE:
    _options = {
        "charset": "utf8mb4",
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    }
    _ssl_ca = env("DB_SSL_CA", default="")
    if _ssl_ca:
        _options["ssl"] = {"ca": _ssl_ca}

DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default=""),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        "OPTIONS": _options,
    }
}

# ---------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Decisão do produto: o registo tem de ser o mais simples possível, por
# isso não são impostas regras de complexidade — qualquer palavra-passe é
# aceite. As palavras-passe continuam guardadas com o hashing padrão do
# Django (PBKDF2-SHA256) e a recuperação por email continua disponível.
#
# Para voltar a exigir palavras-passe fortes, basta repor os validadores:
#   UserAttributeSimilarityValidator, MinimumLengthValidator (min_length=8),
#   CommonPasswordValidator e NumericPasswordValidator.
AUTH_PASSWORD_VALIDATORS: list[dict] = []

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "weddings:list"
LOGOUT_REDIRECT_URL = "core:home"

# --- django-allauth (email based accounts) ---
# The custom user model has no username at all: the email is the identifier.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"
ACCOUNT_LOGIN_METHODS = {"email"}
# Registo com o mínimo: nome (acrescentado por accounts.forms.SignupForm),
# email e palavra-passe. Sem confirmação de palavra-passe e sem telefone —
# o resto preenche-se depois no perfil.
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
# "optional": quem cria conta entra imediatamente na aplicação. O email de
# confirmação continua a ser enviado, mas nunca bloqueia o acesso.
# Para deixar de enviar esse email por completo, mudar para "none".
ACCOUNT_EMAIL_VERIFICATION = "optional"
# O django-allauth impõe um mínimo próprio (6 caracteres) além dos
# validadores do Django. Também é retirado, pela mesma decisão de produto.
ACCOUNT_PASSWORD_MIN_LENGTH = 1
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[MeuConvite] "
ACCOUNT_CONFIRM_EMAIL_ON_GET = False
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_SESSION_REMEMBER = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
ACCOUNT_FORMS = {"signup": "accounts.forms.SignupForm"}
# Rate limits applied by allauth itself (per IP / per user).
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m/ip,5/5m/key",
    "signup": "10/h/ip",
    "reset_password": "5/h/ip,3/h/key",
    "reset_password_from_key": "10/h/ip",
    "confirm_email": "10/h/key",
}

# ---------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------
# A interface é em português de Portugal. `pt` é o código que o Django e o
# django-allauth usam para as traduções europeias (pt_BR é o Brasil).
LANGUAGE_CODE = env("LANGUAGE_CODE", default="pt")
TIME_ZONE = env("TIME_ZONE", default="Africa/Maputo")
USE_I18N = True
USE_TZ = True

# Apenas o português está activo: a interface é sempre em português,
# independentemente do idioma configurado no navegador do utilizador.
# A infra-estrutura de i18n fica pronta (LocaleMiddleware, LOCALE_PATHS,
# strings marcadas para tradução) — para acrescentar inglês mais tarde
# basta voltar a incluir ("en", "English") nesta lista.
LANGUAGES = [
    ("pt", "Português"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# Displayed formats (interface is Portuguese).
DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
TIME_FORMAT = "H:i"
DATE_INPUT_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]
USE_THOUSAND_SEPARATOR = True

# ---------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# Storage backends are declared through Django's STORAGES setting so a
# future move to S3/Azure Blob only requires changing this mapping.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Upload limits (also enforced per-field by core.validators).
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB per image
ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_IMAGE_CONTENT_TYPES = ["image/jpeg", "image/png", "image/webp"]
ALLOWED_AUDIO_EXTENSIONS = ["mp3", "m4a", "ogg"]
MAX_AUDIO_UPLOAD_SIZE = 15 * 1024 * 1024
ALLOWED_SPREADSHEET_EXTENSIONS = ["xlsx"]
MAX_SPREADSHEET_UPLOAD_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------------
# Sessions, messages, security defaults
# ---------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "meuconvite_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 days
CSRF_COOKIE_HTTPONLY = False  # HTMX reads the token from the cookie
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

# ---------------------------------------------------------------------
# Caching (Redis when available, local memory otherwise)
# ---------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "meuconvite-default",
        }
    }

# ---------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", default="MeuConvite <noreply@meuconvite.co.mz>"
)
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="info@meuconvite.co.mz")

# ---------------------------------------------------------------------
# Pagamentos (subscrições)
# ---------------------------------------------------------------------
# Checkout M-Pesa processado pela Payzeno. A chave pode ser definida por
# variável de ambiente ou, cifrada, na administração da plataforma.
PAYZENO_ENABLED = env.bool("PAYZENO_ENABLED", default=False)
PAYZENO_API_KEY = env("PAYZENO_API_KEY", default="")
PAYZENO_WEBHOOK_SECRET = env("PAYZENO_WEBHOOK_SECRET", default="")
PAYZENO_BASE_URL = env("PAYZENO_BASE_URL", default="https://api.payzeno.io")
PAYZENO_TIMEOUT_SECONDS = env.int("PAYZENO_TIMEOUT_SECONDS", default=20)

# Contactos antigos são mantidos apenas para pagamentos manuais já existentes.
MPESA_NUMBER = env("MPESA_NUMBER", default="840297715")
MPESA_ACCOUNT_NAME = env("MPESA_ACCOUNT_NAME", default="MeuConvite")
WHATSAPP_NUMBER = env("WHATSAPP_NUMBER", default="+258840297715")

# ---------------------------------------------------------------------
# Application specific
# ---------------------------------------------------------------------
# Rate limiting for public pages (invitation, RSVP, check-in scanning).
PUBLIC_RATE_LIMITS = {
    "invitation_view": (60, 60 * 60),  # 60 requests per hour, per IP
    "rsvp_submit": (20, 60 * 60),
    "public_wedding": (120, 60 * 60),
}
