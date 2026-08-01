from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapForm, BootstrapModelForm
from core.schema import (
    DRESS_CODE_CHOICES,
    FIELD_TYPES,
    MAX_FIELDS,
    add_schema_fields,
    collect_schema_values,
    slugify_key,
)

from .models import ScheduleItem, WeddingEvent, WeddingLocation


class ProgramItemForm(BootstrapModelForm):
    """Formulário curto usado directamente na página do programa."""

    location_name = forms.CharField(
        label=_("Local"),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Ex.: Paróquia de Santo António")}),
    )
    address = forms.CharField(
        label=_("Endereço"),
        max_length=250,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Rua, bairro ou ligação do mapa")}),
    )

    class Meta:
        model = WeddingEvent
        fields = ["name", "date", "start_time", "end_time"]
        labels = {"name": _("Nome no programa")}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Ex.: Cerimónia religiosa")}),
            "date": forms.DateInput(),
            "start_time": forms.TimeInput(),
            "end_time": forms.TimeInput(),
        }

    def __init__(self, *args, wedding=None, **kwargs) -> None:
        self.wedding = wedding
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.location:
            self.fields["location_name"].initial = self.instance.location.name
            self.fields["address"].initial = self.instance.location.address

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end < start:
            self.add_error("end_time", _("A hora de fim deve ser posterior à hora de início."))
        return cleaned

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if self.wedding is not None:
            duplicates = WeddingEvent.objects.filter(wedding=self.wedding, name__iexact=name)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise forms.ValidationError(_("Já existe um item com este nome no programa."))
        return name


class WeddingEventForm(BootstrapModelForm):
    """
    Create/edit an event.

    The location dropdown is restricted to the locations of the same
    wedding — a second layer of isolation on top of the view checks.
    """

    class Meta:
        model = WeddingEvent
        fields = [
            "event_type",
            "name",
            "description",
            "date",
            "start_time",
            "end_time",
            "location",
            "map_url",
            "host_family",
            "dress_code",
            "instructions",
            "requires_rsvp",
            "requires_qr_code",
            "show_to_all_guests",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 3}),
            "date": forms.DateInput(),
            "start_time": forms.TimeInput(),
            "end_time": forms.TimeInput(),
        }
        help_texts = {
            "host_family": _("Opcional. Por exemplo, a família anfitriã do lobolo ou xiguiane."),
            "requires_qr_code": _("Exige leitura de QR Code à entrada deste evento."),
        }

    def __init__(self, *args, wedding=None, **kwargs) -> None:
        self.wedding = wedding
        super().__init__(*args, **kwargs)
        queryset = WeddingLocation.objects.none()
        if wedding is not None:
            queryset = WeddingLocation.objects.filter(wedding=wedding)
        self.fields["location"].queryset = queryset
        self.fields["location"].empty_label = _("— Sem local definido —")
        dress_choices = [("", _("— Não especificar —"))] + [
            (choice, choice) for choice in DRESS_CODE_CHOICES
        ]
        current_dress = getattr(self.instance, "dress_code", "")
        if current_dress and current_dress not in DRESS_CODE_CHOICES:
            dress_choices.append((current_dress, current_dress))
        self.fields["dress_code"] = forms.ChoiceField(
            label=_("Traje"),
            choices=dress_choices,
            required=False,
            widget=forms.Select(attrs={"class": "form-select"}),
        )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end < start:
            self.add_error("end_time", _("A hora de fim tem de ser posterior à hora de início."))
        return cleaned

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if self.wedding is None:
            return name
        duplicates = WeddingEvent.objects.filter(wedding=self.wedding, name__iexact=name)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(_("Já existe um evento com este nome neste evento."))
        return name


class WeddingLocationForm(BootstrapModelForm):
    class Meta:
        model = WeddingLocation
        fields = [
            "name",
            "address",
            "description",
            "map_url",
            "latitude",
            "longitude",
            "contact_phone",
            "parking_information",
            "transport_information",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "parking_information": forms.Textarea(attrs={"rows": 2}),
            "transport_information": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "map_url": _("Cole aqui a ligação partilhada do Google Maps."),
            "latitude": _("Opcional. Preenchido apenas se souber as coordenadas."),
        }

    def __init__(self, *args, wedding=None, **kwargs) -> None:
        self.wedding = wedding
        super().__init__(*args, **kwargs)

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if self.wedding is None:
            return name
        duplicates = WeddingLocation.objects.filter(wedding=self.wedding, name__iexact=name)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(_("Já existe um local com este nome neste evento."))
        return name


