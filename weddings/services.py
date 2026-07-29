"""
Write operations for weddings and their team.

Views stay thin: they validate input with forms and delegate here, where
transactions and the audit trail are handled consistently.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from audit.models import AuditAction
from audit.services import log_action, log_create, log_update, model_to_dict

from .models import Wedding, WeddingMember, WeddingRole, WeddingStatus


@dataclass(frozen=True)
class ChecklistItem:
    """One requirement shown in the "what is missing" panel."""

    code: str
    label: str
    done: bool
    required: bool
    url_name: str = ""

    @property
    def blocking(self) -> bool:
        return self.required and not self.done


@transaction.atomic
def create_wedding(*, owner, data: dict, request=None) -> Wedding:
    """Create a wedding and register the owner as a team member."""
    wedding = Wedding(owner=owner, **data)
    wedding.full_clean(exclude=["public_token", "slug"] if not data.get("slug") else ["public_token"])
    wedding.save()

    membership = WeddingMember(
        wedding=wedding,
        user=owner,
        role=WeddingRole.OWNER,
        accepted_at=timezone.now(),
    )
    membership.apply_role_defaults()
    membership.save()

    log_create(wedding, actor=owner, wedding=wedding, request=request)
    return wedding


@transaction.atomic
def update_wedding(*, wedding: Wedding, data: dict, actor, request=None) -> Wedding:
    """Apply validated changes to a wedding, recording the diff."""
    old_data = model_to_dict(wedding)
    for field, value in data.items():
        setattr(wedding, field, value)
    wedding.full_clean(exclude=["public_token"])
    wedding.save()
    log_update(wedding, old_data=old_data, actor=actor, wedding=wedding, request=request)
    return wedding


def build_checklist(wedding: Wedding) -> list[ChecklistItem]:
    """
    What still has to be done before the wedding can be published.

    Items for features that arrive in later phases (guests, invitations)
    are added by those apps as they are implemented; the publish rule only
    depends on the required items present here.
    """
    from events.models import ScheduleItem, WeddingEvent, WeddingLocation

    events = WeddingEvent.objects.filter(wedding=wedding, is_active=True)
    has_rsvp_event = events.filter(requires_rsvp=True).exists()

    items = [
        ChecklistItem(
            code="couple",
            label=_("Informações dos noivos preenchidas"),
            done=bool(wedding.bride_full_name and wedding.groom_full_name),
            required=True,
            url_name="weddings:settings",
        ),
        ChecklistItem(
            code="date",
            label=_("Data principal definida"),
            done=bool(wedding.main_date),
            required=True,
            url_name="weddings:settings",
        ),
        ChecklistItem(
            code="events",
            label=_("Pelo menos um evento criado"),
            done=events.exists(),
            required=True,
            url_name="events:list",
        ),
        ChecklistItem(
            code="locations",
            label=_("Pelo menos um local criado"),
            done=WeddingLocation.objects.filter(wedding=wedding).exists(),
            required=True,
            url_name="events:location_list",
        ),
        ChecklistItem(
            code="rsvp_event",
            label=_("Um evento aceita confirmações de presença"),
            done=has_rsvp_event,
            required=False,
            url_name="events:list",
        ),
        ChecklistItem(
            code="schedule",
            label=_("Programa do dia definido"),
            done=ScheduleItem.objects.filter(wedding=wedding).exists(),
            required=False,
            url_name="events:schedule",
        ),
        ChecklistItem(
            code="cover",
            label=_("Fotografia de capa carregada"),
            done=bool(wedding.cover_image),
            required=False,
            url_name="weddings:settings",
        ),
        ChecklistItem(
            code="welcome",
            label=_("Mensagem de boas-vindas escrita"),
            done=bool(wedding.welcome_message),
            required=False,
            url_name="weddings:settings",
        ),
    ]
    return items


def missing_requirements(wedding: Wedding) -> list[ChecklistItem]:
    return [item for item in build_checklist(wedding) if item.blocking]


@transaction.atomic
def publish_wedding(*, wedding: Wedding, actor, request=None) -> Wedding:
    """Make the wedding public after validating the mandatory checklist."""
    if wedding.status == WeddingStatus.BLOCKED:
        raise PermissionDenied(_("Este casamento está bloqueado. Contacte o suporte."))

    missing = missing_requirements(wedding)
    if missing:
        raise ValidationError(
            [_("Falta completar: %(item)s") % {"item": item.label} for item in missing]
        )

    wedding.status = WeddingStatus.PUBLISHED
    wedding.published_at = wedding.published_at or timezone.now()
    wedding.save(update_fields=["status", "published_at", "updated_at"])

    log_action(
        action=AuditAction.PUBLISH,
        actor=actor,
        wedding=wedding,
        request=request,
        instance=wedding,
        new_data={"status": wedding.status},
    )
    return wedding


@transaction.atomic
def unpublish_wedding(*, wedding: Wedding, actor, request=None) -> Wedding:
    """Return a published wedding to draft (public pages stop responding)."""
    old_status = wedding.status
    wedding.status = WeddingStatus.DRAFT
    wedding.save(update_fields=["status", "updated_at"])
    log_action(
        action=AuditAction.UPDATE,
        actor=actor,
        wedding=wedding,
        request=request,
        instance=wedding,
        old_data={"status": old_status},
        new_data={"status": wedding.status},
    )
    return wedding


@transaction.atomic
def archive_wedding(*, wedding: Wedding, actor, request=None) -> Wedding:
    """
    Archive instead of deleting.

    No data is removed: the wedding simply stops being listed and its
    public pages stop responding.
    """
    old_status = wedding.status
    wedding.status = WeddingStatus.ARCHIVED
    wedding.save(update_fields=["status", "updated_at"])
    log_action(
        action=AuditAction.UPDATE,
        actor=actor,
        wedding=wedding,
        request=request,
        instance=wedding,
        old_data={"status": old_status},
        new_data={"status": wedding.status},
    )
    return wedding


@transaction.atomic
def add_member(
    *,
    wedding: Wedding,
    user,
    role: str,
    permissions: dict | None = None,
    actor,
    request=None,
    notes: str = "",
) -> WeddingMember:
    """
    Add (or reactivate) a team member.

    Permissions default to the role template and can then be overridden
    field by field.
    """
    if user.pk == wedding.owner_id:
        raise ValidationError(_("O proprietário já faz parte da equipa."))

    membership, created = WeddingMember.objects.get_or_create(
        wedding=wedding,
        user=user,
        defaults={"role": role, "notes": notes},
    )
    membership.role = role
    membership.notes = notes or membership.notes
    membership.is_active = True
    membership.apply_role_defaults()
    for field, value in (permissions or {}).items():
        if field.startswith("can_"):
            setattr(membership, field, bool(value))
    membership.full_clean()
    membership.save()

    log_action(
        action=AuditAction.MEMBER_ADDED if created else AuditAction.PERMISSION_CHANGED,
        actor=actor,
        wedding=wedding,
        request=request,
        instance=membership,
        new_data={"role": membership.role, "user": user.email},
    )
    return membership


@transaction.atomic
def update_member(
    *, membership: WeddingMember, role: str, permissions: dict, actor, request=None
) -> WeddingMember:
    old_data = model_to_dict(membership)
    membership.role = role
    for field, value in permissions.items():
        if field.startswith("can_"):
            setattr(membership, field, bool(value))
    membership.full_clean()
    membership.save()
    log_update(
        membership,
        old_data=old_data,
        actor=actor,
        wedding=membership.wedding,
        request=request,
    )
    return membership


@transaction.atomic
def deactivate_member(*, membership: WeddingMember, actor, request=None) -> None:
    """Revoke access without deleting the history of what the member did."""
    membership.is_active = False
    membership.save(update_fields=["is_active", "updated_at"])
    log_action(
        action=AuditAction.MEMBER_REMOVED,
        actor=actor,
        wedding=membership.wedding,
        request=request,
        instance=membership,
        old_data={"user": membership.user.email, "role": membership.role},
    )
