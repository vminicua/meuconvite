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
    validate_phone,
    validate_wedding_slug,
)

DEFAULT_SMS_INVITATION_MESSAGE = (
    "*O Nosso Casamento*\n"
    "Ola {nome}! Sera uma alegria celebrar este dia contigo.\n"
    "Convite:{link}\n\n"
    "{evento}"
)

SMS_TEMPLATE_MAX_LENGTH = 100
SMS_MAX_LENGTH = 160


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

    # --- Tipo de evento ---
    # O tipo determina como se chamam os protagonistas, que campos extra
    # são pedidos e que momentos/programa são sugeridos ao criar o evento.
    category = models.ForeignKey(
        "events.EventCategory",
        verbose_name=_("tipo de evento"),
        on_delete=models.PROTECT,
        related_name="weddings",
        null=True,
        blank=True,
    )

    # --- Protagonistas ---
    # Num casamento são os noivos; num aniversário é o aniversariante; num
    # lobolo são as duas famílias. As etiquetas vêm da categoria.
    primary_name = models.CharField(_("nome completo (1)"), max_length=150)
    secondary_name = models.CharField(_("nome completo (2)"), max_length=150, blank=True)
    primary_short_name = models.CharField(_("nome curto (1)"), max_length=60)
    secondary_short_name = models.CharField(_("nome curto (2)"), max_length=60, blank=True)

    # Valores dos campos próprios do tipo de evento (EventCategory.field_schema).
    extra_data = models.JSONField(_("dados específicos"), default=dict, blank=True)

    # Campos que o próprio utilizador acrescentou ao programa deste evento,
    # além dos que a plataforma já traz (hora, título, local, ícone).
    schedule_field_schema = models.JSONField(
        _("campos adicionais do programa"), default=list, blank=True
    )

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
    city = models.CharField(_("endereço"), max_length=250, blank=True, default="")

    # --- Content ---
    cover_image = models.ImageField(
        _("fotografia de capa"),
        upload_to=wedding_cover_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )
    cover_message = models.CharField(
        _("mensagem da capa"),
        max_length=200,
        blank=True,
        help_text=_("Frase curta apresentada antes de abrir o convite."),
    )
    invitation_message = models.TextField(
        _("mensagem principal do convite"),
        max_length=1000,
        blank=True,
        help_text=_("Mensagem apresentada ao convidado depois de abrir o convite."),
    )
    sms_invitation_message = models.CharField(
        _("mensagem do convite por SMS"),
        max_length=SMS_TEMPLATE_MAX_LENGTH,
        default=DEFAULT_SMS_INVITATION_MESSAGE,
        help_text=_("Sem acentos ou emojis. Pode usar {nome}, {evento} e {link}."),
    )
    notification_phone_primary = models.CharField(
        _("telefone para notificações"), max_length=20, blank=True,
        validators=[validate_phone],
        help_text=_("Recebe SMS quando um convidado responde ou escolhe um presente."),
    )
    notification_phone_secondary = models.CharField(
        _("segundo telefone"), max_length=20, blank=True,
        validators=[validate_phone],
        help_text=_("Opcional. Pode ser o telefone do outro noivo ou anfitrião."),
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
        default="carta-selada",
        help_text=_(
            "Código do template escolhido (templates_manager.InvitationTemplate)."
        ),
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
        verbose_name = _("evento")
        verbose_name_plural = _("eventos")
        ordering = ["-main_date", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name="wedding_owner_status_idx"),
            models.Index(fields=["main_date"], name="wedding_main_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(primary_name=""),
                name="event_primary_name_not_empty",
            ),
        ]

    def __str__(self) -> str:
        return self.display_names

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.display_names.replace("&", "e"))
        if not self.public_token:
            self.public_token = generate_secure_token()
        return super().save(*args, **kwargs)

    # --- Derived information -----------------------------------------
    @property
    def names_separator(self) -> str:
        return self.category.names_separator if self.category_id else "&"

    @property
    def display_names(self) -> str:
        """Título curto do evento: «Ivone & Dário» ou «Dona Amélia»."""
        if self.secondary_short_name:
            return f"{self.primary_short_name} {self.names_separator} {self.secondary_short_name}"
        return self.primary_short_name

    @property
    def full_names(self) -> str:
        if self.secondary_name:
            return f"{self.primary_name} e {self.secondary_name}"
        return self.primary_name

    @property
    def category_name(self) -> str:
        return self.category.name if self.category_id else _("Evento")

    @property
    def category_icon(self) -> str:
        return self.category.icon if self.category_id else "bi-calendar-heart"

    def extra_values(self) -> list[dict]:
        """Campos próprios do tipo de evento, com etiqueta e valor preenchido."""
        if not self.category_id:
            return []
        values = self.extra_data or {}
        return [
            {**definition, "value": values.get(definition["key"], "")}
            for definition in self.category.extra_fields
        ]

    @property
    def schedule_fields(self) -> list[dict]:
        """Definições dos campos que o utilizador acrescentou ao programa."""
        from core.schema import normalise_schema

        return normalise_schema(self.schedule_field_schema)

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
        Wedding, verbose_name=_("evento"), on_delete=models.CASCADE, related_name="members"
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
