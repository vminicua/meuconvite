from __future__ import annotations

from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.utils.translation import gettext_lazy as _

from core.utils import normalise_phone

from .models import User


class SignupForm(AllauthSignupForm):
    """Registration form: email + name + optional phone."""

    first_name = forms.CharField(
        label=_("Nome próprio"),
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": _("Natércia"), "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label=_("Apelido"),
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": _("Matola"), "autocomplete": "family-name"}),
    )
    phone = forms.CharField(
        label=_("Telefone"),
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "+258 84 123 4567", "autocomplete": "tel", "inputmode": "tel"}
        ),
        help_text=_("Opcional. Usado apenas para contacto sobre a sua conta."),
    )

    field_order = ["first_name", "last_name", "email", "phone", "password1", "password2"]

    def clean_phone(self) -> str:
        return normalise_phone(self.cleaned_data.get("phone"))


class ProfileForm(forms.ModelForm):
    """Profile data the user can change themselves (email is not editable here)."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "avatar", "preferred_language"]
        labels = {
            "first_name": _("Nome próprio"),
            "last_name": _("Apelido"),
            "phone": _("Telefone"),
            "avatar": _("Fotografia"),
            "preferred_language": _("Idioma da interface"),
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+258 84 123 4567"}
            ),
            "avatar": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}
            ),
            "preferred_language": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_phone(self) -> str:
        return normalise_phone(self.cleaned_data.get("phone"))
