"""
Construção do contexto do convite.

Um sítio só a decidir o que o convite mostra, para a pré-visualização de
hoje e a página pública do convidado (fase 2) desenharem exactamente o
mesmo — mudando apenas quem é o convidado e se o RSVP está activo.
"""

from __future__ import annotations

from datetime import datetime, time

from django.conf import settings
from django.utils import timezone

import segno

from weddings.invitation_texts import InvitationTexts

from .models import InvitationTemplate, _relative_luminance

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
    guest=None,
    is_preview: bool = False,
    use_event_colours: bool = True,
    include_qr: bool = True,
) -> dict:
    """
    Tudo o que os layouts de convite precisam.

    `use_event_colours` distingue dois casos: no convite do evento as cores
    escolhidas pelos noivos mandam; ao espreitar um template diferente,
    mostra-se a paleta original desse template — caso contrário
    experimentar um template novo mostrava sempre as cores antigas.
    """
    from events.models import ScheduleItem, WeddingEvent, WeddingLocation

    category = wedding.category
    first_moment = _first_moment(wedding)

    monogram = wedding.primary_short_name[:1].upper()
    if wedding.secondary_short_name:
        monogram = f"{monogram}{wedding.secondary_short_name[:1].upper()}"

    programme_qs = WeddingEvent.objects.filter(wedding=wedding, is_active=True)
    if guest is not None:
        programme_qs = programme_qs.filter(pk__in=guest.allowed_events.values("pk"))

    qr_events = list(
        programme_qs.filter(requires_qr_code=True).order_by("date", "start_time", "display_order")
    ) if include_qr else []
    qr_data_uri = ""
    if include_qr:
        # O convite público terá um token por convidado. No estúdio usamos um
        # endereço de demonstração estável para que a página de QR também faça
        # parte da pré-visualização completa.
        qr_url = (
            f"{settings.SITE_BASE_URL}/check-in/{guest.invitation_token}/"
            if guest is not None
            else f"{settings.SITE_BASE_URL}/check-in/demo/{wedding.public_token}/"
        )
        # O QR precisa de contraste real, não apenas de combinar com a cor
        # decorativa do template. Ordenar papel/tinta pela luminosidade evita
        # dourado-claro sobre creme e mantém os templates escuros legíveis.
        qr_dark, qr_light = sorted(
            (template.paper, template.ink), key=_relative_luminance
        )
        qr_data_uri = segno.make(qr_url, error="h").svg_data_uri(
            scale=6,
            border=2,
            dark=qr_dark,
            light=qr_light,
        )

    programme = list(
        programme_qs
        .select_related("location", "location__wedding")
        .order_by("date", "start_time", "display_order")
    )
    # Compatibilidade durante a migração: itens antigos que ainda não foram
    # convertidos entram na mesma sequência, sem duplicar nomes.
    programme_names = {item.name.casefold() for item in programme}
    for legacy in (
        ScheduleItem.objects.filter(wedding=wedding, is_public=True)
        .select_related("location", "location__wedding")
        .order_by("date", "start_time", "display_order")
    ):
        if guest is None and legacy.title.casefold() not in programme_names:
            programme.append(legacy)
            programme_names.add(legacy.title.casefold())

    visible_first_moment = (
        programme[0] if guest is not None and programme
        else None if guest is not None
        else first_moment
    )

    guest_name = guest.full_name if guest is not None else guest_name
    texts = InvitationTexts(wedding, template.layout, guest_name=guest_name or "")

    return {
        "wedding": wedding,
        "template": template,
        # Todas as frases do convite, personalizáveis pelos anfitriões.
        # Use {% invtext "chave" %} (ver weddings/invitation_texts.py).
        "texts": texts,
        "css_variables": (
            template.css_variables(wedding.primary_color, wedding.secondary_color)
            if use_event_colours
            else template.css_variables()
        ),
        # Mantidos por compatibilidade; os layouts usam texts/invtext.
        "invitation_eyebrow": texts.plain("hero_eyebrow"),
        "invitation_greeting": (
            category.invitation_greeting if category else "convida-o para"
        ),
        "monogram": monogram,
        "guest": guest,
        "guest_name": guest_name,
        "seats": guest.party_size if guest is not None else seats,
        "seating_assignment": guest.seating_assignment if guest is not None else "",
        "first_moment": visible_first_moment,
        "countdown_target": _countdown_target(wedding, visible_first_moment),
        "schedule": programme,
        "locations": list(
            WeddingLocation.objects.filter(wedding=wedding)
            .select_related("wedding")
            .order_by("display_order", "name")
        ),
        "gallery": list(
            wedding.gallery_photos.filter(is_visible=True)
            .order_by("display_order", "created_at")
        ),
        # Momentos com local definido, para layouts que mostram «onde» à parte.
        "located_schedule": [item for item in programme if item.location_id],
        "dress_codes": _dress_codes(wedding, programme),
        "qr_events": qr_events,
        "qr_data_uri": qr_data_uri,
        "is_preview": is_preview,
        "show_branding": _show_branding(wedding),
    }


# Campos próprios das categorias que descrevem o traje dos convidados.
DRESS_CODE_KEYS = ("traje", "codigo_vestuario", "traje_tradicional")


def _dress_codes(wedding, programme) -> list[dict]:
    """
    Traje pedido aos convidados, sem repetições.

    Vem do campo «traje» de cada momento do programa e, quando existe, do
    campo próprio da categoria (ex.: «Traje» no noivado). `event` fica
    vazio quando o traje vale para toda a celebração.
    """
    codes: list[dict] = []
    seen: set[str] = set()
    extra = wedding.extra_data or {}
    for key in DRESS_CODE_KEYS:
        value = str(extra.get(key) or "").strip()
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            codes.append({"event": "", "value": value})
    for item in programme:
        value = (getattr(item, "dress_code", "") or "").strip()
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            codes.append({"event": item.programme_title, "value": value})
    return codes


def _show_branding(wedding) -> bool:
    """A marca da plataforma só desaparece nos pacotes que o permitem."""
    from subscriptions.services import limits

    return not limits(wedding).removes_branding
