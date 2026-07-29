from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    """Adapts allauth to the platform's own user model and branding."""

    def save_user(self, request, user, form, commit: bool = True):
        data = form.cleaned_data
        user.first_name = (data.get("first_name") or "").strip()
        user.last_name = (data.get("last_name") or "").strip()
        user.phone = (data.get("phone") or "").strip()
        return super().save_user(request, user, form, commit=commit)

    def get_email_verification_redirect_url(self, email_address) -> str:
        from django.urls import reverse

        return reverse(settings.LOGIN_REDIRECT_URL)

    def get_from_email(self) -> str:
        return settings.DEFAULT_FROM_EMAIL
