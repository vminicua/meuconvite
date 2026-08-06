"""Configuração operacional editável pela equipa da plataforma."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


def _cipher() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii") if value else ""


def _decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


class PlatformConfiguration(TimeStampedModel):
    """Singleton com integrações; segredos são cifrados antes de chegar à base de dados."""

    key = models.CharField(max_length=20, primary_key=True, default="default", editable=False)
    twilio_account_sid_secret = models.TextField(blank=True, editable=False)
    twilio_api_key_sid_secret = models.TextField(blank=True, editable=False)
    twilio_api_key_secret_secret = models.TextField(blank=True, editable=False)
    twilio_auth_token_secret = models.TextField(blank=True, editable=False)
    twilio_sms_from = models.CharField(_("remetente SMS"), max_length=40, blank=True)
    twilio_status_callback_url = models.URLField(_("URL de estados Twilio"), blank=True)

    payzeno_api_key_secret = models.TextField(blank=True, editable=False)
    payzeno_webhook_secret_secret = models.TextField(blank=True, editable=False)
    payzeno_enabled = models.BooleanField(_("activar pagamentos Payzeno"), default=False)
    payzeno_base_url = models.URLField(
        _("URL da API Payzeno"), default="https://api.payzeno.io"
    )

    mpesa_number = models.CharField(_("número M-Pesa"), max_length=40, blank=True)
    mpesa_account_name = models.CharField(_("titular M-Pesa"), max_length=100, blank=True)
    whatsapp_number = models.CharField(_("WhatsApp de pagamentos"), max_length=40, blank=True)

    class Meta:
        verbose_name = _("configuração da plataforma")
        verbose_name_plural = _("configuração da plataforma")

    @classmethod
    def load(cls) -> "PlatformConfiguration":
        obj, _created = cls.objects.get_or_create(
            key="default",
            defaults={
                "twilio_sms_from": getattr(settings, "TWILIO_SMS_FROM", ""),
                "twilio_status_callback_url": getattr(settings, "TWILIO_STATUS_CALLBACK_URL", ""),
                "payzeno_enabled": getattr(settings, "PAYZENO_ENABLED", False),
                "payzeno_base_url": getattr(
                    settings, "PAYZENO_BASE_URL", "https://api.payzeno.io"
                ),
                "mpesa_number": getattr(settings, "MPESA_NUMBER", ""),
                "mpesa_account_name": getattr(settings, "MPESA_ACCOUNT_NAME", ""),
                "whatsapp_number": getattr(settings, "WHATSAPP_NUMBER", ""),
            },
        )
        return obj

    def set_secret(self, name: str, value: str) -> None:
        setattr(self, f"{name}_secret", _encrypt((value or "").strip()))

    def get_secret(self, name: str) -> str:
        return _decrypt(getattr(self, f"{name}_secret", ""))

    def has_secret(self, name: str) -> bool:
        return bool(self.get_secret(name))


def configured_value(name: str, fallback: str = "") -> str:
    """Valor da administração quando definido; caso contrário, variável de ambiente."""
    try:
        config = PlatformConfiguration.objects.filter(key="default").first()
        if config is None:
            return getattr(settings, name.upper(), fallback)
        if name in {
            "twilio_account_sid",
            "twilio_api_key_sid",
            "twilio_api_key_secret",
            "twilio_auth_token",
            "payzeno_api_key",
            "payzeno_webhook_secret",
        }:
            value = config.get_secret(name)
        else:
            value = getattr(config, name, "")
    except Exception:
        value = ""
    return value or getattr(settings, name.upper(), fallback)
