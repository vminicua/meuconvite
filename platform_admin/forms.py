from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapForm, BootstrapModelForm
from core.schema import FIELD_TYPES, MAX_FIELDS, slugify_key, validate_schema
from events.models import EventCategory
from subscriptions.models import Plan, Voucher
from templates_manager.models import InvitationTemplate
from .models import PlatformConfiguration


class PlatformConfigurationForm(BootstrapModelForm):
    """Integrações da plataforma; segredos vazios mantêm o valor actual."""

    twilio_account_sid = forms.CharField(label="Account SID", required=False)
    twilio_api_key_sid = forms.CharField(label="API Key SID", required=False)
    twilio_api_key_secret = forms.CharField(
        label="API Key Secret", required=False, widget=forms.PasswordInput(render_value=True)
    )
    twilio_auth_token = forms.CharField(
        label="Auth Token (webhooks)", required=False, widget=forms.PasswordInput(render_value=True)
    )
    payzeno_api_key = forms.CharField(
        label="API Key Payzeno",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=_("Chave privada pk_live_… criada em API & Webhooks na Payzeno."),
    )

    SECRET_NAMES = (
        "twilio_account_sid",
        "twilio_api_key_sid",
        "twilio_api_key_secret",
        "twilio_auth_token",
        "payzeno_api_key",
    )

    class Meta:
        model = PlatformConfiguration
        fields = [
            "twilio_sms_from",
            "twilio_status_callback_url",
            "payzeno_enabled",
            "payzeno_base_url",
            "mpesa_number",
            "mpesa_account_name",
            "whatsapp_number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.SECRET_NAMES:
            if self.instance and self.instance.has_secret(name):
                self.fields[name].widget.attrs["placeholder"] = "Configurado — deixe vazio para manter"
        self.fields["twilio_status_callback_url"].help_text = _(
            "Use HTTPS. Normalmente: https://seu-dominio/convites/twilio/estado/."
        )
        self.fields["twilio_sms_from"].help_text = _(
            "Número Twilio em E.164 (por exemplo +123456789) ou Messaging Service compatível."
        )
        self.fields["payzeno_enabled"].help_text = _(
            "Active apenas depois de o KYC e a aplicação Payzeno estarem aprovados."
        )
        self.fields["payzeno_base_url"].help_text = _(
            "Mantenha https://api.payzeno.io, salvo indicação oficial da Payzeno."
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        for name in self.SECRET_NAMES:
            value = self.cleaned_data.get(name, "")
            if value:
                instance.set_secret(name, value)
        if commit:
            instance.save()
        return instance


class PlanForm(BootstrapModelForm):
    """Criação e edição de um pacote comercial."""

    max_sms = forms.IntegerField(
        label=_("SMS incluídos"),
        min_value=0,
        required=False,
        initial=0,
        help_text=_("0 desactiva o envio por SMS neste pacote."),
    )

    def clean_max_sms(self) -> int:
        return self.cleaned_data.get("max_sms") or 0

    class Meta:
        model = Plan
        fields = [
            "name",
            "code",
            "description",
            "max_guests",
            "max_events",
            "max_sms",
            "templates_limit",
            "price_mzn",
            "duration_days",
            "allows_qr_checkin",
            "allows_seating",
            "allows_team",
            "allows_exports",
            "removes_branding",
            "is_active",
            "is_default",
            "display_order",
        ]
        help_texts = {
            "code": _("Identificador interno. Não mude depois de haver subscrições."),
            "templates_limit": _("0 = todos os templates."),
            "duration_days": _("0 = sem validade (usado no plano gratuito)."),
            "is_default": _("O pacote atribuído automaticamente a cada evento novo."),
        }

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get("price_mzn") or 0
        if cleaned.get("is_default") and price > 0:
            self.add_error(
                "is_default",
                _("O pacote inicial tem de ser gratuito — é o que todos recebem ao criar um evento."),
            )
        return cleaned

    def save(self, commit: bool = True) -> Plan:
        plan = super().save(commit=commit)
        # Só pode haver um pacote inicial.
        if commit and plan.is_default:
            Plan.objects.exclude(pk=plan.pk).filter(is_default=True).update(is_default=False)
        return plan


class VoucherForm(BootstrapModelForm):
    """Criação dos códigos promocionais usados pelos noivos."""

    class Meta:
        model = Voucher
        fields = [
            "name", "code", "description", "max_guests", "sms_enabled", "max_sms",
            "valid_from", "valid_until", "max_redemptions", "is_active",
        ]
        widgets = {
            "valid_from": forms.DateInput(),
            "valid_until": forms.DateInput(),
        }
        help_texts = {
            "code": _("Código entregue aos noivos; será guardado em maiúsculas."),
            "max_redemptions": _("0 permite utilizações ilimitadas."),
            "max_sms": _("Só é usado quando «activar envio por SMS» estiver marcado."),
        }

    def clean_code(self) -> str:
        return (self.cleaned_data.get("code") or "").strip().upper()


class EventCategoryForm(BootstrapModelForm):
    """
    Criação e edição de um tipo de evento.

    Os campos próprios (`field_schema`) são geridos por uma lista com
    botões, na página; aqui trata-se do resto. Momentos e programa
    predefinidos continuam em JSON, com validação amigável.
    """

    class Meta:
        model = EventCategory
        fields = [
            "name",
            "code",
            "description",
            "icon",
            "uses_two_names",
            "primary_label",
            "secondary_label",
            "names_separator",
            "invitation_greeting",
            "default_moments",
            "is_active",
            "display_order",
        ]
        widgets = {
            "default_moments": forms.Textarea(attrs={"rows": 6, "class": "form-control font-monospace"}),
        }
        labels = {"default_moments": _("Programa predefinido")}
        help_texts = {
            "icon": _("Nome de um ícone Bootstrap, por exemplo bi-cake2."),
            "names_separator": _("Usado no título: «Ivone & Dário»."),
            "default_moments": _("Lista JSON com name, start_time e opções de RSVP/QR Code."),
        }

    def _clean_json_list(self, field: str) -> list:
        value = self.cleaned_data.get(field)
        if isinstance(value, str):
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(
                    _("JSON inválido: %(erro)s") % {"erro": exc.msg}
                ) from exc
        if not isinstance(value, list):
            raise forms.ValidationError(_("Tem de ser uma lista."))
        return value

    def clean_default_moments(self) -> list:
        moments = self._clean_json_list("default_moments")
        for position, item in enumerate(moments, start=1):
            if not isinstance(item, dict) or not item.get("name"):
                raise forms.ValidationError(
                    _("O momento %(n)s precisa de «name».") % {"n": position}
                )
        return moments

class CategoryFieldForm(BootstrapForm):
    """Acrescenta um campo próprio a um tipo de evento."""

    label = forms.CharField(label=_("Nome do campo"), max_length=60)
    type = forms.ChoiceField(
        label=_("Tipo"), choices=[(key, value) for key, value in FIELD_TYPES.items()], initial="text"
    )
    choices = forms.CharField(
        label=_("Opções"),
        required=False,
        help_text=_("Só para listas de opções: separe por vírgulas."),
    )
    required = forms.BooleanField(label=_("Obrigatório"), required=False)

    def __init__(self, *args, category: EventCategory | None = None, **kwargs) -> None:
        self.category = category
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        label = (cleaned.get("label") or "").strip()
        if not label or self.category is None:
            return cleaned

        key = slugify_key(label)
        existing = {field["key"] for field in self.category.extra_fields}
        if key in existing:
            raise forms.ValidationError(_("Já existe um campo com este nome."))
        if len(existing) >= MAX_FIELDS:
            raise forms.ValidationError(
                _("Máximo de %(max)s campos por tipo de evento.") % {"max": MAX_FIELDS}
            )
        if cleaned.get("type") == "choice" and not (cleaned.get("choices") or "").strip():
            self.add_error("choices", _("Indique as opções, separadas por vírgulas."))

        cleaned["key"] = key
        return cleaned

    def definition(self) -> dict:
        raw = (self.cleaned_data.get("choices") or "").split(",")
        definition = {
            "key": self.cleaned_data["key"],
            "label": self.cleaned_data["label"].strip(),
            "type": self.cleaned_data["type"],
            "required": bool(self.cleaned_data.get("required")),
            "choices": [choice.strip() for choice in raw if choice.strip()],
        }
        validate_schema([definition])
        return definition


TEMPLATE_FONT_CHOICES = [
    ('"Playfair Display", Georgia, serif', _("Playfair Display — elegante")),
    ('"Great Vibes", cursive', _("Great Vibes — manuscrita")),
    ('"Cormorant Garamond", Georgia, serif', _("Cormorant Garamond — clássica")),
    ('"Montserrat", "Segoe UI", sans-serif', _("Montserrat — moderna")),
]


class InvitationTemplateForm(BootstrapModelForm):
    """Criação e edição de um template de convite."""

    class Meta:
        model = InvitationTemplate
        fields = [
            "name",
            "code",
            "description",
            "layout",
            "categories",
            "primary",
            "secondary",
            "paper",
            "ink",
            "display_font",
            "body_font",
            "google_fonts",
            "tags",
            "has_countdown",
            "supports_music",
            "default_music",
            "cover_image",
            "is_featured",
            "is_active",
            "display_order",
        ]
        widgets = {
            "primary": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "secondary": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "paper": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "ink": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "display_font": forms.Select(choices=TEMPLATE_FONT_CHOICES),
            "body_font": forms.Select(choices=TEMPLATE_FONT_CHOICES),
            "google_fonts": forms.HiddenInput(),
            "categories": forms.SelectMultiple(attrs={"class": "form-select js-select2", "size": 6}),
            "default_music": forms.ClearableFileInput(
                attrs={"accept": ".mp3,.m4a,.ogg,audio/mpeg,audio/mp4,audio/ogg"}
            ),
        }
        labels = {
            "display_font": _("Fonte dos títulos"),
            "body_font": _("Fonte do texto"),
            "cover_image": _("Capa do template"),
            "default_music": _("Música deste template"),
            "display_order": _("Posição no catálogo"),
        }
        help_texts = {
            "categories": _("Deixe vazio para disponibilizar este template em todos os tipos de evento."),
            "code": "",
            "layout": _("Escolha o estilo base do convite."),
            "display_font": "",
            "body_font": "",
            "google_fonts": "",
            "default_music": _(
                "Opcional. Se não escolher uma faixa, será usada a música padrão de casamento."
            ),
        }

    def clean(self):
        cleaned = super().clean()
        font_parameters = {
            '"Playfair Display", Georgia, serif': "Playfair+Display:wght@500;600",
            '"Great Vibes", cursive': "Great+Vibes",
            '"Cormorant Garamond", Georgia, serif': "Cormorant+Garamond:wght@400;600",
            '"Montserrat", "Segoe UI", sans-serif': "Montserrat:wght@400;600",
        }
        selected = []
        for field_name in ("display_font", "body_font"):
            parameter = font_parameters.get(cleaned.get(field_name))
            if parameter and parameter not in selected:
                selected.append(parameter)
        cleaned["google_fonts"] = "|".join(selected)
        return cleaned


class BlockEventForm(BootstrapForm):
    """Bloqueio de um evento pela equipa da plataforma."""

    reason = forms.CharField(
        label=_("Motivo"),
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": _("Fica registado na auditoria")}),
    )

    def clean_reason(self) -> str:
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 5:
            raise ValidationError(_("Escreva um motivo claro — será consultado mais tarde."))
        return reason
