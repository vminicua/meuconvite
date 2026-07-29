from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from core.storage import user_avatar_upload_to
from core.validators import validate_image_upload, validate_phone

from .managers import UserManager


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """
    Platform user.

    The email address is the login identifier; there is no username.
    Roles inside a wedding are not stored here — they live in
    `weddings.WeddingMember`, so one account can take part in several
    weddings with different permissions.
    """

    email = models.EmailField(_("email"), unique=True, db_index=True)
    first_name = models.CharField(_("nome próprio"), max_length=80, blank=True)
    last_name = models.CharField(_("apelido"), max_length=80, blank=True)
    phone = models.CharField(
        _("telefone"), max_length=20, blank=True, validators=[validate_phone]
    )
    avatar = models.ImageField(
        _("fotografia"),
        upload_to=user_avatar_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )

    is_email_verified = models.BooleanField(_("email verificado"), default=False)
    is_active = models.BooleanField(_("activo"), default=True)
    is_staff = models.BooleanField(
        _("equipa MeuConvite"),
        default=False,
        help_text=_("Permite o acesso à administração da plataforma."),
    )

    preferred_language = models.CharField(
        _("idioma"), max_length=5, default="pt", choices=[("pt", "Português"), ("en", "English")]
    )
    last_login_ip = models.GenericIPAddressField(_("último IP"), blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _("utilizador")
        verbose_name_plural = _("utilizadores")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    def clean(self) -> None:
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        return super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name or self.email.split("@")[0]

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.get_short_name()

    @property
    def initials(self) -> str:
        parts = [part for part in (self.first_name, self.last_name) if part]
        if not parts:
            return self.email[:2].upper()
        return "".join(part[0].upper() for part in parts[:2])
