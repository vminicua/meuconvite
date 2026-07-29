from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from core.storage import (
    wedding_cover_upload_to,
    wedding_music_upload_to,
)
from core.utils import generate_secure_token, unique_slugify
from core.validators import (
    validate_audio_upload,
    validate_hex_color,
    validate_image_upload,
    validate_wedding_slug,
)


class WeddingStatus(models.TextChoices):
    DRAFT = "draft", _("Rascunho")
    PUBLISHED = "published", _("Publicado")
    ARCHIVED = "archived", _("Arquivado")
    BLOCKED = "blocked", _("Bloqueado")


class SeatVisibility(models.TextChoices):
    """When the guest is allowed to see their table."""

    ALWAYS = "always", _("Mostrar sempre no convite")
    ON_EVENT_DAY = "on_event_day", _("Mostrar apenas no dia do evento")
    AFTER_CHECKIN = "after_checkin", _("Mostrar depois do check-in")
    NEVER = "never", _("Não mostrar no convite")


class WeddingRole(models.TextChoices):
    OWNER = "owner", _("Proprietário")
    SPOUSE = "spouse", _("Noivo(a)")
    WEDDING_PLANNER = "wedding_planner", _("Wedding planner")
    COMMITTEE = "committee", _("Comissão")
    RECEPTIONIST = "receptionist", _("Recepção")
    VIEWER = "viewer", _("Consulta")


class WeddingQuerySet(models.QuerySet):
    def for_user(self, user) -> "WeddingQuerySet":
        """
        Every wedding the user may access.

        This is the single entry point used by the views: data isolation
        between weddings depends on it, so it is covered by dedicated
        tests in `weddings/tests/test_isolation.py`.
        """
        if not user or not user.is_authenticated:
            return self.none()
        return self.filter(
            models.Q(owner=user)
            | models.Q(members__user=user, members__is_active=True)
        ).distinct()

    def visible(self) -> "WeddingQuerySet":
        return self.exclude(status__in=[WeddingStatus.ARCHIVED, WeddingStatus.BLOCKED])

    def published(self) -> "WeddingQuerySet":
        return self.filter(status=WeddingStatus.PUBLISHED)


