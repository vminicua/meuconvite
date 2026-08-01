"""
Templates visuais de convite.

Antes o catálogo vivia em código. Passou para a base de dados porque a
equipa MeuConvite precisa de criar, ajustar e desactivar templates sem um
deploy — e porque cada template tem agora um *layout* real (a estrutura da
página do convite), além da paleta e das letras.

Um template = layout + paleta + tipografia. O layout é um ficheiro de
template Django em `templates/invitations/layouts/`; acrescentar um layout
novo é acrescentar um ficheiro e uma entrada em `Layout`.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


def _rgb(hex_colour: str) -> tuple[int, int, int] | None:
    value = (hex_colour or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(channel * 2 for channel in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(hex_colour: str) -> float:
    rgb = _rgb(hex_colour)
    if rgb is None:
        return 0
    channels = []
    for value in rgb:
        channel = value / 255
        channels.append(
            channel / 12.92
            if channel <= .04045
            else ((channel + .055) / 1.055) ** 2.4
        )
    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + .05) / (darker + .05)


def _mix(first: str, second: str, amount: float) -> str:
    first_rgb = _rgb(first)
    second_rgb = _rgb(second)
    if first_rgb is None or second_rgb is None:
        return second
    mixed = tuple(round(a + (b - a) * amount) for a, b in zip(first_rgb, second_rgb))
    return "#" + "".join(f"{channel:02X}" for channel in mixed)


def readable_colour(accent: str, background: str, ink: str, minimum: float = 4.5) -> str:
    """Preserva o tom da paleta, aproximando-o da tinta até ficar legível."""
    if _rgb(accent) is None or _rgb(background) is None or _rgb(ink) is None:
        return ink
    if _contrast(accent, background) >= minimum:
        return accent
    for step in range(1, 21):
        candidate = _mix(accent, ink, step / 20)
        if _contrast(candidate, background) >= minimum:
            return candidate
    return ink

from core.models import BaseModel
from core.storage import template_cover_upload_to, template_music_upload_to
from core.validators import validate_audio_upload, validate_hex_color, validate_image_upload


class InvitationLayout(models.TextChoices):
    """
    Estruturas de convite implementadas.

    Cada valor corresponde a `templates/invitations/layouts/<valor>.html`.
    """

    SEALED_LETTER = "carta_selada", _("Carta selada (abertura animada)")
    BOTANICAL = "envelope_botanico", _("Envelope botânico")
    CLASSIC_CARD = "cartao_classico", _("Cartão clássico")


class InvitationTemplateQuerySet(models.QuerySet):
    def active(self) -> "InvitationTemplateQuerySet":
        return self.filter(is_active=True)

    def featured(self) -> "InvitationTemplateQuerySet":
        return self.active().filter(is_featured=True)

    def for_category(self, category) -> "InvitationTemplateQuerySet":
        """
        Templates aplicáveis a um tipo de evento.

        Um template sem tipos associados serve para todos — é o caso
        comum, e evita ter de manter listas longas na administração.
        """
        queryset = self.active()
        if category is None:
            return queryset
        return queryset.filter(
            models.Q(categories__isnull=True) | models.Q(categories=category)
        ).distinct()


class InvitationTemplate(BaseModel):
    code = models.SlugField(_("código"), max_length=50, unique=True)
    name = models.CharField(_("nome"), max_length=80)
    description = models.CharField(_("descrição"), max_length=250, blank=True)

    layout = models.CharField(
        _("layout"),
        max_length=40,
        choices=InvitationLayout.choices,
        default=InvitationLayout.CLASSIC_CARD,
        help_text=_("A estrutura da página do convite."),
    )
    categories = models.ManyToManyField(
        "events.EventCategory",
        verbose_name=_("tipos de evento"),
        blank=True,
        related_name="invitation_templates",
        help_text=_("Deixe vazio para o template servir todos os tipos de evento."),
    )

    # --- Paleta ---
    primary = models.CharField(
        _("cor principal"), max_length=7, default="#C8A96A", validators=[validate_hex_color]
    )
    secondary = models.CharField(
        _("cor secundária"), max_length=7, default="#1F2933", validators=[validate_hex_color]
    )
    paper = models.CharField(
        _("cor do papel"), max_length=7, default="#FFFDF8", validators=[validate_hex_color]
    )
    ink = models.CharField(
        _("cor do texto"), max_length=7, default="#3A3226", validators=[validate_hex_color]
    )

    # --- Tipografia ---
    display_font = models.CharField(
        _("letra dos títulos"),
        max_length=120,
        default='"Great Vibes", cursive',
        help_text=_('Valor CSS, por exemplo: "Playfair Display", Georgia, serif'),
    )
    body_font = models.CharField(
        _("letra do texto"),
        max_length=120,
        default='"Cormorant Garamond", Georgia, serif',
    )
    google_fonts = models.CharField(
        _("famílias do Google Fonts"),
        max_length=250,
        blank=True,
        help_text=_(
            "Parâmetros family= a carregar, separados por «|». Exemplo: "
            "Great+Vibes|Cormorant+Garamond:wght@400;600"
        ),
    )

    # --- Comportamento do convite ---
    has_cover = models.BooleanField(
        _("abertura com capa"),
        default=True,
        help_text=_("Mostra um ecrã de abertura antes do convite."),
    )
    has_countdown = models.BooleanField(_("contagem regressiva"), default=True)
    supports_music = models.BooleanField(_("suporta música"), default=True)

    default_music = models.FileField(
        _("música do template"),
        upload_to=template_music_upload_to,
        blank=True,
        null=True,
        validators=[validate_audio_upload],
        help_text=_(
            "Opcional. Quando vazio, usa a música padrão da plataforma. "
            "MP3, M4A ou OGG até 8 MB."
        ),
    )

    cover_image = models.ImageField(
        _("cover do template"),
        upload_to=template_cover_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
        help_text=_(
            "Imagem vertical usada no catálogo. Recomendado: proporção 4:5, "
            "mínimo 1200 × 1500 px, JPG, PNG ou WEBP até 5 MB."
        ),
    )

    tags = models.CharField(
        _("etiquetas"),
        max_length=150,
        blank=True,
        help_text=_("Separadas por vírgulas: clássico, dourado, floral…"),
    )

    is_featured = models.BooleanField(
        _("destaque"),
        default=False,
        help_text=_("Aparece primeiro na escolha do template."),
    )
    is_active = models.BooleanField(_("activo"), default=True, db_index=True)
    display_order = models.PositiveIntegerField(_("ordem"), default=0)

    objects = InvitationTemplateQuerySet.as_manager()

    class Meta:
        verbose_name = _("template de convite")
        verbose_name_plural = _("templates de convite")
        ordering = ["-is_featured", "display_order", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # A capa faz parte do padrão visual da plataforma.
        self.has_cover = True
        return super().save(*args, **kwargs)

    @property
    def tag_list(self) -> list[str]:
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    @property
    def layout_template(self) -> str:
        """Caminho do ficheiro que desenha este convite."""
        return f"invitations/layouts/{self.layout}.html"

    @property
    def fonts_url(self) -> str:
        """URL do Google Fonts com as famílias deste template."""
        if not self.google_fonts:
            return ""
        families = "&".join(
            f"family={family.strip()}" for family in self.google_fonts.split("|") if family.strip()
        )
        return f"https://fonts.googleapis.com/css2?{families}&display=swap"

    @property
    def preview_style(self) -> str:
        """Variáveis usadas pelos cartões da galeria (templates-gallery.css)."""
        return (
            f"--tpl-primary: {self.primary};"
            f"--tpl-secondary: {self.secondary};"
            f"--tpl-paper: {self.paper};"
            f"--tpl-ink: {self.ink};"
            f"--tpl-display: {self.display_font};"
            f"--tpl-body: {self.body_font};"
        )

    def css_variables(self, primary: str = "", secondary: str = "") -> str:
        """
        Variáveis CSS do convite.

        As cores do evento, quando existem, ganham às do template: os
        noivos podem afinar a paleta sem sair do design escolhido.
        """
        primary = primary or self.primary
        secondary = secondary or self.secondary
        # Texto e acções usam contraste AAA. O limite anterior de 4.5 podia
        # ser tecnicamente válido e ainda assim parecer fraco em ecrãs móveis.
        primary_text = readable_colour(primary, self.paper, self.ink, minimum=7.0)
        secondary_text = readable_colour(secondary, self.paper, self.ink, minimum=7.0)
        on_primary = max(
            (self.paper, self.ink, "#FFFFFF", "#000000"),
            key=lambda colour: _contrast(colour, primary),
        )
        on_secondary = max(
            (self.paper, self.ink, "#FFFFFF", "#000000"),
            key=lambda colour: _contrast(colour, secondary),
        )
        seal_background = secondary
        seal_foreground = on_secondary
        if _contrast(seal_background, seal_foreground) < 7.0:
            seal_background = readable_colour(
                secondary, self.paper, self.ink, minimum=7.0
            )
            seal_foreground = self.paper
        return (
            f"--inv-primary: {primary};"
            f"--inv-secondary: {secondary};"
            f"--inv-primary-text: {primary_text};"
            f"--inv-secondary-text: {secondary_text};"
            f"--inv-on-primary: {on_primary};"
            f"--inv-on-secondary: {on_secondary};"
            f"--inv-seal-bg: {seal_background};"
            f"--inv-on-seal: {seal_foreground};"
            f"--inv-paper: {self.paper};"
            f"--inv-ink: {self.ink};"
            f"--inv-display: {self.display_font};"
            f"--inv-body: {self.body_font};"
        )
