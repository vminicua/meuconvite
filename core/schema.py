"""
Campos definidos por dados (JSON) em vez de colunas.

Dois sítios da plataforma precisam de campos que não são conhecidos à
partida:

* `events.EventCategory.field_schema` — os campos próprios de cada tipo de
  evento, configurados pela equipa MeuConvite;
* `weddings.Wedding.schedule_field_schema` — os campos que o próprio
  utilizador acrescenta ao programa do seu evento.

Ambos usam o mesmo formato e passam por estas funções, para que a
validação e a construção dos formulários sejam iguais nos dois casos.

Formato de cada campo:

    {"key": "traje", "label": "Traje", "type": "choice",
     "required": false, "help_text": "", "choices": ["A", "B"]}
"""

from __future__ import annotations

import re

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

FIELD_TYPES: dict[str, str] = {
    "text": _("Texto curto"),
    "textarea": _("Texto longo"),
    "number": _("Número"),
    "date": _("Data"),
    "time": _("Hora"),
    "url": _("Ligação"),
    "choice": _("Lista de opções"),
    "list": _("Lista de linhas"),
    "boolean": _("Sim / Não"),
}

MAX_FIELDS = 20

DRESS_CODE_CHOICES = (
    "Traje de gala",
    "Traje formal",
    "Traje semi-formal",
    "Traje tradicional",
    "Traje casual",
    "Traje temático",
)


class RepeatedTextWidget(forms.Widget):
    """Uma lista editável de linhas, enviada como vários valores com o mesmo nome."""

    template_name = "widgets/repeated_text.html"

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        return mark_safe(render_to_string(self.template_name, context))

    def format_value(self, value):
        if not value:
            return [""]
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value] or [""]
        return [str(value)]

    def value_from_datadict(self, data, files, name):
        return [value.strip() for value in data.getlist(name) if value.strip()]


class RepeatedTextField(forms.Field):
    widget = RepeatedTextWidget

    def to_python(self, value):
        if not value:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [str(item).strip()[:500] for item in value if str(item).strip()]


def slugify_key(label: str) -> str:
    """Transforma uma etiqueta escrita à mão numa chave estável."""
    import unicodedata

    normalised = unicodedata.normalize("NFKD", label or "")
    ascii_only = "".join(char for char in normalised if not unicodedata.combining(char))
    key = re.sub(r"[^a-z0-9]+", "_", ascii_only.lower()).strip("_")[:40]
    if not key or not key[0].isalpha():
        key = f"campo_{key}".strip("_")[:40]
    return key


def validate_schema(raw) -> None:
    """Valida um esquema vindo do JSON, com mensagens úteis por posição."""
    if not isinstance(raw, list):
        raise ValidationError(_("Tem de ser uma lista de campos."))
    if len(raw) > MAX_FIELDS:
        raise ValidationError(
            _("Demasiados campos (máximo %(max)s).") % {"max": MAX_FIELDS}
        )

    seen: set[str] = set()
    for position, definition in enumerate(raw, start=1):
        if not isinstance(definition, dict):
            raise ValidationError(
                _("O campo %(n)s não é um objecto.") % {"n": position}
            )
        key = definition.get("key")
        if not key or not KEY_RE.match(str(key)):
            raise ValidationError(
                _(
                    "O campo %(n)s precisa de uma «key» em minúsculas, sem espaços "
                    "nem acentos (por exemplo: traje_convidados)."
                )
                % {"n": position}
            )
        if key in seen:
            raise ValidationError(
                _("A chave «%(key)s» está repetida.") % {"key": key}
            )
        seen.add(key)

        if not definition.get("label"):
            raise ValidationError(
                _("O campo %(n)s precisa de «label».") % {"n": position}
            )

        field_type = definition.get("type", "text")
        if field_type not in FIELD_TYPES:
            raise ValidationError(
                _("Tipo «%(type)s» não suportado. Use: %(allowed)s.")
                % {"type": field_type, "allowed": ", ".join(FIELD_TYPES)}
            )
        if field_type == "choice" and not definition.get("choices"):
            raise ValidationError(
                _("O campo «%(key)s» é uma lista de opções e precisa de «choices».")
                % {"key": key}
            )