class Wedding(BaseModel):
    """
    A wedding: the tenant boundary of the whole platform.

    Every other domain model points at a wedding (directly or through a
    parent) and every query is scoped by it.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("proprietário"),
        on_delete=models.PROTECT,
        related_name="owned_weddings",
    )

    # --- Couple ---
    bride_full_name = models.CharField(_("nome completo da noiva"), max_length=150)
    groom_full_name = models.CharField(_("nome completo do noivo"), max_length=150)
    bride_short_name = models.CharField(_("nome curto da noiva"), max_length=60)
    groom_short_name = models.CharField(_("nome curto do noivo"), max_length=60)

    # --- Public identifiers ---
    slug = models.SlugField(
        _("endereço público"),
        max_length=70,
        unique=True,
        validators=[validate_wedding_slug],
        help_text=_("Usado em meuconvite.co.mz/o-seu-endereco/"),
    )
    public_token = models.CharField(
        _("token público"),
        max_length=64,
        unique=True,
        default=generate_secure_token,
        editable=False,
        help_text=_("Token seguro usado em ligações que não devem expor o endereço."),
    )

    # --- When and where ---
    main_date = models.DateField(_("data principal"), db_index=True)
    timezone = models.CharField(_("fuso horário"), max_length=50, default="Africa/Maputo")
    country = models.CharField(_("país"), max_length=80, default="Moçambique")
    city = models.CharField(_("cidade"), max_length=100)

    # --- Content ---
    cover_image = models.ImageField(
        _("fotografia de capa"),
        upload_to=wedding_cover_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )
    welcome_message = models.TextField(_("mensagem de boas-vindas"), blank=True, max_length=1000)
    story = models.TextField(_("a nossa história"), blank=True, max_length=5000)
    hashtag = models.CharField(_("hashtag"), max_length=60, blank=True)

    # --- Design ---
    primary_color = models.CharField(
        _("cor principal"), max_length=7, default="#C8A96A", validators=[validate_hex_color]
    )
    secondary_color = models.CharField(
        _("cor secundária"), max_length=7, default="#1F2933", validators=[validate_hex_color]
    )
    selected_template = models.CharField(
        _("template"),
        max_length=50,
        default="classic",
        help_text=_("Identificador do template visual escolhido."),
    )
    invitation_music = models.FileField(
        _("música do convite"),
        upload_to=wedding_music_upload_to,
        blank=True,
        null=True,
        validators=[validate_audio_upload],
    )

    # --- Behaviour ---
    status = models.CharField(
        _("estado"),
        max_length=20,
        choices=WeddingStatus.choices,
        default=WeddingStatus.DRAFT,
        db_index=True,
    )
    show_music = models.BooleanField(_("reproduzir música"), default=False)
    show_countdown = models.BooleanField(_("mostrar contagem regressiva"), default=True)
    show_seat_before_event = models.CharField(
        _("visibilidade da mesa"),
        max_length=20,
        choices=SeatVisibility.choices,
        default=SeatVisibility.ON_EVENT_DAY,
    )
    rsvp_deadline = models.DateField(_("prazo de confirmação"), null=True, blank=True)

    published_at = models.DateTimeField(_("publicado em"), null=True, blank=True)
    blocked_reason = models.CharField(_("motivo do bloqueio"), max_length=200, blank=True)

    objects = WeddingQuerySet.as_manager()

    class Meta:
        verbose_name = _("casamento")
        verbose_name_plural = _("casamentos")
        ordering = ["-main_date", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name="wedding_owner_status_idx"),
            models.Index(fields=["main_date"], name="wedding_main_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(bride_full_name=""),
                name="wedding_bride_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(groom_full_name=""),
                name="wedding_groom_name_not_empty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.bride_short_name} & {self.groom_short_name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.bride_short_name}-e-{self.groom_short_name}"
            self.slug = unique_slugify(self, base)
        if not self.public_token:
            self.public_token = generate_secure_token()
        return super().save(*args, **kwargs)

    # --- Derived information -----------------------------------------
    @property
    def couple_names(self) -> str:
        return f"{self.bride_short_name} & {self.groom_short_name}"

    @property
    def couple_full_names(self) -> str:
        return f"{self.bride_full_name} e {self.groom_full_name}"

    @property
    def is_published(self) -> bool:
        return self.status == WeddingStatus.PUBLISHED

    @property
    def is_editable(self) -> bool:
        return self.status in {WeddingStatus.DRAFT, WeddingStatus.PUBLISHED}

    @property
    def days_until(self) -> int | None:
        if not self.main_date:
            return None
        return (self.main_date - timezone.localdate()).days

    @property
    def has_happened(self) -> bool:
        return bool(self.main_date and self.main_date < timezone.localdate())

    @property
    def rsvp_is_open(self) -> bool:
        today: date = timezone.localdate()
        if self.rsvp_deadline and today > self.rsvp_deadline:
            return False
        return self.status == WeddingStatus.PUBLISHED

    def get_absolute_url(self) -> str:
        return reverse("weddings:detail", args=[self.pk])

    def get_public_url(self) -> str:
        return f"{settings.SITE_BASE_URL}/{self.slug}/"


class WeddingMember(BaseModel):
    """
    A person who helps to manage a wedding.

    Permissions are stored as explicit booleans instead of being derived
    from the role alone, so the couple can fine-tune what each helper can
    do. `apply_role_defaults()` fills them from the role as a starting
    point.
    """

    ROLE_DEFAULTS: dict[str, dict[str, bool]] = {
        WeddingRole.OWNER: {
            "can_manage_guests": True,
            "can_manage_events": True,
            "can_manage_seating": True,
            "can_check_in": True,
            "can_view_reports": True,
            "can_manage_design": True,
            "can_manage_billing": True,
        },
        WeddingRole.SPOUSE: {
            "can_manage_guests": True,
            "can_manage_events": True,
            "can_manage_seating": True,
            "can_check_in": True,
            "can_view_reports": True,
            "can_manage_design": True,
            "can_manage_billing": False,
        },
        WeddingRole.WEDDING_PLANNER: {
            "can_manage_guests": True,
            "can_manage_events": True,
            "can_manage_seating": True,
            "can_check_in": True,
            "can_view_reports": True,
            "can_manage_design": True,
            "can_manage_billing": False,
        },
        WeddingRole.COMMITTEE: {
            "can_manage_guests": True,
            "can_manage_events": False,
            "can_manage_seating": True,
            "can_check_in": True,
            "can_view_reports": True,
            "can_manage_design": False,
            "can_manage_billing": False,
        },
        WeddingRole.RECEPTIONIST: {
            "can_manage_guests": False,
            "can_manage_events": False,
            "can_manage_seating": False,
            "can_check_in": True,
            "can_view_reports": False,
            "can_manage_design": False,
            "can_manage_billing": False,
        },
        WeddingRole.VIEWER: {
            "can_manage_guests": False,
            "can_manage_events": False,
            "can_manage_seating": False,
            "can_check_in": False,
            "can_view_reports": True,
            "can_manage_design": False,
            "can_manage_billing": False,
        },
    }

    wedding = models.ForeignKey(
        Wedding, verbose_name=_("casamento"), on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("utilizador"),
        on_delete=models.CASCADE,
        related_name="wedding_memberships",
    )
    role = models.CharField(
        _("função"), max_length=20, choices=WeddingRole.choices, default=WeddingRole.COMMITTEE
    )

    can_manage_guests = models.BooleanField(_("gerir convidados"), default=False)
    can_manage_events = models.BooleanField(_("gerir eventos"), default=False)
    can_manage_seating = models.BooleanField(_("gerir mesas"), default=False)
    can_check_in = models.BooleanField(_("fazer check-in"), default=False)
    can_view_reports = models.BooleanField(_("ver relatórios"), default=True)
    can_manage_design = models.BooleanField(_("gerir design"), default=False)
    can_manage_billing = models.BooleanField(_("gerir subscrição"), default=False)

    invited_at = models.DateTimeField(_("convidado em"), default=timezone.now)
    accepted_at = models.DateTimeField(_("aceite em"), null=True, blank=True)
    is_active = models.BooleanField(_("activo"), default=True, db_index=True)
    notes = models.CharField(_("notas"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("membro da equipa")
        verbose_name_plural = _("membros da equipa")
        ordering = ["role", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["wedding", "user"], name="unique_member_per_wedding"
            )
        ]
        indexes = [
            models.Index(fields=["wedding", "is_active"], name="member_wedding_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.get_role_display()}"

    def apply_role_defaults(self) -> None:
        for field, value in self.ROLE_DEFAULTS.get(self.role, {}).items():
            setattr(self, field, value)

    @property
    def has_accepted(self) -> bool:
        return self.accepted_at is not None
