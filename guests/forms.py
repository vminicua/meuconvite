from django import forms

from core.forms import BootstrapModelForm

from .models import Guest


class GuestForm(BootstrapModelForm):
    class Meta:
        model = Guest
        fields = ["full_name", "phone", "email", "party_size", "allowed_events", "notes"]
        widgets = {
            "party_size": forms.NumberInput(attrs={"min": 1, "max": 20}),
            "allowed_events": forms.CheckboxSelectMultiple(),
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
