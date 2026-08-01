"""Small helpers used across the project."""

from __future__ import annotations

import re
import secrets
import string
import unicodedata

from django.utils.text import slugify

# Characters that are unambiguous when read out loud or typed by hand.
_SHORT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_secure_token(length: int = 32) -> str:
    """URL-safe cryptographically secure token (used in public links)."""
    return secrets.token_urlsafe(length)[:length] if length else secrets.token_urlsafe(32)


def generate_short_code(length: int = 8) -> str:
    """Human friendly code (no 0/O/1/I) for manual search at the door."""
    return "".join(secrets.choice(_SHORT_CODE_ALPHABET) for _ in range(length))


def generate_invitation_code() -> str:
    """Return the compact, URL-safe code used in individual invitations."""
    return generate_short_code(4)


def generate_numeric_code(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def unique_slugify(instance, value: str, slug_field: str = "slug", max_length: int = 60) -> str:
    """
    Build a slug unique across the model, appending a short suffix when needed.

    Does not hit the database more than a handful of times because the
    suffix is random rather than an incrementing counter.
    """
    model = instance.__class__
    base = slugify(value)[:max_length] or generate_short_code(6).lower()
    slug = base
    queryset = model._default_manager.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.filter(**{slug_field: slug}).exists():
        suffix = generate_short_code(4).lower()
        slug = f"{base[: max_length - len(suffix) - 1]}-{suffix}"
    return slug


def get_client_ip(request) -> str | None:
    """
    Best-effort client IP.

    X-Forwarded-For is only trusted when the deployment sits behind a
    proxy (cPanel/LiteSpeed does), and only the first entry is used.
    """
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    remote = request.META.get("REMOTE_ADDR")
    return remote[:45] if remote else None


def get_user_agent(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:400]


def normalise_phone(value: str | None, default_country_code: str = "+258") -> str:
    """
    Normalise Mozambican phone numbers to +258XXXXXXXXX.

    Unknown formats are returned trimmed rather than rejected, because the
    platform also has to accept foreign guests.
    """
    if not value:
        return ""
    digits = re.sub(r"[^\d+]", "", value.strip())
    if not digits:
        return ""
    if digits.startswith("+"):
        return digits[:20]
    if digits.startswith("00"):
        return f"+{digits[2:]}"[:20]
    if digits.startswith("258"):
        return f"+{digits}"[:20]
    # Local notation: 84 123 4567 or 084 123 4567.
    local = digits[1:] if digits.startswith("0") else digits
    if len(local) == 9 and local.startswith("8"):
        return f"{default_country_code}{local}"
    return digits[:20]


def strip_accents(value: str) -> str:
    """Used for accent-insensitive guest search."""
    normalised = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalised if not unicodedata.combining(char))


def mask_email(email: str) -> str:
    """Partially hide an email address in logs and audit trails."""
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    visible = local[:2]
    return f"{visible}{'*' * max(len(local) - 2, 1)}@{domain}"
