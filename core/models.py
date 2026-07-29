"""Abstract model building blocks shared by every application."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Adds automatic creation/update timestamps."""

    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("actualizado em"), auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Primary key as UUID so public identifiers are never guessable."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """UUID primary key + timestamps: the default base for domain models."""

    class Meta:
        abstract = True


class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class SoftDeleteModel(models.Model):
    """Marks records as inactive instead of deleting them."""

    is_active = models.BooleanField(_("activo"), default=True, db_index=True)

    objects = ActiveQuerySet.as_manager()

    class Meta:
        abstract = True
