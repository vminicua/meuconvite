"""
Read-only queries for weddings.

Keeping the aggregations here means views never build ad-hoc querysets
and the dashboard can be tuned (indexes, annotations) in one place.
"""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from .models import Wedding, WeddingMember, WeddingStatus


def categories_with_templates():
    """Tipos de evento activos, cada um com os templates que lhe são aplicáveis."""
    from events.models import EventCategory
    from templates_manager.models import InvitationTemplate

    categories = list(
        EventCategory.objects.active().order_by("display_order", "name")
    )
    catalogue = list(
        InvitationTemplate.objects.active()
        .prefetch_related("categories")
        .order_by("-is_featured", "display_order", "name")
    )
    category_ids_by_template = {
        template.pk: {item.pk for item in template.categories.all()}
        for template in catalogue
    }
    for category in categories:
        category.template_options = [
            template
            for template in catalogue
            if not category_ids_by_template[template.pk]
            or category.pk in category_ids_by_template[template.pk]
        ]
    return categories


def weddings_for_user(user) -> QuerySet[Wedding]:
    """Weddings listed on the user's home page, with cheap counters."""
    return (
        Wedding.objects.for_user(user)
        .exclude(status=WeddingStatus.ARCHIVED)
        .select_related(
            "owner", "subscription", "subscription__plan",
            "voucher_redemption", "voucher_redemption__voucher",
        )
        .annotate(
            event_count=Count("events", filter=Q(events__is_active=True), distinct=True),
            member_count=Count("members", filter=Q(members__is_active=True), distinct=True),
        )
        .order_by("main_date")
    )


def archived_weddings_for_user(user) -> QuerySet[Wedding]:
    return (
        Wedding.objects.for_user(user)
        .filter(status=WeddingStatus.ARCHIVED)
        .select_related("owner")
        .order_by("-main_date")
    )


def team_members(wedding: Wedding) -> QuerySet[WeddingMember]:
    return (
        WeddingMember.objects.filter(wedding=wedding)
        .select_related("user")
        .order_by("-is_active", "role", "created_at")
    )


def dashboard_summary(wedding: Wedding) -> dict:
    """
    Numbers shown on the wedding dashboard.

    Guest, invitation and check-in figures are added by their own apps in
    later phases; the keys already exist here so the template does not
    have to change.
    """
    from events.models import ScheduleItem, WeddingEvent, WeddingLocation

    event_stats = WeddingEvent.objects.filter(wedding=wedding).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        with_rsvp=Count("id", filter=Q(requires_rsvp=True, is_active=True)),
        with_qr=Count("id", filter=Q(requires_qr_code=True, is_active=True)),
    )

    return {
        "events_total": event_stats["active"] or 0,
        "events_with_rsvp": event_stats["with_rsvp"] or 0,
        "events_with_qr": event_stats["with_qr"] or 0,
        "locations_total": WeddingLocation.objects.filter(wedding=wedding).count(),
        "schedule_total": ScheduleItem.objects.filter(wedding=wedding).count(),
        "team_total": WeddingMember.objects.filter(wedding=wedding, is_active=True).count(),
        "days_until": wedding.days_until,
    }


def upcoming_events(wedding: Wedding, limit: int = 5):
    from events.models import WeddingEvent

    return list(
        WeddingEvent.objects.filter(wedding=wedding, is_active=True)
        .select_related("location")
        .order_by("date", "start_time", "display_order")[:limit]
    )
