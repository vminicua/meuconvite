"""Local development settings. Never use in production."""

from __future__ import annotations

import os
import sys

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

# ---------------------------------------------------------------------
# Base de dados
# ---------------------------------------------------------------------
# Por decisão do projecto, o desenvolvimento corre contra a MESMA base de
# dados de produção (MariaDB no cPanel). Como essa base só aceita ligações
# a partir do próprio servidor, o acesso faz-se por um túnel SSH:
#
#     python scripts/dev_tunnel.py      (deixar a correr)
#     python manage.py runserver
#
# DEV_DB_HOST/DEV_DB_PORT apontam para a ponta local do túnel; as restantes
# credenciais são as mesmas do `.env`.
_dev_db_host = env("DEV_DB_HOST", default="")
_dev_db_port = env("DEV_DB_PORT", default="")
if _dev_db_host:
    DATABASES["default"]["HOST"] = _dev_db_host  # noqa: F405
if _dev_db_port:
    DATABASES["default"]["PORT"] = _dev_db_port  # noqa: F405

if DATABASES["default"]["ENGINE"].endswith("mysql"):  # noqa: F405
    # A ligação passa por um túnel SSH que pode ser restabelecido: não
    # reutilizar conexões evita ficar preso a um socket já morto.
    DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
    DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405
    DATABASES["default"]["OPTIONS"]["connect_timeout"] = 10  # noqa: F405

    if os.environ.get("RUN_MAIN") != "true":
        print(
            "[meuconvite] ATENÇÃO: o ambiente local está ligado à base de dados de "
            f"PRODUÇÃO ({DATABASES['default']['NAME']}@{DATABASES['default']['HOST']}:"  # noqa: F405
            f"{DATABASES['default']['PORT']}). "  # noqa: F405
            "O túnel (scripts/dev_tunnel.py) tem de estar a correr.",
            file=sys.stderr,
        )

# Keep console email as the safe development default, but honour an explicit
# SMTP configuration in ``.env``.  This lets local password-reset flows work
# end to end when the developer intentionally supplies the real mailbox.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

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
