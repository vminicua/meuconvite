from __future__ import annotations

from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.utils.translation import gettext_lazy as _

from core.utils import normalise_phone

from .models import User


class SignupForm(AllauthSignupForm):
    """
    Registo com o mínimo indispensável: nome, email e palavra-passe.

    Apelido, telefone e fotografia ficam para o perfil — pedir tudo à
    entrada só afasta quem está a experimentar a plataforma. O nome é um
    campo único; o adaptador divide-o em nome próprio e apelido.
    """

    name = forms.CharField(
        label=_("Nome"),
        max_length=160,
        widget=forms.TextInput(
            attrs={"placeholder": _("O seu nome"), "autocomplete": "name", "autofocus": True}
        ),
    )

    field_order = ["name", "email", "password1"]

    def clean_name(self) -> str:
        return " ".join(self.cleaned_data["name"].split())


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
