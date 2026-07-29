"""Small helpers to build test data without extra dependencies."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from events.models import EventType, ScheduleItem, WeddingEvent, WeddingLocation
from weddings.models import Wedding, WeddingMember, WeddingRole

User = get_user_model()

DEFAULT_PASSWORD = "Casamento2026!"


def create_user(email: str = "noiva@example.com", **extra) -> User:
    """
    Create a user that can sign in.

    Email verification is mandatory, so a verified allauth `EmailAddress`
    is created alongside the user — exactly what the signup flow does.
    """
    from allauth.account.models import EmailAddress

    extra.setdefault("first_name", "Natércia")
    extra.setdefault("last_name", "Matola")
    extra.setdefault("is_email_verified", True)
    user = User.objects.create_user(email=email, password=DEFAULT_PASSWORD, **extra)
    EmailAddress.objects.create(
        user=user, email=user.email, verified=user.is_email_verified, primary=True
    )
    return user


def create_wedding(owner=None, **extra) -> Wedding:
    owner = owner or create_user()
    defaults = {
        "bride_full_name": "Natércia Alice Matola",
        "groom_full_name": "Hivaldo José Cossa",
        "bride_short_name": "Natércia",
        "groom_short_name": "Hivaldo",
        "main_date": timezone.localdate() + timedelta(days=120),
        "city": "Maputo",
        "country": "Moçambique",
    }
    defaults.update(extra)
    wedding = Wedding.objects.create(owner=owner, **defaults)
    membership = WeddingMember(
        wedding=wedding, user=owner, role=WeddingRole.OWNER, accepted_at=timezone.now()
    )
    membership.apply_role_defaults()
    membership.save()
    return wedding


def add_member(wedding: Wedding, user, role: str = WeddingRole.COMMITTEE, **permissions):
    membership = WeddingMember(wedding=wedding, user=user, role=role)
    membership.apply_role_defaults()
    for field, value in permissions.items():
        setattr(membership, field, value)
    membership.save()
    return membership


def create_location(wedding: Wedding, name: str = "Igreja de São José", **extra):
    return WeddingLocation.objects.create(wedding=wedding, name=name, **extra)


def create_event(wedding: Wedding, name: str = "Cerimónia Religiosa", **extra):
    defaults = {"event_type": EventType.RELIGIOUS, "date": wedding.main_date}
    defaults.update(extra)
    return WeddingEvent.objects.create(wedding=wedding, name=name, **defaults)


def create_schedule_item(wedding: Wedding, title: str = "Cerimónia Religiosa", **extra):
    return ScheduleItem.objects.create(wedding=wedding, title=title, **extra)
