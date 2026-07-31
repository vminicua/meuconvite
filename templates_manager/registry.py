"""
Acesso ao catálogo de templates.

O catálogo passou para a base de dados (`InvitationTemplate`), gerido pela
equipa MeuConvite. Este módulo continua a existir como ponto único de
consulta, para que views, formulários e templates não falem directamente
com o modelo — e para que a aplicação continue a funcionar mesmo antes de
o catálogo estar semeado.
"""

from __future__ import annotations

from .models import InvitationTemplate

DEFAULT_TEMPLATE_CODE = "carta-selada"


def all_templates(category=None):
    """Templates activos, opcionalmente filtrados pelo tipo de evento."""
    return InvitationTemplate.objects.for_category(category)


def get_template(code: str) -> InvitationTemplate | None:
    """O template pedido, ou o primeiro disponível se o código não existir."""
    if code:
        found = InvitationTemplate.objects.filter(code=code).first()
        if found is not None:
            return found
    return (
        InvitationTemplate.objects.active().filter(code=DEFAULT_TEMPLATE_CODE).first()
        or InvitationTemplate.objects.active().first()
    )


def default_code() -> str:
    template = get_template("")
    return template.code if template else DEFAULT_TEMPLATE_CODE


def is_valid_code(code: str) -> bool:
    return InvitationTemplate.objects.active().filter(code=code).exists()


def template_choices() -> list[tuple[str, str]]:
    return [
        (template.code, template.name) for template in InvitationTemplate.objects.active()
    ]
