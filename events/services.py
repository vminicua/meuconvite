"""Write operations for events, locations and the programme."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max

from audit.services import log_create, log_delete, log_update, model_to_dict

from .models import ScheduleItem, WeddingEvent, WeddingLocation


def _next_display_order(model, wedding) -> int:
    current = model.objects.filter(wedding=wedding).aggregate(value=Max("display_order"))
    return (current["value"] or 0) + 10


@transaction.atomic
def create_event(*, wedding, form, actor, request=None) -> WeddingEvent:
    event: WeddingEvent = form.save(commit=False)
    event.wedding = wedding
    event.display_order = _next_display_order(WeddingEvent, wedding)
    event.full_clean(exclude=["slug"])
    event.save()
    log_create(event, actor=actor, wedding=wedding, request=request)
    return event


@transaction.atomic
def update_event(*, event: WeddingEvent, form, actor, request=None) -> WeddingEvent:
    old_data = model_to_dict(event)
    event = form.save(commit=False)
    event.full_clean(exclude=["slug"])
    event.save()
    log_update(event, old_data=old_data, actor=actor, wedding=event.wedding, request=request)
    return event


@transaction.atomic
def delete_event(*, event: WeddingEvent, actor, request=None) -> None:
    """
    Removes an event.

    Only allowed while nothing depends on it; the caller checks that. The
    full snapshot is kept in the audit trail.
    """
    log_delete(event, actor=actor, wedding=event.wedding, request=request)
    event.delete()


@transaction.atomic
def create_location(*, wedding, form, actor, request=None) -> WeddingLocation:
    location: WeddingLocation = form.save(commit=False)
    location.wedding = wedding
    location.display_order = _next_display_order(WeddingLocation, wedding)
    location.full_clean()
    location.save()
    log_create(location, actor=actor, wedding=wedding, request=request)
    return location


@transaction.atomic
def update_location(*, location: WeddingLocation, form, actor, request=None) -> WeddingLocation:
    old_data = model_to_dict(location)
    location = form.save(commit=False)
    location.full_clean()
    location.save()
    log_update(location, old_data=old_data, actor=actor, wedding=location.wedding, request=request)
    return location


@transaction.atomic
def delete_location(*, location: WeddingLocation, actor, request=None) -> None:
    log_delete(location, actor=actor, wedding=location.wedding, request=request)
    location.delete()


@transaction.atomic
def create_schedule_item(*, wedding, form, actor, request=None) -> ScheduleItem:
    item: ScheduleItem = form.save(commit=False)
    item.wedding = wedding
    item.display_order = _next_display_order(ScheduleItem, wedding)
    if not item.date:
        item.date = item.event.date if item.event_id else wedding.main_date
    item.full_clean()
    item.save()
    log_create(item, actor=actor, wedding=wedding, request=request)
    return item


@transaction.atomic
def update_schedule_item(*, item: ScheduleItem, form, actor, request=None) -> ScheduleItem:
    old_data = model_to_dict(item)
    item = form.save(commit=False)
    item.full_clean()
    item.save()
    log_update(item, old_data=old_data, actor=actor, wedding=item.wedding, request=request)
    return item


@transaction.atomic
def delete_schedule_item(*, item: ScheduleItem, actor, request=None) -> None:
    log_delete(item, actor=actor, wedding=item.wedding, request=request)
    item.delete()


@transaction.atomic
def reorder(*, model, wedding, ordered_ids: list[str]) -> int:
    """
    Persist a drag-and-drop reordering.

    Ids that do not belong to `wedding` are ignored, so a tampered request
    cannot touch another couple's data. Returns how many rows changed.
    """
    objects = {str(obj.pk): obj for obj in model.objects.filter(wedding=wedding)}
    to_update = []
    for position, raw_id in enumerate(ordered_ids, start=1):
        obj = objects.get(str(raw_id))
        if obj is None:
            continue
        new_order = position * 10
        if obj.display_order != new_order:
            obj.display_order = new_order
            to_update.append(obj)

    if to_update:
        model.objects.bulk_update(to_update, ["display_order"])
    return len(to_update)
