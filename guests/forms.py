from django import forms

from core.forms import BootstrapModelForm

from .models import Gift, Guest, InvitationChannel


class SendInvitationForm(forms.Form):
    channel = forms.ChoiceField(
        label="Enviar por",
        choices=InvitationChannel.choices,
        widget=forms.RadioSelect,
    )


class GuestForm(BootstrapModelForm):
    class Meta:
        model = Guest
        fields = ["full_name", "phone", "email", "party_size", "allowed_events", "notes"]
        widgets = {
            "party_size": forms.NumberInput(attrs={"min": 1, "max": 20}),
            "allowed_events": forms.CheckboxSelectMultiple(
                attrs={"class": "guest-programme-list"}
            ),
        }

    def __init__(self, *args, wedding=None, **kwargs):
        super().__init__(*args, **kwargs)
        if wedding is not None:
            self.fields["allowed_events"].queryset = wedding.events.filter(
                is_active=True
            ).order_by("date", "start_time", "display_order")
        self.fields["allowed_events"].required = False
        self.fields["allowed_events"].label = "Acesso ao programa"
        self.fields["allowed_events"].help_text = (
            "Deixe todas desmarcadas para permitir todo o programa. "
            "Seleccione apenas quando este convite for limitado."
        )


class GiftForm(BootstrapModelForm):
    class Meta:
        model = Gift
        fields = ["name", "description", "allow_multiple"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }
