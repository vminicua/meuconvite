from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapForm, BootstrapModelForm
from core.schema import add_schema_fields, collect_schema_values
from core.utils import unique_slugify
from templates_manager import registry

from .models import Wedding, WeddingMember, WeddingRole

User = get_user_model()


class WeddingCreateForm(BootstrapModelForm):
    """
    Criação de um evento — deliberadamente curta.

    Só o essencial: quem/o quê, quando e onde. O tipo de evento (recebido
    já escolhido) decide as etiquetas dos nomes, se são um ou dois, e quais
    os campos próprios a pedir. Programa, locais e convidados vêm depois.
    """

    class Meta:
        model = Wedding
        fields = [
            "primary_name",
            "secondary_name",
            "main_date",
            "city",
        ]
        widgets = {
            "main_date": forms.DateInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, category=None, **kwargs) -> None:
        self.category = category
        super().__init__(*args, **kwargs)

        self.fields["main_date"].label = _("Data do evento")
        self.fields["city"].label = _("Cidade")

        if category is None:
            self.fields["secondary_name"].required = False
            return

        self.fields["primary_name"].label = category.primary_label
        if category.uses_two_names:
            self.fields["secondary_name"].label = category.secondary_label
            self.fields["secondary_name"].required = True
        else:
            # Um único protagonista: o segundo nome não é pedido.
            del self.fields["secondary_name"]

        # Campos próprios do tipo de evento, definidos pela equipa MeuConvite.
        add_schema_fields(self, category.extra_fields)

    def clean_main_date(self):
        main_date = self.cleaned_data["main_date"]
        if main_date < timezone.localdate():
            raise forms.ValidationError(_("A data do evento não pode estar no passado."))
        return main_date

    def clean(self):
        cleaned = super().clean()
        # Os nomes curtos usados no convite são derivados dos nomes
        # completos: é uma decisão que ninguém precisa de tomar no início.
        if cleaned.get("primary_name"):
            cleaned["primary_short_name"] = cleaned["primary_name"].split()[0][:60]
        if cleaned.get("secondary_name"):
            cleaned["secondary_short_name"] = cleaned["secondary_name"].split()[0][:60]
        return cleaned

    def extra_data(self) -> dict:
        """Valores dos campos próprios, prontos a guardar em `Wedding.extra_data`."""
        if self.category is None:
            return {}
        return collect_schema_values(self, self.category.extra_fields)

    def wedding_data(self) -> dict:
        """Apenas os campos do modelo, sem os `extra__*` do esquema."""
        model_fields = {"primary_name", "secondary_name", "main_date", "city"}
        data = {
            key: value
            for key, value in self.cleaned_data.items()
            if key in model_fields or key in {"primary_short_name", "secondary_short_name"}
        }
        data.setdefault("secondary_name", "")
        data.setdefault("secondary_short_name", "")
        return data


class WeddingSettingsForm(BootstrapModelForm):
    """Definições gerais de um evento já criado."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        category = getattr(self.instance, "category", None)
        if category is None:
            return

        self.fields["primary_name"].label = category.primary_label
        self.fields["primary_short_name"].label = _("%(label)s (nome curto)") % {
            "label": category.primary_label
        }
        if category.uses_two_names:
            self.fields["secondary_name"].label = category.secondary_label
            self.fields["secondary_short_name"].label = _("%(label)s (nome curto)") % {
                "label": category.secondary_label
            }
        else:
            del self.fields["secondary_name"]
            del self.fields["secondary_short_name"]

        add_schema_fields(self, category.extra_fields, self.instance.extra_data or {})

    def extra_data(self) -> dict:
        category = getattr(self.instance, "category", None)
        if category is None:
            return self.instance.extra_data or {}
        return collect_schema_values(self, category.extra_fields)

    class Meta:
        model = Wedding
        fields = [
            "primary_name",
            "secondary_name",
            "primary_short_name",
            "secondary_short_name",
            "main_date",
            "city",
            "country",
            "slug",
            "hashtag",
            "welcome_message",
            "story",
            "rsvp_deadline",
            "show_countdown",
            "show_seat_before_event",
        ]
        widgets = {
            "main_date": forms.DateInput(),
            "rsvp_deadline": forms.DateInput(),
            "welcome_message": forms.Textarea(attrs={"rows": 3}),
            "story": forms.Textarea(attrs={"rows": 6}),
        }
        help_texts = {
            "slug": _("Endereço público: meuconvite.co.mz/<endereço>/"),
            "rsvp_deadline": _("Depois desta data deixam de ser aceites confirmações."),
        }

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get("slug") or "").strip().lower()
        if not slug:
            return unique_slugify(
                self.instance,
                f"{self.instance.primary_short_name}-e-{self.instance.secondary_short_name}",
            )
        return slug

    def clean(self):
        cleaned = super().clean()
        deadline = cleaned.get("rsvp_deadline")
        main_date = cleaned.get("main_date")
        if deadline and main_date and deadline > main_date:
            self.add_error(
                "rsvp_deadline",
                _("O prazo de confirmação tem de ser anterior à data do evento."),
            )
        return cleaned


class WeddingDesignForm(BootstrapModelForm):
    """Template, colours, cover photo and music."""

    class Meta:
        model = Wedding
        fields = [
            "selected_template",
            "primary_color",
            "secondary_color",
            "cover_image",
            "invitation_music",
            "show_music",
        ]
        widgets = {
            # O template é escolhido na galeria de cartões da página, não
            # num select: o campo fica escondido e é preenchido por lá.
            "selected_template": forms.HiddenInput(),
            "primary_color": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "secondary_color": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "cover_image": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "invitation_music": forms.ClearableFileInput(attrs={"accept": "audio/mpeg,audio/mp4,audio/ogg"}),
        }

    def clean_selected_template(self) -> str:
        """O código tem de existir no catálogo — nunca confiar no que vem do formulário."""
        code = (self.cleaned_data.get("selected_template") or "").strip()
        if not registry.is_valid_code(code):
            raise forms.ValidationError(_("Escolha um dos templates disponíveis."))
        return code


class MemberInviteForm(BootstrapForm):
    """Adds someone to the wedding team by email address."""

    email = forms.EmailField(
        label=_("Email do membro"),
        help_text=_("A pessoa tem de ter (ou criar) uma conta MeuConvite com este email."),
    )
    role = forms.ChoiceField(
        label=_("Função"),
        choices=[(value, label) for value, label in WeddingRole.choices if value != WeddingRole.OWNER],
        initial=WeddingRole.COMMITTEE,
    )
    notes = forms.CharField(label=_("Notas"), max_length=200, required=False)

    def __init__(self, *args, wedding: Wedding | None = None, **kwargs) -> None:
        self.wedding = wedding
        super().__init__(*args, **kwargs)

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        try:
            self.user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise forms.ValidationError(
                _(
                    "Não existe nenhuma conta com este email. Peça à pessoa para se "
                    "registar em %(site)s e tente novamente."
                )
                % {"site": "meuconvite.co.mz"}
            ) from None

        if self.wedding and self.user.pk == self.wedding.owner_id:
            raise forms.ValidationError(_("O proprietário já faz parte da equipa."))
        return email


class MemberPermissionsForm(BootstrapModelForm):
    """Fine-grained permissions for an existing member."""

    class Meta:
        model = WeddingMember
        fields = [
            "role",
            "can_manage_guests",
            "can_manage_events",
            "can_manage_seating",
            "can_check_in",
            "can_view_reports",
            "can_manage_design",
            "can_manage_billing",
            "notes",
        ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            (value, label) for value, label in WeddingRole.choices if value != WeddingRole.OWNER
        ]
