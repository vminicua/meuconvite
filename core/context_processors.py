from __future__ import annotations

import os

from django.conf import settings
from django.http import HttpRequest

# O caminho do Django Admin é configurável (ver config/urls.py); os
# atalhos da área de administração precisam de o conhecer.
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "django-admin/").strip("/") + "/"


def site_settings(request: HttpRequest) -> dict:
    """Values every template needs (branding, absolute URLs, debug flag)."""
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "MeuConvite"),
        "SITE_DOMAIN": getattr(settings, "SITE_DOMAIN", "meuconvite.co.mz"),
        "SITE_BASE_URL": getattr(settings, "SITE_BASE_URL", ""),
        "SUPPORT_EMAIL": getattr(settings, "SUPPORT_EMAIL", ""),
        "ADMIN_URL": ADMIN_URL,
        "DEBUG": settings.DEBUG,
    }


def staff_badges(request: HttpRequest) -> dict:
    """
    Contadores mostrados à equipa MeuConvite no menu.

    A consulta só é feita para quem é `is_staff` — os restantes
    utilizadores não pagam nada por isto.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff:
        return {}

    from subscriptions.models import Payment, PaymentStatus

    return {
        "pending_payments_count": Payment.objects.filter(
            status__in=[PaymentStatus.AWAITING_PROOF, PaymentStatus.UNDER_REVIEW]
        ).count()
    }
