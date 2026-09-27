"""
``{% invtext "chave" %}`` — frase personalizável do convite.

    {% load invitation_texts %}
    {% invtext "gallery_title" %}
    {% invtext "greeting" convidado=guest_name %}
    {% invtext "open_button" as open_label %}

Usa ``texts`` do contexto (criado em ``invitation_context``); se não
existir, constrói-o a partir de ``wedding`` e ``template``. O resultado é
sempre HTML seguro: texto e valores são escapados.
"""

from __future__ import annotations

import logging

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

from weddings.invitation_texts import REGISTRY, InvitationTexts

register = template.Library()
logger = logging.getLogger(__name__)


def _texts(context) -> InvitationTexts | None:
    texts = context.get("texts")
    if isinstance(texts, InvitationTexts):
        return texts
    wedding = context.get("wedding")
    if wedding is None:
        return None
    layout = getattr(context.get("template"), "layout", "")
    return InvitationTexts(wedding, layout, guest_name=context.get("guest_name") or "")


@register.simple_tag(takes_context=True)
def invtext(context, key, **values):
    if key not in REGISTRY:
        if settings.DEBUG:
            raise template.TemplateSyntaxError(f"Texto de convite desconhecido: {key!r}")
        logger.warning("Texto de convite desconhecido: %s", key)
        return mark_safe("")
    texts = _texts(context)
    if texts is None:
        return mark_safe("")
    return texts.render(key, **values)
