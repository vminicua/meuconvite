#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_environment() -> None:
    """
    Read `.env` *before* choosing the settings module.

    This matters: on the server the `.env` sets
    `DJANGO_SETTINGS_MODULE=config.settings.production`, so management
    commands run against the real database. Without this, `manage.py`
    would silently fall back to the development settings (SQLite) even in
    production.
    """
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    try:
        import environ
    except ImportError:  # pragma: no cover - dependency not installed yet
        return
    environ.Env.read_env(str(env_file))


def main() -> None:
    _load_environment()
    # Only used when neither the shell nor `.env` defined it.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

    # Printed to stderr so it never pollutes command output, and so that
    # running a command against the wrong environment is impossible to miss.
    # `RUN_MAIN` is set by the autoreloader's child process — without this
    # guard the line would appear twice on every `runserver`.
    if os.environ.get("RUN_MAIN") != "true":
        print(f"[meuconvite] settings: {os.environ['DJANGO_SETTINGS_MODULE']}", file=sys.stderr)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ImportError(
            "Django is not installed or the virtual environment is not active. "
            "Run: pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
