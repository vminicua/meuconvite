"""Envio de convites por SMS e composição de mensagens para WhatsApp."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import DeliveryStatus, InvitationChannel, InvitationDelivery


def normalize_phone(value: str) -> str:
    """Normaliza números moçambicanos e E.164 sem inventar destinos."""
    raw = (value or "").strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise ValidationError("Este convidado não tem um telefone válido.")
    if has_plus:
        normalized = f"+{digits}"
    elif digits.startswith("258") and len(digits) == 12:
        normalized = f"+{digits}"
    elif len(digits) == 9 and digits.startswith(("8", "2")):
        normalized = f"+258{digits}"
    else:
        raise ValidationError(
            "Use o telefone em formato internacional, por exemplo +258840000000."
        )
    if not 8 <= len(digits) <= 15:
        raise ValidationError("O telefone indicado não é válido.")
    return normalized


def invitation_message(guest, invitation_url: str, channel: str) -> str:
    if channel == InvitationChannel.SMS:
        # Contas Trial acrescentam um prefixo próprio. Mantemos o SMS em GSM-7
        # e curto para não ultrapassar o limite de um segmento do Twilio Trial.
        first_name = (guest.full_name or "Convidado").split()[0]
        first_name = unicodedata.normalize("NFKD", first_name).encode("ascii", "ignore").decode()
        return f"Convite para {first_name[:20]}: {invitation_url}"
    return (
        f"Olá {guest.full_name}! {guest.wedding.display_names} convidam-no(a) "
        f"para celebrar este momento especial. Abra o convite e confirme a sua presença: "
        f"{invitation_url}"
    )


def whatsapp_invitation_url(*, guest, invitation_url: str) -> str:
    """Cria uma conversa wa.me com destinatário e convite pré-preenchidos."""
    phone = normalize_phone(guest.phone)
    body = invitation_message(guest, invitation_url, InvitationChannel.WHATSAPP)
    return f"https://wa.me/{phone.removeprefix('+')}?{urlencode({'text': body})}"


def _client():
    from twilio.rest import Client

    account_sid = settings.TWILIO_ACCOUNT_SID
    api_key_sid = settings.TWILIO_API_KEY_SID
    api_key_secret = settings.TWILIO_API_KEY_SECRET
    if not all((account_sid, api_key_sid, api_key_secret)):
        raise ValidationError("O serviço Twilio ainda não está configurado.")
    return Client(api_key_sid, api_key_secret, account_sid)


def status_callback_url() -> str:
    callback = settings.TWILIO_STATUS_CALLBACK_URL.strip()
    return callback if callback.startswith("https://") else ""


def send_invitation(*, guest, channel: str, invitation_url: str, actor) -> InvitationDelivery:
    if channel not in InvitationChannel.values:
        raise ValidationError("Escolha SMS ou WhatsApp.")
    if channel == InvitationChannel.WHATSAPP:
        raise ValidationError(
            "O WhatsApp é aberto directamente no seu dispositivo e não é enviado pela Twilio."
        )
    phone = normalize_phone(guest.phone)
    destination = phone
    sender = settings.TWILIO_SMS_FROM
    if not sender:
        raise ValidationError(f"O remetente de {channel.upper()} ainda não está configurado.")

    body = invitation_message(guest, invitation_url, channel)
    delivery = InvitationDelivery.objects.create(
        wedding=guest.wedding,
        guest=guest,
        channel=channel,
        destination=destination,
        message_body=body,
        sent_by=actor,
    )
    arguments = {"body": body, "from_": sender, "to": destination}
    callback = status_callback_url()
    if callback:
        arguments["status_callback"] = callback

    try:
        message = _client().messages.create(**arguments)
    except Exception as exc:
        error_code = str(getattr(exc, "code", "") or "")
        safe_message = str(getattr(exc, "msg", "") or exc)[:500]
        delivery.status = DeliveryStatus.FAILED
        delivery.error_code = error_code
        delivery.error_message = safe_message
        delivery.save(update_fields=["status", "error_code", "error_message", "updated_at"])
        if error_code == "21608":
            raise ValidationError(
                "A conta Twilio Trial só envia SMS para números verificados. "
                "Verifique este telefone na consola Twilio."
            ) from exc
        raise ValidationError(f"O Twilio recusou o envio ({error_code or 'erro de comunicação'}).") from exc

    delivery.provider_sid = message.sid
    delivery.status = (
        message.status if message.status in DeliveryStatus.values else DeliveryStatus.QUEUED
    )
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=["provider_sid", "status", "sent_at", "updated_at"])
    return delivery


def update_delivery_status(*, provider_sid: str, status: str, error_code: str = ""):
    delivery = InvitationDelivery.objects.filter(provider_sid=provider_sid).first()
    if delivery is None:
        return None
    if status in DeliveryStatus.values:
        delivery.status = status
    delivery.error_code = (error_code or "")[:30]
    delivery.save(update_fields=["status", "error_code", "updated_at"])
    return delivery
