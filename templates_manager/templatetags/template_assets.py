"""
Recursos opcionais por template.

Cada template pode ter a sua própria folha de estilos, uma camada decorativa
e um script, sem tocar nos ficheiros partilhados dos layouts:

    static/css/tpl/<código>.css
    static/js/tpl/<código>.js
    templates/invitations/tpl/<código>.html

Só são incluídos quando existem, por isso um template novo continua a
funcionar sem nenhum destes ficheiros.
"""

from __future__ import annotations

from functools import lru_cache

from django import template
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.templatetags.static import static
from django.template import TemplateDoesNotExist
from django.utils.html import format_html

register = template.Library()


@lru_cache(maxsize=256)
def _static_exists(path: str) -> bool:
    return bool(finders.find(path))


def _asset_url(kind: str, code: str) -> str:
    path = f"{kind}/tpl/{code}.{kind}"
    return static(path) if code and _static_exists(path) else ""


@register.simple_tag
def template_stylesheet(invitation_template) -> str:
    url = _asset_url("css", getattr(invitation_template, "code", ""))
    return format_html('<link href="{}" rel="stylesheet">', url) if url else ""


@register.simple_tag
def template_script(invitation_template) -> str:
    url = _asset_url("js", getattr(invitation_template, "code", ""))
    return format_html('<script src="{}" defer></script>', url) if url else ""


@register.simple_tag(takes_context=True)
def template_decor(context, invitation_template) -> str:
    code = getattr(invitation_template, "code", "")
    if not code:
        return ""
    try:
        decor = get_template(f"invitations/tpl/{code}.html")
    except TemplateDoesNotExist:
        return ""
    return decor.render(context.flatten())
