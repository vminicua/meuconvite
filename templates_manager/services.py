"""
Construção do contexto do convite.

Um sítio só a decidir o que o convite mostra, para a pré-visualização de
hoje e a página pública do convidado (fase 2) desenharem exactamente o
mesmo — mudando apenas quem é o convidado e se o RSVP está activo.
"""

from __future__ import annotations

from datetime import datetime, time

from django.utils import timezone

from .models import InvitationTemplate

# Nome usado quando ainda não há um convidado real (pré-visualização).
DEMO_GUEST_NAME = "Élio Nhaca"


def _first_moment(wedding):
    from events.models import WeddingEvent

    return (
        WeddingEvent.objects.filter(wedding=wedding, is_active=True)
        .order_by("date", "start_time", "display_order")
        .first()
    )


def _countdown_target(wedding, first_moment) -> datetime | None:
    """Momento exacto para onde a contagem regressiva aponta."""
    if not wedding.main_date:
        return None
    start = first_moment.start_time if first_moment and first_moment.start_time else time(9, 0)
    naive = datetime.combine(wedding.main_date, start)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def invitation_context(
    wedding,
    template: InvitationTemplate,
    *,
    guest_name: str | None = None,
    seats: int | None = None,
    is_preview: bool = False,
    use_event_colours: bool = True,
) -> dict:
    """
    Tudo o que os layouts de convite precisam.

    `use_event_colours` distingue dois casos: no convite do evento as cores
    escolhidas pelos noivos mandam; ao espreitar um template diferente,
    mostra-se a paleta original desse template — caso contrário
    experimentar um template novo mostrava sempre as cores antigas.
    """
    from events.models import ScheduleItem, WeddingLocation

    category = wedding.category
    first_moment = _first_moment(wedding)

    monogram = wedding.primary_short_name[:1].upper()
    if wedding.secondary_short_name:
        monogram = f"{monogram}{wedding.secondary_short_name[:1].upper()}"

    return {
        "wedding": wedding,
        "template": template,
        "css_variables": (
            template.css_variables(wedding.primary_color, wedding.secondary_color)
            if use_event_colours
            else template.css_variables()
        ),
        "invitation_eyebrow": category.name if category else "Convite",
        "invitation_greeting": (
            category.invitation_greeting if category else "convida-o para"
        ),
        "monogram": monogram,
        "guest_name": guest_name,
        "seats": seats,
        "first_moment": first_moment,
        "countdown_target": _countdown_target(wedding, first_moment),
        "schedule": list(
            ScheduleItem.objects.filter(wedding=wedding, is_public=True)
            .select_related("event", "location")
            .order_by("display_order", "start_time")
        ),
        "locations": list(
            WeddingLocation.objects.filter(wedding=wedding).order_by("display_order", "name")
        ),
        "is_preview": is_preview,
        "show_branding": _show_branding(wedding),
    }


def _show_branding(wedding) -> bool:
    """A marca da plataforma só desaparece nos pacotes que o permitem."""
    from subscriptions.services import limits

    return not limits(wedding).removes_branding
