from __future__ import annotations

from . import services
from .models import Plan


def upgrade_modal(request):
    """Disponibiliza os planos no modal sem obrigar a sair da página actual."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    match = getattr(request, "resolver_match", None)
    wedding_id = match.kwargs.get("wedding_id") if match else None
    if not wedding_id:
        return {}
    from weddings.models import Wedding
    from weddings.permissions import capability_flags
    wedding = (Wedding.objects.for_user(request.user)
        .select_related("subscription", "subscription__plan")
        .filter(pk=wedding_id).first())
    if wedding is None:
        return {}
    current = services.limits(wedding)
    return {
        "upgrade_modal_wedding": wedding,
        "upgrade_modal_limits": current,
        "upgrade_modal_plans": Plan.objects.active().filter(
            price_mzn__gt=0, max_guests__gt=current.max_guests
        ).order_by("display_order", "max_guests"),
        "upgrade_modal_can_pay": capability_flags(wedding, request.user)["can_manage_billing"],
        "upgrade_modal_payzeno_ready": services.payzeno_is_ready(),
    }
