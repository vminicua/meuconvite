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

    {"key": "trajo", "label": "Traje", "type": "text",
     "required": false, "help_text": "", "choices": ["A", "B"]}
"""

from __future__ import annotations

import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

FIELD_TYPES: dict[str, str] = {
    "text": _("Texto curto"),
    "textarea": _("Texto longo"),
    "number": _("Número"),
    "date": _("Data"),
    "time": _("Hora"),
    "url": _("Ligação"),
    "choice": _("Lista de opções"),
    "boolean": _("Sim / Não"),
}

MAX_FIELDS = 20


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
            widget=forms.Textarea(attrs={"rows": 3}), max_length=2000, **common
        )
    if field_type == "number":
        return forms.DecimalField(**common)
    if field_type == "date":
        return forms.DateField(widget=forms.DateInput(), **common)
    if field_type == "time":
        return forms.TimeField(widget=forms.TimeInput(), **common)
    if field_type == "url":
        return forms.URLField(max_length=500, **common)
    if field_type == "boolean":
        common["required"] = False  # um checkbox obrigatório é sempre um erro de UX
        return forms.BooleanField(**common)
    if field_type == "choice":
        choices = [("", "———")] + [
            (choice, choice) for choice in definition.get("choices", [])
        ]
        return forms.ChoiceField(choices=choices, **common)
    return forms.CharField(max_length=250, **common)


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
            form.initial.setdefault(name, values[definition["key"]])


def collect_schema_values(form: forms.Form, schema: list[dict]) -> dict:
    """Recolhe, do formulário validado, os valores dos campos do esquema."""
    collected: dict = {}
    for definition in schema:
        value = form.cleaned_data.get(f"extra__{definition['key']}")
        if value in (None, ""):
            continue
        collected[definition["key"]] = value if isinstance(value, (bool, int, float)) else str(value)
    return collected
