from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, SoftDeleteModel


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
