from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapForm, BootstrapModelForm
from core.schema import FIELD_TYPES, MAX_FIELDS, slugify_key, validate_schema
from events.models import EventCategory
from subscriptions.models import Plan
from templates_manager.models import InvitationTemplate


class PlanForm(BootstrapModelForm):
    """Criação e edição de um pacote comercial."""

    class Meta:
        model = Plan
        fields = [
            "name",
            "code",
            "description",
            "max_guests",
            "max_events",
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
            "default_schedule",
            "is_active",
            "display_order",
        ]
        widgets = {
            "default_moments": forms.Textarea(attrs={"rows": 6, "class": "form-control font-monospace"}),
            "default_schedule": forms.Textarea(attrs={"rows": 6, "class": "form-control font-monospace"}),
        }
        help_texts = {
            "icon": _("Nome de um ícone Bootstrap, por exemplo bi-cake2."),
            "names_separator": _("Usado no título: «Ivone & Dário»."),
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

    def clean_default_schedule(self) -> list:
        items = self._clean_json_list("default_schedule")
        for position, item in enumerate(items, start=1):
            if not isinstance(item, dict) or not item.get("title"):
                raise forms.ValidationError(
                    _("O item %(n)s do programa precisa de «title».") % {"n": position}
                )
        return items


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
            "has_cover",
            "has_countdown",
            "supports_music",
            "preview_image",
            "is_featured",
            "is_active",
            "display_order",
        ]
        widgets = {
            "primary": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "secondary": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "paper": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "ink": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "categories": forms.SelectMultiple(attrs={"class": "form-select js-select2", "size": 6}),
        }
        help_texts = {
            "categories": _("Vazio = serve todos os tipos de evento."),
            "code": _("Identificador usado nos eventos. Evite mudá-lo depois de estar em uso."),
        }


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
