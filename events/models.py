from __future__ import annotations

from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from core.utils import unique_slugify
from core.validators import validate_phone
from weddings.models import Wedding


class EventType(models.TextChoices):
    """
    Common wedding events in Mozambique.

    The list is a convenience, not a limitation: `CUSTOM` lets each family
    create any other event with its own name and description, and no
    cultural meaning is hard-coded anywhere in the platform.
    """

    RELIGIOUS = "religious", _("Cerimónia religiosa")
    CIVIL = "civil", _("Cerimónia civil")
    RECEPTION = "reception", _("Recepção")
    WELCOME_DRINK = "welcome_drink", _("Copo de água / Welcome drink")
    PHOTO_SESSION = "photo_session", _("Sessão fotográfica")
    CAKE_CUTTING = "cake_cutting", _("Corte do bolo")
    LOBOLO = "lobolo", _("Lobolo")
    XIGUIANE = "xiguiane", _("Xiguiane")
    TRADITIONAL = "traditional", _("Cerimónia tradicional")
    CUSTOM = "custom", _("Outro evento")


class WeddingLocation(BaseModel):
    """A place where one or more events happen."""

    wedding = models.ForeignKey(
        Wedding, verbose_name=_("casamento"), on_delete=models.CASCADE, related_name="locations"
    )
    name = models.CharField(_("nome"), max_length=150)
    address = models.CharField(_("endereço"), max_length=250, blank=True)
    description = models.TextField(_("descrição"), max_length=1000, blank=True)
    map_url = models.URLField(_("ligação do mapa"), max_length=500, blank=True)
    latitude = models.DecimalField(
        _("latitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        _("longitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    contact_phone = models.CharField(
        _("telefone de contacto"), max_length=20, blank=True, validators=[validate_phone]
    )
    parking_information = models.TextField(_("estacionamento"), max_length=500, blank=True)
    transport_information = models.TextField(_("transporte"), max_length=500, blank=True)
    display_order = models.PositiveIntegerField(_("ordem"), default=0)

    class Meta:
        verbose_name = _("local")
        verbose_name_plural = _("locais")
        ordering = ["display_order", "name"]
        indexes = [models.Index(fields=["wedding", "display_order"], name="location_order_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["wedding", "name"], name="unique_location_name_per_wedding"
            )
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def directions_url(self) -> str:
        """Map link, built from coordinates when no explicit URL was given."""
        if self.map_url:
            return self.map_url
        if self.has_coordinates:
            return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
        if self.address:
            from urllib.parse import quote

            return f"https://www.google.com/maps/search/?api=1&query={quote(self.address)}"
        return ""


class WeddingEventQuerySet(models.QuerySet):
    def active(self) -> "WeddingEventQuerySet":
        return self.filter(is_active=True)

    def for_wedding(self, wedding) -> "WeddingEventQuerySet":
        return self.filter(wedding=wedding)

    def requiring_rsvp(self) -> "WeddingEventQuerySet":
        return self.filter(requires_rsvp=True, is_active=True)


class WeddingEvent(BaseModel):
    """
    One event of the celebration.

    Each event carries its own date, place, guest list, confirmations,
    tables and QR code rules, which is what makes lobolo, xiguiane and the
    religious ceremony independent from each other.
    """

    wedding = models.ForeignKey(
        Wedding, verbose_name=_("casamento"), on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(
        _("tipo"), max_length=30, choices=EventType.choices, default=EventType.CUSTOM
    )
    name = models.CharField(_("nome"), max_length=150)
    slug = models.SlugField(_("identificador"), max_length=70, blank=True)
    description = models.TextField(_("descrição"), max_length=2000, blank=True)

    date = models.DateField(_("data"), null=True, blank=True, db_index=True)
    start_time = models.TimeField(_("hora de início"), null=True, blank=True)
    end_time = models.TimeField(_("hora de fim"), null=True, blank=True)

    location = models.ForeignKey(
        WeddingLocation,
        verbose_name=_("local"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    map_url = models.URLField(_("ligação do mapa"), max_length=500, blank=True)
    host_family = models.CharField(
        _("família anfitriã"),
        max_length=150,
        blank=True,
        help_text=_("Por exemplo, a família que recebe o lobolo ou o xiguiane."),
    )
    dress_code = models.CharField(_("traje"), max_length=150, blank=True)
    instructions = models.TextField(_("instruções aos convidados"), max_length=2000, blank=True)

    requires_rsvp = models.BooleanField(_("exige confirmação"), default=True)
    requires_qr_code = models.BooleanField(_("exige QR Code à entrada"), default=False)
    show_to_all_guests = models.BooleanField(
        _("visível para todos os convidados"),
        default=True,
        help_text=_("Se desactivado, só os convidados autorizados vêem este evento."),
    )
    is_active = models.BooleanField(_("activo"), default=True, db_index=True)
    display_order = models.PositiveIntegerField(_("ordem"), default=0)

    objects = WeddingEventQuerySet.as_manager()

    class Meta:
        verbose_name = _("evento")
        verbose_name_plural = _("eventos")
        ordering = ["date", "start_time", "display_order"]
        indexes = [
            models.Index(fields=["wedding", "is_active"], name="event_wedding_active_idx"),
            models.Index(fields=["wedding", "date", "start_time"], name="event_wedding_when_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["wedding", "name"], name="unique_event_name_per_wedding"
            ),
            models.CheckConstraint(
                condition=models.Q(end_time__isnull=True)
                | models.Q(start_time__isnull=True)
                | models.Q(end_time__gte=models.F("start_time")),
                name="event_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        if not self.date and self.wedding_id:
            # Events default to the main wedding date until changed.
            self.date = self.wedding.main_date
        return super().save(*args, **kwargs)

    @property
    def starts_at(self) -> datetime | None:
        """Timezone aware start, used for countdowns and calendar files."""
        if not self.date or not self.start_time:
            return None
        naive = datetime.combine(self.date, self.start_time)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def is_past(self) -> bool:
        if not self.date:
            return False
        return self.date < timezone.localdate()

    @property
    def is_today(self) -> bool:
        return bool(self.date and self.date == timezone.localdate())

    @property
    def effective_map_url(self) -> str:
        return self.map_url or (self.location.directions_url if self.location else "")

    @property
    def time_range_display(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.start_time:%H:%M} — {self.end_time:%H:%M}"
        if self.start_time:
            return f"{self.start_time:%H:%M}"
        return ""


class ScheduleItem(BaseModel):
    """
    One line of the day's programme.

    Kept separate from `WeddingEvent` because the programme is often more
    granular than the events guests are invited to.
    """

    wedding = models.ForeignKey(
        Wedding,
        verbose_name=_("casamento"),
        on_delete=models.CASCADE,
        related_name="schedule_items",
    )
    event = models.ForeignKey(
        WeddingEvent,
        verbose_name=_("evento"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_items",
    )
    title = models.CharField(_("título"), max_length=150)
    description = models.CharField(_("descrição"), max_length=300, blank=True)
    date = models.DateField(_("data"), null=True, blank=True)
    start_time = models.TimeField(_("hora"), null=True, blank=True)
    end_time = models.TimeField(_("hora de fim"), null=True, blank=True)
    location = models.ForeignKey(
        WeddingLocation,
        verbose_name=_("local"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_items",
    )
    icon = models.CharField(
        _("ícone"),
        max_length=40,
        blank=True,
        help_text=_("Nome do ícone Bootstrap, por exemplo bi-camera."),
    )
    display_order = models.PositiveIntegerField(_("ordem"), default=0, db_index=True)
    is_public = models.BooleanField(
        _("visível na página pública"),
        default=True,
        help_text=_("Se desactivado, aparece apenas nos convites individuais."),
    )

    class Meta:
        verbose_name = _("item do programa")
        verbose_name_plural = _("programa")
        ordering = ["display_order", "start_time"]
        indexes = [
            models.Index(fields=["wedding", "display_order"], name="schedule_order_idx"),
        ]

    def __str__(self) -> str:
        if self.start_time:
            return f"{self.start_time:%Hh%M} — {self.title}"
        return self.title

    @property
    def time_display(self) -> str:
        return f"{self.start_time:%Hh%M}" if self.start_time else ""