class ScheduleItemForm(BootstrapModelForm):
    """
    Um item do programa.

    Tem os campos que a plataforma já traz (hora, título, local, ícone) e
    ainda os campos que o próprio utilizador acrescentou a este evento
    (`Wedding.schedule_field_schema`), construídos aqui dinamicamente.
    """

    class Meta:
        model = ScheduleItem
        fields = [
            "title",
            "description",
            "date",
            "start_time",
            "end_time",
            "event",
            "location",
            "icon",
            "is_public",
        ]
        widgets = {
            "date": forms.DateInput(),
            "start_time": forms.TimeInput(),
            "end_time": forms.TimeInput(),
        }

    def __init__(self, *args, wedding=None, **kwargs) -> None:
        self.wedding = wedding
        super().__init__(*args, **kwargs)
        if wedding is not None:
            self.fields["event"].queryset = WeddingEvent.objects.filter(wedding=wedding)
            self.fields["location"].queryset = WeddingLocation.objects.filter(wedding=wedding)
        else:
            self.fields["event"].queryset = WeddingEvent.objects.none()
            self.fields["location"].queryset = WeddingLocation.objects.none()
        self.fields["event"].empty_label = _("— Independente de evento —")
        self.fields["location"].empty_label = _("— Sem local definido —")

        if wedding is not None:
            add_schema_fields(
                self, wedding.schedule_fields, self.instance.extra_data or {}
            )

    def extra_data(self) -> dict:
        if self.wedding is None:
            return {}
        return collect_schema_values(self, self.wedding.schedule_fields)


class ScheduleFieldForm(BootstrapForm):
    """
    Acrescenta um campo ao programa deste evento.

    A chave é derivada da etiqueta, para o utilizador não ter de pensar em
    identificadores técnicos.
    """

    label = forms.CharField(
        label=_("Nome do campo"),
        max_length=60,
        widget=forms.TextInput(attrs={"placeholder": _("Por exemplo: Responsável")}),
    )
    type = forms.ChoiceField(
        label=_("Tipo"),
        choices=[(key, label) for key, label in FIELD_TYPES.items()],
        initial="text",
    )
    choices = forms.CharField(
        label=_("Opções"),
        required=False,
        help_text=_("Só para listas de opções: separe por vírgulas."),
        widget=forms.TextInput(attrs={"placeholder": _("Igreja, Salão, Casa")}),
    )
    required = forms.BooleanField(label=_("Obrigatório"), required=False)

    def __init__(self, *args, wedding=None, **kwargs) -> None:
        self.wedding = wedding
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        label = (cleaned.get("label") or "").strip()
        if not label:
            return cleaned

        key = slugify_key(label)
        existing = {field["key"] for field in (self.wedding.schedule_fields if self.wedding else [])}
        if key in existing:
            raise forms.ValidationError(
                _("Já existe um campo com este nome no programa.")
            )
        if len(existing) >= MAX_FIELDS:
            raise forms.ValidationError(
                _("Já atingiu o máximo de %(max)s campos adicionais.") % {"max": MAX_FIELDS}
            )

        if cleaned.get("type") == "choice" and not (cleaned.get("choices") or "").strip():
            self.add_error("choices", _("Indique as opções, separadas por vírgulas."))

        cleaned["key"] = key
        return cleaned

    def definition(self) -> dict:
        """A definição pronta a acrescentar ao esquema do evento."""
        raw_choices = (self.cleaned_data.get("choices") or "").split(",")
        return {
            "key": self.cleaned_data["key"],
            "label": self.cleaned_data["label"].strip(),
            "type": self.cleaned_data["type"],
            "required": bool(self.cleaned_data.get("required")),
            "choices": [choice.strip() for choice in raw_choices if choice.strip()],
        }
