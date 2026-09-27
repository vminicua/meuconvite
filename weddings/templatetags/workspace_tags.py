"""Template tags for the event workspace navigation."""

from __future__ import annotations

from django import template

from weddings.workspace import build_workspace_nav

register = template.Library()


@register.simple_tag(takes_context=True)
def workspace_nav(context):
    """Grouped navigation for the event in context (see weddings.workspace)."""
    wedding = context.get("wedding")
    if wedding is None:
        return []
    request = context.get("request")
    return build_workspace_nav(
        wedding,
        context.get("capabilities"),
        getattr(request, "resolver_match", None),
    )
