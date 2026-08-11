from django import forms

from core.forms import BootstrapModelForm

from .models import Gift, Guest, InvitationChannel


class SendInvitationForm(forms.Form):
    channel = forms.ChoiceField(
        label="Enviar por",
        choices=InvitationChannel.choices,
        widget=forms.RadioSelect,
    )


class GuestImportForm(forms.Form):
    file = forms.FileField(
        label="Ficheiro Excel",
        help_text="Use o modelo MeuConvite em formato .xlsx (máximo 5 MB).",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um ficheiro Excel no formato .xlsx.")
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError("O ficheiro não pode exceder 5 MB.")
        return upload


class BulkInvitationForm(SendInvitationForm):
    guest_ids = forms.MultipleChoiceField(widget=forms.MultipleHiddenInput)

    def __init__(self, *args, wedding=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["guest_ids"].choices = [
            (str(pk), str(pk))
            for pk in Guest.objects.filter(wedding=wedding, is_active=True).values_list("pk", flat=True)
        ] if wedding is not None else []


class GuestForm(BootstrapModelForm):
    class Meta:
        model = Guest
        fields = [
            "full_name", "phone", "email", "party_size", "seating_assignment",
            "allowed_events", "notes",
        ]
        widgets = {
            "party_size": forms.NumberInput(attrs={"min": 1, "max": 20}),
            "allowed_events": forms.CheckboxSelectMultiple(
                attrs={"class": "guest-programme-list"}
            ),
        }

    def __init__(self, *args, wedding=None, allow_seating=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not allow_seating:
            self.fields.pop("seating_assignment", None)
        if wedding is not None:
            self.fields["allowed_events"].queryset = wedding.events.filter(
                is_active=True
            ).order_by("date", "start_time", "display_order")
        self.fields["allowed_events"].required = False
        self.fields["allowed_events"].label = "Acesso ao programa"
        self.fields["allowed_events"].help_text = (
            "Seleccione todos para permitir o programa completo. "
            "Se não seleccionar nenhum, o convite não mostrará o programa."
        )


class GiftForm(BootstrapModelForm):
    class Meta:
        model = Gift
        fields = ["name", "description", "allow_multiple"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }
