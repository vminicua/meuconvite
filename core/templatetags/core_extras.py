"""Template helpers for the administration interface."""

from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="add_class")
def add_class(field, css_classes: str):
    """Add CSS classes to a form widget from the template."""
    existing = field.field.widget.attrs.get("class", "")
    combined = f"{existing} {css_classes}".strip()
    return field.as_widget(attrs={"class": combined})


@register.filter(name="attr")
def set_attr(field, pair: str):
    """Usage: {{ field|attr:"placeholder:Nome completo" }}"""
    key, _, value = pair.partition(":")
    return field.as_widget(attrs={key.strip(): value.strip()})


@register.simple_tag
def status_badge(status: str, label: str) -> str:
    """Coloured badge for the many status fields in the platform."""
    mapping = {
        "draft": "secondary",
        "ready": "info",
        "published": "success",
        "active": "success",
        "sent": "primary",
        "opened": "info",
        "confirmed": "success",
        "attending": "success",
        "declined": "danger",
        "not_attending": "danger",
        "undecided": "warning",
        "pending": "warning",
        "expired": "secondary",
        "revoked": "dark",
        "archived": "secondary",
        "cancelled": "danger",
        "blocked": "danger",
    }
    colour = mapping.get(status, "secondary")
    return mark_safe(f'<span class="badge text-bg-{colour}">{label}</span>')


@register.filter(name="percentage")
def percentage(value, total) -> str:
    """Safe percentage for dashboard progress bars."""
    try:
        total = float(total)
        if total <= 0:
            return "0"
        return f"{(float(value) / total) * 100:.0f}"
    except (TypeError, ValueError):
        return "0"
