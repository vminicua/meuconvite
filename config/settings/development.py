"""Local development settings. Never use in production."""

from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env  # noqa: F401

# This module *is* the development environment: DEBUG and ALLOWED_HOSTS are
# fixed here instead of read from `.env`, because `.env` holds the production
# values (domain meuconvite.co.mz, DEBUG=False) used by config.settings.production.
DEBUG = True

# A throwaway key is acceptable locally; production refuses to start without one.
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="dev-only-insecure-key-do-not-use-in-production",
)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver", ".localhost"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

SITE_BASE_URL = env("SITE_BASE_URL", default="http://localhost:8000")

# The `.env` file carries the *production* database credentials (MariaDB on
# the cPanel host), which are not reachable from a developer machine. Local
# development therefore always uses SQLite unless explicitly asked otherwise
# with DEV_DB_FROM_ENV=True (useful when working through an SSH tunnel).
if not env.bool("DEV_DB_FROM_ENV", default=False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
            "OPTIONS": {"transaction_mode": "IMMEDIATE"},
        }
    }

# Emails are printed to the console instead of being sent.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Relaxed cookie flags so the site works over plain HTTP locally.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

INTERNAL_IPS = ["127.0.0.1"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "meuconvite": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
