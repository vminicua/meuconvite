from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, SoftDeleteModel
from core.utils import generate_invitation_code


class RSVPStatus(models.TextChoices):
    PENDING = "pending", _("Por responder")
    CONFIRMED = "confirmed", _("Confirmado")
    DECLINED = "declined", _("Não vai comparecer")


class Guest(BaseModel, SoftDeleteModel):
    wedding = models.ForeignKey(
        "weddings.Wedding", on_delete=models.CASCADE, related_name="guests"
    )
    full_name = models.CharField(_("nome completo"), max_length=160)
    phone = models.CharField(_("telefone"), max_length=30, blank=True)
    email = models.EmailField(_("email"), blank=True)
    party_size = models.PositiveSmallIntegerField(
        _("lugares"), default=1, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    seating_assignment = models.CharField(
        _("mesa ou cadeira"), max_length=100, blank=True,
        help_text=_("Ex.: Mesa dos Jacarandás, Mesa 8 ou Cadeira A12."),
    )
    notes = models.CharField(_("observações"), max_length=500, blank=True)
    invitation_token = models.CharField(
        _("codigo do convite"), max_length=4, unique=True,
        default=generate_invitation_code, editable=False,
    )
    rsvp_status = models.CharField(
        _("confirmação"), max_length=20, choices=RSVPStatus.choices,
        default=RSVPStatus.PENDING, db_index=True,
    )
    responded_at = models.DateTimeField(_("respondido em"), null=True, blank=True)
    plan_access = models.BooleanField(
        _("incluído no plano"),
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text=_(
            "Sem valor usa a ordem automática; sim inclui e não exclui explicitamente."
        ),
    )
    allowed_events = models.ManyToManyField(
        "events.WeddingEvent", verbose_name=_("programa autorizado"),
        blank=True, related_name="invited_guests",
        help_text=_("Seleccione os momentos que este convidado pode consultar."),
    )

    class Meta:
        verbose_name = _("convidado")
        verbose_name_plural = _("convidados")
        ordering = ["full_name"]
        indexes = [
            models.Index(
                fields=["wedding", "is_active", "full_name"],
                name="guests_gues_wedding_e386a8_idx",
            )
        ]

    def __str__(self) -> str:
        return self.full_name

    def save(self, *args, **kwargs):
        if self._state.adding:
            while not self.invitation_token or Guest.objects.filter(
                invitation_token=self.invitation_token
            ).exists():
                self.invitation_token = generate_invitation_code()
        return super().save(*args, **kwargs)

    @property
    def has_programme_restrictions(self) -> bool:
        active_total = self.wedding.events.filter(is_active=True).count()
        return self.allowed_events.count() < active_total


class Gift(BaseModel, SoftDeleteModel):
    """Presente sugerido pelos anfitriões para um evento."""

    wedding = models.ForeignKey(
        "weddings.Wedding", on_delete=models.CASCADE, related_name="gifts"
    )
    name = models.CharField(_("presente"), max_length=160)
    description = models.CharField(_("descrição"), max_length=500, blank=True)
    allow_multiple = models.BooleanField(
        _("permitir vários convidados"),
        default=False,
        help_text=_("Por omissão, o presente fica reservado ao primeiro convidado."),
    )
    display_order = models.PositiveIntegerField(_("ordem"), default=0)

    class Meta:
        verbose_name = _("presente")
        verbose_name_plural = _("presentes")
        ordering = ["display_order", "created_at", "name"]
        indexes = [
            models.Index(fields=["wedding", "is_active"], name="gift_wedding_active_idx")
        ]

    def __str__(self) -> str:
        return self.name


class GiftSelection(BaseModel):
    """Associa um convidado ao presente que decidiu levar."""

    gift = models.ForeignKey(Gift, on_delete=models.CASCADE, related_name="selections")
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="gift_selections")

    class Meta:
        verbose_name = _("selecção de presente")
        verbose_name_plural = _("selecções de presentes")
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["gift", "guest"], name="unique_gift_guest")
        ]

    def __str__(self) -> str:
        return f"{self.guest} — {self.gift}"


class InvitationChannel(models.TextChoices):
    SMS = "sms", _("SMS")
    WHATSAPP = "whatsapp", _("WhatsApp")
    EMAIL = "email", _("Email")


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", _("A preparar")
    QUEUED = "queued", _("Na fila")
    SENT = "sent", _("Enviado")
    DELIVERED = "delivered", _("Entregue")
    READ = "read", _("Lido")
    FAILED = "failed", _("Falhou")
    UNDELIVERED = "undelivered", _("Não entregue")
    CANCELED = "canceled", _("Cancelado")


class InvitationDelivery(BaseModel):
    """Tentativa auditável de envio de um convite pelo Twilio."""

    wedding = models.ForeignKey(
        "weddings.Wedding", on_delete=models.CASCADE, related_name="invitation_deliveries"
    )
    guest = models.ForeignKey(
        Guest, on_delete=models.CASCADE, related_name="invitation_deliveries"
    )
    channel = models.CharField(max_length=20, choices=InvitationChannel.choices)
    status = models.CharField(
        max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING, db_index=True
    )
    destination = models.CharField(max_length=254)
    message_body = models.TextField(max_length=1600)
    provider = models.CharField(max_length=30, default="twilio")
    provider_sid = models.CharField(max_length=64, blank=True, db_index=True)
    error_code = models.CharField(max_length=30, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitation_deliveries_sent",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    counts_toward_limit = models.BooleanField(
        _("conta para o limite"),
        default=True,
        help_text=_("Desmarcado para notificações operacionais e reposições de saldo."),
    )

    class Meta:
        verbose_name = _("envio de convite")
        verbose_name_plural = _("envios de convites")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["guest", "-created_at"], name="guest_delivery_date_idx"),
            models.Index(fields=["wedding", "status"], name="wedding_delivery_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.guest} — {self.get_channel_display()} ({self.get_status_display()})"


class EventReminderDelivery(BaseModel):
    """Registo idempotente de um lembrete de evento enviado por email."""

    wedding = models.ForeignKey(
        "weddings.Wedding", on_delete=models.CASCADE, related_name="reminder_deliveries"
    )
    guest = models.ForeignKey(
        Guest, on_delete=models.CASCADE, related_name="reminder_deliveries"
    )
    event_date = models.DateField(_("data do evento"))
    days_before = models.PositiveSmallIntegerField(_("dias de antecedência"))
    destination = models.EmailField(_("destino"))
    subject = models.CharField(_("assunto"), max_length=255)
    status = models.CharField(
        max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING,
        db_index=True,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = _("lembrete de evento")
        verbose_name_plural = _("lembretes de eventos")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["guest", "event_date", "days_before"],
                name="unique_guest_event_reminder",
            )
        ]
        indexes = [
            models.Index(fields=["wedding", "event_date"], name="reminder_wedding_date_idx"),
            models.Index(fields=["status", "created_at"], name="reminder_status_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.guest} — {self.days_before} dia(s) antes ({self.get_status_display()})"
