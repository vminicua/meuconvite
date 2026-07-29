"""
Signals limited to non-critical bookkeeping.

Business rules never live in signals (see the project code standards);
these only keep the denormalised `is_email_verified` flag and the last
login IP in sync with what allauth/Django already did.
"""

from __future__ import annotations

from allauth.account.signals import email_confirmed
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from core.utils import get_client_ip


@receiver(email_confirmed)
def mark_email_verified(sender, request, email_address, **kwargs) -> None:
    user = email_address.user
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified", "updated_at"])


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs) -> None:
    ip = get_client_ip(request)
    if ip and user.last_login_ip != ip:
        user.last_login_ip = ip
        user.save(update_fields=["last_login_ip", "updated_at"])

    from audit.services import log_action

    log_action(
        actor=user,
        action="login",
        request=request,
        model_name="accounts.User",
        object_id=str(user.pk),
    )
