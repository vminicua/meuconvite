from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import DeliveryStatus, EventReminderDelivery


def invitation_url(guest) -> str:
    return f"{settings.SITE_BASE_URL.rstrip('/')}/convite/{guest.invitation_token}/"


def send_event_reminder(*, guest, days_before: int) -> EventReminderDelivery:
    """Envia uma vez cada marco de lembrete; falhas podem ser tentadas novamente."""
    wedding = guest.wedding
    subject = f"{wedding.display_names}: faltam {days_before} dia(s) para o evento"
    if days_before == 1:
        subject = f"{wedding.display_names}: o evento é amanhã"
    context = {
        "guest": guest,
        "wedding": wedding,
        "days_before": days_before,
        "invitation_url": invitation_url(guest),
    }
    delivery, _ = EventReminderDelivery.objects.get_or_create(
        guest=guest,
        event_date=wedding.main_date,
        days_before=days_before,
        defaults={
            "wedding": wedding,
            "destination": guest.email,
            "subject": subject,
        },
    )
    if delivery.status == DeliveryStatus.SENT:
        return delivery

    delivery.destination = guest.email
    delivery.subject = subject
    text_body = render_to_string("emails/event_reminder.txt", context)
    html_body = render_to_string("emails/event_reminder.html", context)
    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [guest.email])
    message.attach_alternative(html_body, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        delivery.status = DeliveryStatus.FAILED
        delivery.error_message = str(exc)[:500]
        delivery.save()
        raise
    delivery.status = DeliveryStatus.SENT
    delivery.sent_at = timezone.now()
    delivery.error_message = ""
    delivery.save()
    return delivery
