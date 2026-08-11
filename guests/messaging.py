"""Envio de convites por SMS e composição de mensagens para WhatsApp."""

from __future__ import annotations

import hashlib
import re
from email.utils import formataddr, parseaddr
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from core.utils import strip_accents
from .models import DeliveryStatus, InvitationChannel, InvitationDelivery
from weddings.models import (
    DEFAULT_SMS_INVITATION_MESSAGE,
    DEFAULT_WHATSAPP_INVITATION_MESSAGE,
    SMS_MAX_LENGTH,
)


WHATSAPP_PREVIEW_REVISION = "4"


def _sms_ascii(value: str, limit: int) -> str:
    """Transliterate dynamic content and retain printable ASCII only."""
    value = strip_accents(value or "")
    return "".join(char for char in value if 32 <= ord(char) <= 126)[:limit]


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


def whatsapp_cover_version(wedding) -> str:
    """Versão curta que renova a pré-visualização quando a capa muda."""
    cover_identity = (
        f"{wedding.selected_template}:{getattr(wedding.cover_image, 'name', '')}:"
        f"{WHATSAPP_PREVIEW_REVISION}"
    )
    return hashlib.sha256(cover_identity.encode("utf-8")).hexdigest()[:6]


def invitation_message(guest, invitation_url: str, channel: str) -> str:
    if channel == InvitationChannel.SMS:
        first_name = _sms_ascii((guest.full_name or "Convidado").split()[0], 20)
        template = guest.wedding.sms_invitation_message or DEFAULT_SMS_INVITATION_MESSAGE
        try:
            body = template.format(
                nome=first_name,
                evento=_sms_ascii(guest.wedding.display_names, 40),
                link=invitation_url,
            )
        except (KeyError, ValueError):
            body = f"Convite para {first_name}: {invitation_url}"
        if not body.isascii():
            raise ValidationError("A mensagem SMS contem acentos, emojis ou caracteres nao permitidos.")
        if len(body) > SMS_MAX_LENGTH:
            raise ValidationError(
                f"A mensagem SMS tem {len(body)} caracteres. O limite e {SMS_MAX_LENGTH}. "
                "Reduza a mensagem nos detalhes do evento."
            )
        return body
    cover_version = whatsapp_cover_version(guest.wedding)
    separator = "&" if "?" in invitation_url else "?"
    whatsapp_url = f"{invitation_url}{separator}v={cover_version}"
    event_names = re.sub(r"\bAntonio\b", "António", guest.wedding.display_names)
    template = (
        guest.wedding.whatsapp_invitation_message
        or DEFAULT_WHATSAPP_INVITATION_MESSAGE
    )
    try:
        return template.format(
            nome=guest.full_name,
            evento=event_names,
            link=whatsapp_url,
        )
    except (KeyError, ValueError):
        return DEFAULT_WHATSAPP_INVITATION_MESSAGE.format(
            nome=guest.full_name,
            evento=event_names,
            link=whatsapp_url,
        )


def whatsapp_invitation_url(*, guest, invitation_url: str) -> str:
    """Cria uma conversa wa.me com destinatário e convite pré-preenchidos."""
    phone = normalize_phone(guest.phone)
    body = invitation_message(guest, invitation_url, InvitationChannel.WHATSAPP)
    return f"https://wa.me/{phone.removeprefix('+')}?{urlencode({'text': body})}"


def _client():
    from twilio.rest import Client
    from platform_admin.models import configured_value

    account_sid = configured_value("twilio_account_sid")
    api_key_sid = configured_value("twilio_api_key_sid")
    api_key_secret = configured_value("twilio_api_key_secret")
    if not all((account_sid, api_key_sid, api_key_secret)):
        raise ValidationError("O serviço Twilio ainda não está configurado.")
    return Client(api_key_sid, api_key_secret, account_sid)


def status_callback_url() -> str:
    from platform_admin.models import configured_value

    callback = configured_value("twilio_status_callback_url").strip()
    return callback if callback.startswith("https://") else ""


def send_invitation(*, guest, channel: str, invitation_url: str, actor) -> InvitationDelivery:
    if channel not in InvitationChannel.values:
        raise ValidationError("Escolha SMS, WhatsApp ou email.")
    if channel == InvitationChannel.WHATSAPP:
        raise ValidationError(
            "O WhatsApp é aberto directamente no seu dispositivo e não é enviado pela Twilio."
        )
    if channel == InvitationChannel.EMAIL:
        if not guest.email:
            raise ValidationError("Este convidado não tem um endereço de email.")
        subject = f"Convite de {guest.wedding.display_names}"
        context = {"guest": guest, "wedding": guest.wedding, "invitation_url": invitation_url}
        body = render_to_string("emails/invitation.txt", context)
        html_body = render_to_string("emails/invitation.html", context)
        _configured_name, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
        address = address or settings.DEFAULT_FROM_EMAIL
        sender_name = re.sub(r"[\r\n]+", " ", guest.wedding.display_names).strip()
        sender = formataddr((sender_name, address))
        delivery = InvitationDelivery.objects.create(
            wedding=guest.wedding,
            guest=guest,
            channel=channel,
            destination=guest.email,
            message_body=body,
            provider="smtp",
            sent_by=actor,
            counts_toward_limit=False,
        )
        message = EmailMultiAlternatives(subject, body, sender, [guest.email])
        message.attach_alternative(html_body, "text/html")
        try:
            message.send(fail_silently=False)
        except Exception as exc:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(exc)[:500]
            delivery.save(update_fields=["status", "error_message", "updated_at"])
            raise ValidationError("Não foi possível enviar o email. Tente novamente.") from exc
        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "sent_at", "updated_at"])
        return delivery
    from subscriptions.services import check_can_send_sms

    check_can_send_sms(guest.wedding)
    phone = normalize_phone(guest.phone)
    destination = phone
    from platform_admin.models import configured_value

    sender = configured_value("twilio_sms_from")
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
