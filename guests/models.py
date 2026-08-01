from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, SoftDeleteModel
from core.utils import generate_secure_token


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
    notes = models.CharField(_("observações"), max_length=500, blank=True)
    invitation_token = models.CharField(
        _("token do convite"), max_length=64, unique=True,
        default=generate_secure_token, editable=False,
    )
    rsvp_status = models.CharField(
        _("confirmação"), max_length=20, choices=RSVPStatus.choices,
        default=RSVPStatus.PENDING, db_index=True,
    )
    responded_at = models.DateTimeField(_("respondido em"), null=True, blank=True)
    allowed_events = models.ManyToManyField(
        "events.WeddingEvent", verbose_name=_("programa autorizado"),
        blank=True, related_name="invited_guests",
        help_text=_("Sem selecção, o convidado recebe acesso a todo o programa público."),
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

    @property
    def has_programme_restrictions(self) -> bool:
        return self.allowed_events.exists()


class InvitationChannel(models.TextChoices):
    SMS = "sms", _("SMS")
    WHATSAPP = "whatsapp", _("WhatsApp")


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
    destination = models.CharField(max_length=40)
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
