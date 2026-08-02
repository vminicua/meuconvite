from __future__ import annotations

import string
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapForm, BootstrapModelForm
from core.schema import add_schema_fields, collect_schema_values
from core.utils import strip_accents
from core.validators import validate_image_upload
from templates_manager import registry

from .models import (
    DEFAULT_SMS_INVITATION_MESSAGE,
    DEFAULT_WHATSAPP_INVITATION_MESSAGE,
    SMS_MAX_LENGTH,
    SMS_TEMPLATE_MAX_LENGTH,
    Wedding,
    WeddingGalleryPhoto,
    WeddingMember,
    WeddingRole,
)

User = get_user_model()


class WeddingCreateForm(BootstrapModelForm):
    """
    Criação de um evento — deliberadamente curta.

    Só o essencial: quem/o quê e quando. Endereço, atributos próprios,
    programa, locais e convidados vêm depois.
    """

    class Meta:
        model = Wedding
        fields = [
            "primary_name",
            "secondary_name",
            "main_date",
        ]
        widgets = {
            "main_date": forms.DateInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, category=None, **kwargs) -> None:
        self.category = category
        super().__init__(*args, **kwargs)

        self.fields["main_date"].label = _("Data do evento")

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

    def wedding_data(self) -> dict:
        """Apenas os campos do modelo, sem os `extra__*` do esquema."""
        model_fields = {"primary_name", "secondary_name", "main_date"}
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

    sms_invitation_message = forms.CharField(
        label=_("Mensagem do convite por SMS"),
        required=False,
        max_length=SMS_TEMPLATE_MAX_LENGTH,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "maxlength": SMS_TEMPLATE_MAX_LENGTH,
            "data-sms-ascii": "",
        }),
        help_text=_("Sem acentos ou emojis. Use {nome}, {evento} e {link}."),
    )
    whatsapp_invitation_message = forms.CharField(
        label=_("Mensagem do convite por WhatsApp"),
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 7, "maxlength": 1000}),
        help_text=_("Pode usar {nome}, {evento} e {link}."),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        category = getattr(self.instance, "category", None)
        if not self.is_bound and self.instance and self.instance.pk:
            names = self.instance.display_names
            suggestions = {
                "cover_message": _("Uma celebração para recordar"),
                "invitation_message": _(
                    "Com muita alegria, convidamos para celebrar connosco este momento especial."
                ),
                "welcome_message": _("Sejam muito bem-vindos à celebração de %(names)s.") % {
                    "names": names,
                },
            }
            for field_name, value in suggestions.items():
                if field_name in self.fields and not getattr(self.instance, field_name, ""):
                    self.initial[field_name] = value
            if not self.instance.rsvp_deadline:
                days_until_event = (self.instance.main_date - timezone.localdate()).days
                if days_until_event > 14:
                    self.initial["rsvp_deadline"] = self.instance.main_date - timedelta(days=14)
                elif days_until_event > 2:
                    self.initial["rsvp_deadline"] = timezone.localdate() + timedelta(
                        days=max(days_until_event // 2, 1)
                    )
        if category is None:
            return

        self.fields["primary_name"].label = category.primary_label
        if category.uses_two_names:
            self.fields["secondary_name"].label = category.secondary_label
        else:
            del self.fields["secondary_name"]

        add_schema_fields(self, category.extra_fields, self.instance.extra_data or {})

        def bound(names):
            return [self[name] for name in names if name in self.fields]

        self.details_identity_fields = bound([
            "primary_name", "secondary_name", "main_date", "country",
        ])
        self.details_content_fields = bound([
            "cover_message", "invitation_message", "welcome_message", "story",
        ])
        self.details_planning_fields = bound([
            "rsvp_deadline", "show_countdown", "show_seat_before_event",
        ])
        self.details_extra_fields = [
            self[name] for name in self.fields
            if name.startswith("extra__") and name != "extra__lista_presentes"
        ]

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
            "main_date",
            "country",
            "cover_image",
            "invitation_music",
            "show_music",
            "cover_message",
            "invitation_message",
            "sms_invitation_message",
            "whatsapp_invitation_message",
            "welcome_message",
            "story",
            "rsvp_deadline",
            "show_countdown",
            "show_seat_before_event",
        ]
        widgets = {
            "main_date": forms.DateInput(),
            "rsvp_deadline": forms.DateInput(),
            "invitation_message": forms.Textarea(attrs={"rows": 3}),
            "sms_invitation_message": forms.Textarea(attrs={"rows": 3}),
            "whatsapp_invitation_message": forms.Textarea(attrs={"rows": 7}),
            "welcome_message": forms.Textarea(attrs={"rows": 3}),
            "story": forms.Textarea(attrs={"rows": 6}),
            "cover_image": forms.ClearableFileInput(attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "data-cover-input": "",
            }),
            "invitation_music": forms.ClearableFileInput(attrs={
                "accept": "audio/mpeg,audio/mp4,audio/ogg",
            }),
        }
        help_texts = {
            "rsvp_deadline": _("Depois desta data deixam de ser aceites confirmações."),
        }

    def clean_sms_invitation_message(self) -> str:
        value = (self.cleaned_data.get("sms_invitation_message") or "").strip() or DEFAULT_SMS_INVITATION_MESSAGE
        if not value.isascii() or any(ord(char) < 32 and char not in "\r\n\t" for char in value):
            raise forms.ValidationError(
                _("Use apenas letras sem acentos, numeros e pontuacao simples. Emojis nao sao permitidos.")
            )
        allowed = {"nome", "evento", "link"}
        try:
            fields = {
                field_name
                for _literal, field_name, _spec, _conversion in string.Formatter().parse(value)
                if field_name
            }
        except ValueError as exc:
            raise forms.ValidationError(_("A mensagem contém chavetas inválidas.")) from exc
        unknown = fields - allowed
        if unknown:
            raise forms.ValidationError(
                _("Placeholder desconhecido: %(fields)s. Use apenas {nome}, {evento} e {link}.")
                % {"fields": ", ".join(sorted(unknown))}
            )
        if "link" not in fields:
            raise forms.ValidationError(_("Inclua {link} para enviar a ligação individual."))
        preview_url = f"{settings.SITE_BASE_URL.rstrip('/')}/convite/ABCD/"
        preview_event = strip_accents(self.instance.display_names)[:40]
        preview = value.format(nome="Convidado", evento=preview_event, link=preview_url)
        if len(preview) > SMS_MAX_LENGTH:
            raise forms.ValidationError(
                _("A mensagem completa teria %(length)s caracteres. Reduza para no maximo %(limit)s.")
                % {"length": len(preview), "limit": SMS_MAX_LENGTH}
            )
        return value

    def clean_whatsapp_invitation_message(self) -> str:
        value = (
            self.cleaned_data.get("whatsapp_invitation_message") or ""
        ).strip() or DEFAULT_WHATSAPP_INVITATION_MESSAGE
        allowed = {"nome", "evento", "link"}
        try:
            fields = {
                field_name
                for _literal, field_name, _spec, _conversion in string.Formatter().parse(value)
                if field_name
            }
        except ValueError as exc:
            raise forms.ValidationError(_("A mensagem contém chavetas inválidas.")) from exc
        unknown = fields - allowed
        if unknown:
            raise forms.ValidationError(
                _("Placeholder desconhecido: %(fields)s. Use apenas {nome}, {evento} e {link}.")
                % {"fields": ", ".join(sorted(unknown))}
            )
        if "link" not in fields:
            raise forms.ValidationError(_("Inclua {link} para enviar a ligação individual."))
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("primary_name"):
            cleaned["primary_short_name"] = cleaned["primary_name"].split()[0][:60]
        if "secondary_name" in self.fields:
            secondary_name = cleaned.get("secondary_name") or ""
            cleaned["secondary_short_name"] = secondary_name.split()[0][:60] if secondary_name else ""
        deadline = cleaned.get("rsvp_deadline")
        main_date = cleaned.get("main_date")
        if deadline and main_date and deadline > main_date:
            self.add_error(
                "rsvp_deadline",
                _("O prazo de confirmação tem de ser anterior à data do evento."),
            )
        return cleaned


