"""
Object level permissions and, above all, tenant isolation.

Every view that touches wedding data must obtain the wedding through
`get_wedding_or_404`, which only ever looks inside the set of weddings the
signed-in user belongs to. A wedding the user has no membership in is
reported as 404 (not 403) so the platform does not confirm that an id
exists.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from .models import Wedding, WeddingMember, WeddingRole, WeddingStatus

# Capabilities map 1:1 to the boolean fields on WeddingMember.
CAPABILITIES = (
    "can_manage_guests",
    "can_manage_events",
    "can_manage_seating",
    "can_check_in",
    "can_view_reports",
    "can_manage_design",
    "can_manage_billing",
)

# Capabilities that only the owner (or an explicitly equivalent member) has.
OWNER_ONLY_ACTIONS = frozenset({"delete_wedding", "transfer_ownership", "manage_members"})


def get_membership(wedding: Wedding, user) -> WeddingMember | None:
    """Active membership of `user` in `wedding`, if any."""
    if not user or not user.is_authenticated:
        return None
    return (
        WeddingMember.objects.filter(wedding=wedding, user=user, is_active=True)
        .select_related("user")
        .first()
    )


def is_owner(wedding: Wedding, user) -> bool:
    return bool(user and user.is_authenticated and wedding.owner_id == user.pk)


def user_can(wedding: Wedding, user, capability: str) -> bool:
    """
    Whether `user` may perform `capability` on `wedding`.

    Platform staff are deliberately *not* granted implicit access here:
    support tasks go through the dedicated administration area, which
    keeps its own audit trail.
    """
    if not user or not user.is_authenticated:
        return False
    if is_owner(wedding, user):
        return True

    membership = get_membership(wedding, user)
    if membership is None:
        return False

    if capability in OWNER_ONLY_ACTIONS:
        return membership.role == WeddingRole.SPOUSE
    if capability not in CAPABILITIES:
        raise ValueError(f"Capacidade desconhecida: {capability}")
    return bool(getattr(membership, capability, False))


def get_wedding_or_404(user, wedding_id, capability: str | None = None) -> Wedding:
    """Fetch a wedding the user may access, optionally requiring a capability."""
    wedding = get_object_or_404(
        Wedding.objects.for_user(user).select_related("owner"), pk=wedding_id
    )
    if capability and not user_can(wedding, user, capability):
        raise Http404
    return wedding


def require_wedding(capability: str | None = None, allow_blocked: bool = False) -> Callable:
    """
    Decorator for views under `casamentos/<uuid:wedding_id>/`.

    Injects `request.wedding` and `request.membership` and guarantees the
    signed-in user is allowed to be there.
    """

    def decorator(view_func: Callable) -> Callable:
        @login_required
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, wedding_id, *args, **kwargs) -> HttpResponse:
            wedding = get_wedding_or_404(request.user, wedding_id, capability)
            if not allow_blocked and wedding.status == WeddingStatus.BLOCKED:
                raise Http404
            request.wedding = wedding
            request.membership = get_membership(wedding, request.user)
            return view_func(request, wedding, *args, **kwargs)

        return wrapper

    return decorator


def capability_flags(wedding: Wedding, user) -> dict[str, bool]:
    """All capabilities at once, for templates (avoids repeated queries)."""
    if is_owner(wedding, user):
        flags = {capability: True for capability in CAPABILITIES}
        flags["is_owner"] = True
        flags["manage_members"] = True
        return flags

    membership = get_membership(wedding, user)
    flags = {
        capability: bool(getattr(membership, capability, False)) for capability in CAPABILITIES
    }
    flags["is_owner"] = False
    flags["manage_members"] = bool(membership and membership.role == WeddingRole.SPOUSE)
    return flags
