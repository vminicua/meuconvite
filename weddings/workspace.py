"""
Event workspace helpers: grouped navigation and the "next steps" guide.

The workspace used to show a flat row of eleven tabs. It is now organised
in four areas (convite, informações, convidados, definições), each with a
few sub-sections. Everything here is derived from the URL being visited,
the capability flags and existing data; nothing is stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.urls import reverse

CORPORATE_CATEGORY_CODE = "evento-corporativo"


@dataclass
class NavItem:
    code: str
    label: str
    short_label: str
    icon: str
    url: str
    active: bool = False
    locked: bool = False
    upgrade_feature: str = ""
    upgrade_url: str = ""


@dataclass
class NavGroup:
    code: str
    label: str
    hint: str
    icon: str
    items: list[NavItem] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return any(item.active for item in self.items)

    @property
    def entry(self) -> NavItem:
        """Where the big button of the area leads: the first usable sub-section."""
        return next((item for item in self.items if not item.locked), self.items[0])

    @property
    def has_subnav(self) -> bool:
        return len(self.items) > 1


def _is_active(code: str, namespace: str, url_name: str) -> bool:
    if code == "preview":
        return namespace == "weddings" and url_name == "preview"
    if code == "design":
        return namespace == "weddings" and url_name == "design"
    if code == "details":
        return namespace == "weddings" and url_name in {"detail", "settings", "setup", "category"}
    if code == "story":
        return namespace == "weddings" and url_name == "story"
    if code == "gallery":
        return namespace == "weddings" and url_name.startswith("gallery")
    if code == "programme":
        return namespace == "events"
    if code == "guests":
        return namespace == "guests" and "gift" not in url_name
    if code == "gifts":
        return namespace == "guests" and "gift" in url_name
    if code == "team":
        return namespace == "weddings" and url_name.startswith("team")
    if code == "subscription":
        return namespace == "subscriptions"
    return False


def build_workspace_nav(wedding, capabilities: dict | None, resolver_match=None) -> list[NavGroup]:
    """
    The four workspace areas visible to this user, with their sub-sections.

    Visibility follows exactly the rules of the former flat tab bar; on a
    locked (additional, unpaid) event the owner still sees every area, but
    each link opens the upgrade modal instead of navigating.
    """
    caps = capabilities or {}
    locked = bool(caps.get("event_locked"))
    owner_locked = locked and bool(caps.get("is_owner"))
    namespace = getattr(resolver_match, "namespace", "") or ""
    url_name = getattr(resolver_match, "url_name", "") or ""
    pk = wedding.pk
    upgrade_url = reverse("subscriptions:detail", args=[pk])

    def item(code, label, short_label, icon, url_name_, *, feature=None, with_url=True,
             lockable=True, args=None):
        is_locked = locked and lockable
        return NavItem(
            code=code,
            label=label,
            short_label=short_label,
            icon=icon,
            url=reverse(url_name_, args=args or [pk]),
            active=_is_active(code, namespace, url_name),
            locked=is_locked,
            upgrade_feature=(feature or label) if is_locked else "",
            upgrade_url=upgrade_url if is_locked and with_url else "",
        )

    can_design = bool(caps.get("can_manage_design")) or owner_locked
    can_guests = bool(caps.get("can_manage_guests")) or owner_locked

    invitation = NavGroup("invitation", "O convite", "Ver e personalizar", "bi-envelope-heart")
    invitation.items.append(item("preview", "Ver convite", "Ver convite", "bi-eye",
                                 "weddings:preview", feature="Convite"))
    if can_design:
        invitation.items.append(item("design", "Aspecto", "Aspecto", "bi-palette",
                                     "weddings:design", feature="Aspecto do convite"))

    info = NavGroup("info", "Informações", "Data, programa e fotos", "bi-card-text")
    info.items.append(item("details", "Detalhes do evento", "Detalhes", "bi-card-checklist",
                           "weddings:detail"))
    info.items.append(item("programme", "Programa", "Programa", "bi-calendar3",
                           "events:organisation"))
    category = getattr(wedding, "category", None)
    if getattr(category, "code", "") != CORPORATE_CATEGORY_CODE:
        info.items.append(item("story", "A nossa história", "História", "bi-book",
                               "weddings:story"))
    if can_design:
        info.items.append(item("gallery", "Galeria", "Galeria", "bi-images", "weddings:gallery"))

    guests = NavGroup("guests", "Convidados", "Lista, envio e respostas", "bi-people")
    if can_guests:
        guests.items.append(item("guests", "Lista de convidados", "Convidados", "bi-person-lines-fill",
                                 "guests:list", feature="Convidados"))
        guests.items.append(item("gifts", "Presentes", "Presentes", "bi-gift", "guests:gifts"))

    settings = NavGroup("settings", "Definições", "Pacote e equipa", "bi-gear")
    if caps.get("can_manage_billing"):
        settings.items.append(item("subscription", "Subscrição", "Subscrição", "bi-gem",
                                   "subscriptions:detail", lockable=False))
    if caps.get("is_owner") or caps.get("manage_members"):
        settings.items.append(item("team", "Equipa", "Equipa", "bi-person-gear", "weddings:team",
                                   feature="Este evento", with_url=False))

    return [group for group in (invitation, info, guests, settings) if group.items]


# ---------------------------------------------------------------------------
# Next steps ("o que falta fazer")
# ---------------------------------------------------------------------------

@dataclass
class NextStep:
    code: str
    label: str
    hint: str
    done: bool
    icon: str
    action_label: str
    url: str = ""
    optional: bool = False

    @property
    def actionable(self) -> bool:
        return bool(self.url)


@dataclass
class NextSteps:
    steps: list[NextStep]
    guest_count: int
    confirmed_count: int

    @property
    def done_count(self) -> int:
        return sum(1 for step in self.steps if step.done)

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def percent(self) -> int:
        return int(self.done_count / self.total * 100) if self.total else 100

    @property
    def complete(self) -> bool:
        """Every essential step is done (optional ones may still be pending)."""
        return all(step.done for step in self.steps if not step.optional)

    @property
    def remaining(self) -> int:
        """Essential steps still to do."""
        return sum(1 for step in self.steps if not step.done and not step.optional)

    @property
    def next_step(self) -> NextStep | None:
        """
        The single most useful thing to do now: the first pending step the
        user can open, preferring essential steps over optional ones.
        """
        pending = [step for step in self.steps if not step.done and step.actionable]
        return next((step for step in pending if not step.optional), None) or (
            pending[0] if pending else None
        )


def build_next_steps(wedding, capabilities: dict | None) -> NextSteps:
    """Progress of the event, computed from existing data only (no stored flags)."""
    from events.models import WeddingEvent
    from guests.models import DeliveryStatus, Guest, InvitationDelivery, RSVPStatus

    caps = capabilities or {}
    pk = wedding.pk
    can_events = bool(caps.get("can_manage_events"))
    can_design = bool(caps.get("can_manage_design"))
    can_guests = bool(caps.get("can_manage_guests"))

    events = WeddingEvent.objects.filter(wedding=wedding, is_active=True)
    guests = Guest.objects.filter(wedding=wedding, is_active=True)
    guest_count = guests.count()
    confirmed_count = guests.filter(rsvp_status=RSVPStatus.CONFIRMED).count()
    delivered = InvitationDelivery.objects.filter(
        wedding=wedding,
        status__in=[DeliveryStatus.QUEUED, DeliveryStatus.SENT,
                    DeliveryStatus.DELIVERED, DeliveryStatus.READ],
    ).exists()
    answered = guests.exclude(rsvp_status=RSVPStatus.PENDING).exists()
    has_photos = bool(wedding.cover_image) or wedding.gallery_photos.filter(is_visible=True).exists()

    def url(name, allowed=True):
        return reverse(name, args=[pk]) if allowed else ""

    steps = [
        NextStep(
            code="details",
            label="Data e endereço",
            hint="Quando e onde vai ser o evento.",
            done=bool(wedding.main_date and (wedding.city or "").strip()),
            icon="bi-calendar-event",
            action_label="Completar detalhes",
            url=url("weddings:detail"),
        ),
        NextStep(
            code="programme",
            label="Programa com local",
            hint="Pelo menos um momento com hora e local.",
            done=events.filter(location__isnull=False).exists(),
            icon="bi-geo-alt",
            action_label="Preparar o programa",
            url=url("events:organisation", can_events),
        ),
        NextStep(
            code="photos",
            label="Fotografias",
            hint="Uma fotografia de capa ou na galeria.",
            done=has_photos,
            icon="bi-images",
            action_label="Adicionar fotografias",
            optional=True,
            url=url("weddings:gallery", can_design) or url("weddings:detail", can_events),
        ),
        NextStep(
            code="guests",
            label="Convidados",
            hint=(f"{guest_count} na lista." if guest_count else "Adicione ou importe a lista."),
            done=guest_count > 0,
            icon="bi-people",
            action_label="Adicionar convidados",
            url=url("guests:list", can_guests),
        ),
        NextStep(
            code="sent",
            label="Convites enviados",
            hint=(f"{confirmed_count} confirmado{'s' if confirmed_count != 1 else ''} até agora."
                  if delivered or answered else "Por SMS, email ou WhatsApp."),
            done=delivered or answered,
            icon="bi-send",
            action_label="Enviar convites",
            url=url("guests:list", can_guests),
        ),
    ]
    return NextSteps(steps=steps, guest_count=guest_count, confirmed_count=confirmed_count)