class WeddingDesignForm(BootstrapModelForm):
    """Escolha do template; as cores pertencem sempre ao template."""

    class Meta:
        model = Wedding
        fields = ["selected_template"]
        widgets = {
            # O template é escolhido na galeria de cartões da página, não
            # num select: o campo fica escondido e é preenchido por lá.
            "selected_template": forms.HiddenInput(),
        }

    def clean_selected_template(self) -> str:
        """O código tem de existir no catálogo — nunca confiar no que vem do formulário."""
        code = (self.cleaned_data.get("selected_template") or "").strip()
        if not registry.is_valid_code(code):
            raise forms.ValidationError(_("Escolha um dos templates disponíveis."))
        return code

    def save(self, commit: bool = True):
        wedding = super().save(commit=False)
        template = registry.get_template(self.cleaned_data["selected_template"])
        wedding.primary_color = template.primary
        wedding.secondary_color = template.secondary
        if commit:
            wedding.save(update_fields=[
                "selected_template", "primary_color", "secondary_color", "updated_at",
            ])
        return wedding


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        files = [item for item in files if item]
        if not files and self.required:
            raise forms.ValidationError(self.error_messages["required"], code="required")
        return [super().clean(item, initial) for item in files]


class GalleryUploadForm(forms.Form):
    photos = MultipleImageField(
        label=_("Escolher fotografias"),
        help_text=_("JPG, PNG ou WEBP até 5 MB cada. Pode seleccionar várias de uma vez."),
        widget=MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        validators=[validate_image_upload],
    )


class GalleryPhotoForm(BootstrapModelForm):
    class Meta:
        model = WeddingGalleryPhoto
        fields = ["caption", "is_visible"]
        widgets = {
            "caption": forms.Textarea(attrs={"rows": 2, "maxlength": 240}),
        }


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
