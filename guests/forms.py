from django import forms

from core.forms import BootstrapModelForm

from .models import Guest


class GuestForm(BootstrapModelForm):
    class Meta:
        model = Guest
        fields = ["full_name", "phone", "email", "party_size", "notes"]
        widgets = {"party_size": forms.NumberInput(attrs={"min": 1, "max": 20})}
