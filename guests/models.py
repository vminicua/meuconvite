from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
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
