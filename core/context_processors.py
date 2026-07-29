from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest


def site_settings(request: HttpRequest) -> dict:
    """Values every template needs (branding, absolute URLs, debug flag)."""
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "MeuConvite"),
        "SITE_DOMAIN": getattr(settings, "SITE_DOMAIN", "meuconvite.co.mz"),
        "SITE_BASE_URL": getattr(settings, "SITE_BASE_URL", ""),
        "DEBUG": settings.DEBUG,
    }
