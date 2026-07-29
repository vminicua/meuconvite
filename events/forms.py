from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapModelForm

from .models import ScheduleItem, WeddingEvent, WeddingLocation


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
            raise forms.ValidationError(_("Já existe um evento com este nome neste casamento."))
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
            raise forms.ValidationError(_("Já existe um local com este nome neste casamento."))
        return name


class ScheduleItemForm(BootstrapModelForm):
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
