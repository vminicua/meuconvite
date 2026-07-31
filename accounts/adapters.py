from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    """Adapts allauth to the platform's own user model and branding."""

    def save_user(self, request, user, form, commit: bool = True):
        """
        Guarda os dados do registo.

        O formulário de registo pede um único campo "Nome": a primeira
        palavra fica como nome próprio e o resto como apelido. Se algum dia
        o formulário voltar a ter campos separados, esses têm prioridade.
        """
        data = form.cleaned_data

        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()

        if not first_name and not last_name:
            parts = (data.get("name") or "").split()
            if parts:
                first_name = parts[0]
                last_name = " ".join(parts[1:])

        user.first_name = first_name[:80]
        user.last_name = last_name[:80]
        user.phone = (data.get("phone") or "").strip()
        return super().save_user(request, user, form, commit=commit)

    def get_email_verification_redirect_url(self, email_address) -> str:
        from django.urls import reverse

        return reverse(settings.LOGIN_REDIRECT_URL)

    def get_from_email(self) -> str:
        return settings.DEFAULT_FROM_EMAIL
