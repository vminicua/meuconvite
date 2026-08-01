"""Envio de convites por SMS e composição de mensagens para WhatsApp."""

from __future__ import annotations

import re
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import DeliveryStatus, InvitationChannel, InvitationDelivery
from weddings.models import DEFAULT_SMS_INVITATION_MESSAGE


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
        first_name = (guest.full_name or "Convidado").split()[0]
        template = guest.wedding.sms_invitation_message or DEFAULT_SMS_INVITATION_MESSAGE
        try:
            return template.format(
                nome=first_name[:40],
                evento=guest.wedding.display_names,
                link=invitation_url,
            )
        except (KeyError, ValueError):
            return f"Convite para {first_name[:20]}: {invitation_url}"
    return (
        f"Olá {guest.full_name}! 💛\n\n"
        f"Somos {guest.wedding.display_names} e queremos muito celebrar este dia contigo.\n\n"
        f"✨ Preparámos um convite especial para ti. Abre-o e confirma a tua presença:\n"
        f"{invitation_url}\n\n"
        f"Com carinho,\n{guest.wedding.display_names}"
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
        raise ValidationError("Escolha SMS ou WhatsApp.")
    if channel == InvitationChannel.WHATSAPP:
        raise ValidationError(
            "O WhatsApp é aberto directamente no seu dispositivo e não é enviado pela Twilio."
        )
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


def notify_couple(*, guest, body: str) -> list[InvitationDelivery]:
    """Envia uma notificação operacional aos noivos, sem consumir a quota de convites."""
    from platform_admin.models import configured_value
    from weddings.models import WeddingRole

    wedding = guest.wedding
    users = [wedding.owner]
    users.extend(
        member.user
        for member in wedding.members.filter(
            role=WeddingRole.SPOUSE, is_active=True
        ).select_related("user")
        if member.user.is_active
    )
    recipients: list[str] = []
    candidates = [wedding.notification_phone_primary, wedding.notification_phone_secondary]
    candidates.extend(user.phone for user in users)
    for candidate in candidates:
        try:
            phone = normalize_phone(candidate)
        except ValidationError:
            continue
        if phone not in recipients:
            recipients.append(phone)

    sender = configured_value("twilio_sms_from")
    deliveries: list[InvitationDelivery] = []
    for phone in recipients:
        delivery = InvitationDelivery.objects.create(
            wedding=wedding,
            guest=guest,
            channel=InvitationChannel.SMS,
            destination=phone,
            message_body=body,
            counts_toward_limit=False,
        )
        deliveries.append(delivery)
        if not sender:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = "O remetente SMS ainda não está configurado."
            delivery.save(update_fields=["status", "error_message", "updated_at"])
            continue
        arguments = {"body": body, "from_": sender, "to": phone}
        callback = status_callback_url()
        if callback:
            arguments["status_callback"] = callback
        try:
            message = _client().messages.create(**arguments)
        except Exception as exc:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_code = str(getattr(exc, "code", "") or "")[:30]
            delivery.error_message = str(getattr(exc, "msg", "") or exc)[:500]
            delivery.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            continue
        delivery.provider_sid = message.sid
        delivery.status = message.status if message.status in DeliveryStatus.values else DeliveryStatus.QUEUED
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["provider_sid", "status", "sent_at", "updated_at"])
    return deliveries


def update_delivery_status(*, provider_sid: str, status: str, error_code: str = ""):
    delivery = InvitationDelivery.objects.filter(provider_sid=provider_sid).first()
    if delivery is None:
        return None
    if status in DeliveryStatus.values:
        delivery.status = status
    delivery.error_code = (error_code or "")[:30]
    delivery.save(update_fields=["status", "error_code", "updated_at"])
    return delivery