def normalise_schema(raw) -> list[dict]:
    """Devolve o esquema com valores por omissão preenchidos, ignorando lixo."""
    fields: list[dict] = []
    for definition in raw or []:
        if not isinstance(definition, dict):
            continue
        key = definition.get("key")
        if not key:
            continue
        field_type = definition.get("type", "text")
        if field_type not in FIELD_TYPES:
            field_type = "text"
        fields.append(
            {
                "key": str(key),
                "label": str(definition.get("label") or key),
                "type": field_type,
                "required": bool(definition.get("required", False)),
                "help_text": str(definition.get("help_text", "")),
                "placeholder": str(definition.get("placeholder", "")),
                "choices": [str(choice) for choice in definition.get("choices", [])],
            }
        )
    return fields


def build_form_field(definition: dict) -> forms.Field:
    """Constrói o campo de formulário correspondente a uma definição."""
    common = {
        "label": definition["label"],
        "required": definition["required"],
        "help_text": definition.get("help_text", ""),
    }
    field_type = definition["type"]

    if field_type == "textarea":
        return forms.CharField(
            widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            max_length=2000,
            **common,
        )
    if field_type == "number":
        return forms.DecimalField(widget=forms.NumberInput(attrs={"class": "form-control"}), **common)
    if field_type == "date":
        return forms.DateField(widget=forms.DateInput(attrs={"class": "form-control"}), **common)
    if field_type == "time":
        return forms.TimeField(widget=forms.TimeInput(attrs={"class": "form-control"}), **common)
    if field_type == "url":
        return forms.URLField(widget=forms.URLInput(attrs={"class": "form-control"}), max_length=500, **common)
    if field_type == "boolean":
        common["required"] = False  # um checkbox obrigatório é sempre um erro de UX
        return forms.BooleanField(**common)
    if field_type == "choice":
        choices = [("", _("— Não especificar —"))] + [
            (choice, choice) for choice in definition.get("choices", [])
        ]
        return forms.ChoiceField(
            choices=choices, widget=forms.Select(attrs={"class": "form-select"}), **common
        )
    if field_type == "list":
        return RepeatedTextField(
            widget=RepeatedTextWidget(
                attrs={
                    "class": "form-control",
                    "placeholder": definition.get("placeholder", ""),
                }
            ),
            **common,
        )
    return forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}), max_length=250, **common
    )


def add_schema_fields(form: forms.Form, schema: list[dict], values: dict | None = None) -> None:
    """
    Acrescenta os campos do esquema a um formulário já construído.

    Os campos ficam prefixados com `extra__` para nunca colidirem com os
    campos reais do modelo.
    """
    values = values or {}
    for definition in schema:
        name = f"extra__{definition['key']}"
        form.fields[name] = build_form_field(definition)
        if definition["key"] in values:
            current = values[definition["key"]]
            if definition["type"] == "choice" and current:
                valid_values = {choice[0] for choice in form.fields[name].choices}
                if str(current) not in valid_values:
                    form.fields[name].choices.append((str(current), str(current)))
            form.initial.setdefault(name, current)


def collect_schema_values(form: forms.Form, schema: list[dict]) -> dict:
    """Recolhe, do formulário validado, os valores dos campos do esquema."""
    collected: dict = {}
    for definition in schema:
        value = form.cleaned_data.get(f"extra__{definition['key']}")
        if value in (None, "", [], ()):
            continue
        if isinstance(value, (list, tuple)):
            collected[definition["key"]] = [str(item) for item in value if str(item).strip()]
        else:
            collected[definition["key"]] = (
                value if isinstance(value, (bool, int, float)) else str(value)
            )
    return collected
