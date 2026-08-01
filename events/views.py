from __future__ import annotations

import json

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from weddings.permissions import capability_flags, require_wedding

from . import services
from .forms import (
    ProgramItemForm,
    ScheduleFieldForm,
    ScheduleItemForm,
    WeddingEventForm,
    WeddingLocationForm,
)
from .models import ScheduleItem, WeddingEvent, WeddingLocation

# ---------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------


@require_wedding()
def organisation(request: HttpRequest, wedding) -> HttpResponse:
    """Programa único: nome, data, horas e local na mesma sequência."""
    capabilities = capability_flags(wedding, request.user)
    if request.method == "POST":
        if not capabilities["can_manage_events"]:
            raise Http404
        form = ProgramItemForm(request.POST, wedding=wedding)
        if form.is_valid():
            services.create_program_item(
                wedding=wedding, form=form, actor=request.user, request=request
            )
            messages.success(request, "Item adicionado ao programa.")
            return redirect("events:organisation", wedding_id=wedding.pk)
        messages.error(request, "Corrija os campos assinalados.")
    else:
        form = ProgramItemForm(wedding=wedding, initial={"date": wedding.main_date})

    events = list(
        WeddingEvent.objects.filter(wedding=wedding)
        .select_related("location")
        .order_by("date", "start_time", "display_order")
    )
    return render(
        request,
        "events/organisation.html",
        {
            "wedding": wedding,
            "events": events,
            "form": form,
            "capabilities": capabilities,
        },
    )


@require_wedding()
def event_list(request: HttpRequest, wedding) -> HttpResponse:
    events = (
        WeddingEvent.objects.filter(wedding=wedding)
        .select_related("location")
        .order_by("date", "start_time", "display_order")
    )
    return render(
        request,
        "events/event_list.html",
        {
            "wedding": wedding,
            "events": events,
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding("can_manage_events")
def event_create(request: HttpRequest, wedding) -> HttpResponse:
    if request.method == "POST":
        form = WeddingEventForm(request.POST, wedding=wedding)
        if form.is_valid():
            services.create_event(wedding=wedding, form=form, actor=request.user, request=request)
            messages.success(request, "Evento criado.")
            return redirect("events:list", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingEventForm(wedding=wedding, initial={"date": wedding.main_date})

    return render(
        request,
        "events/event_form.html",
        {"wedding": wedding, "form": form, "capabilities": capability_flags(wedding, request.user)},
    )


@require_wedding("can_manage_events")
def event_edit(request: HttpRequest, wedding, event_id) -> HttpResponse:
    event = get_object_or_404(WeddingEvent, pk=event_id, wedding=wedding)

    if request.method == "POST":
        form = WeddingEventForm(request.POST, instance=event, wedding=wedding)
        if form.is_valid():
            services.update_event(event=event, form=form, actor=request.user, request=request)
            messages.success(request, "Evento actualizado.")
            return redirect("events:list", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingEventForm(instance=event, wedding=wedding)

    return render(
        request,
        "events/event_form.html",
        {
            "wedding": wedding,
            "form": form,
            "event": event,
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_POST
@require_wedding("can_manage_events")
def event_delete(request: HttpRequest, wedding, event_id) -> HttpResponse:
    event = get_object_or_404(WeddingEvent, pk=event_id, wedding=wedding)
    services.delete_event(event=event, actor=request.user, request=request)
    messages.info(request, "Evento eliminado.")
    return redirect("events:list", wedding_id=wedding.pk)


# ---------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------


@require_wedding()
def location_list(request: HttpRequest, wedding) -> HttpResponse:
    locations = WeddingLocation.objects.filter(wedding=wedding).order_by("display_order", "name")
    return render(
        request,
        "events/location_list.html",
        {
            "wedding": wedding,
            "locations": locations,
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding("can_manage_events")
def location_create(request: HttpRequest, wedding) -> HttpResponse:
    if request.method == "POST":
        form = WeddingLocationForm(request.POST, wedding=wedding)
        if form.is_valid():
            services.create_location(
                wedding=wedding, form=form, actor=request.user, request=request
            )
            messages.success(request, "Local criado.")
            return redirect("events:location_list", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingLocationForm(wedding=wedding)

    return render(
        request,
        "events/location_form.html",
        {"wedding": wedding, "form": form, "capabilities": capability_flags(wedding, request.user)},
    )


@require_wedding("can_manage_events")
def location_edit(request: HttpRequest, wedding, location_id) -> HttpResponse:
    location = get_object_or_404(WeddingLocation, pk=location_id, wedding=wedding)

    if request.method == "POST":
        form = WeddingLocationForm(request.POST, instance=location, wedding=wedding)
        if form.is_valid():
            services.update_location(
                location=location, form=form, actor=request.user, request=request
            )
            messages.success(request, "Local actualizado.")
            return redirect("events:location_list", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingLocationForm(instance=location, wedding=wedding)

    return render(
        request,
        "events/location_form.html",
        {
            "wedding": wedding,
            "form": form,
            "location": location,
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_POST
@require_wedding("can_manage_events")
def location_delete(request: HttpRequest, wedding, location_id) -> HttpResponse:
    location = get_object_or_404(WeddingLocation, pk=location_id, wedding=wedding)
    services.delete_location(location=location, actor=request.user, request=request)
    messages.info(request, "Local eliminado. Os eventos associados ficaram sem local.")
    return redirect("events:location_list", wedding_id=wedding.pk)


# ---------------------------------------------------------------------
# Programme (schedule)
# ---------------------------------------------------------------------


@require_wedding()
def schedule(request: HttpRequest, wedding) -> HttpResponse:
    """Programa do evento e gestão dos campos que o utilizador acrescenta."""
    capabilities = capability_flags(wedding, request.user)
    field_form = ScheduleFieldForm(wedding=wedding)

    if request.method == "POST":
        if not capabilities["can_manage_events"]:
            raise Http404
        field_form = ScheduleFieldForm(request.POST, wedding=wedding)
        if field_form.is_valid():
            services.add_schedule_field(
                wedding=wedding,
                definition=field_form.definition(),
                actor=request.user,
                request=request,
            )
            messages.success(
                request,
                f"Campo «{field_form.cleaned_data['label']}» acrescentado ao programa.",
            )
            return redirect("events:schedule", wedding_id=wedding.pk)
        messages.error(request, "Não foi possível acrescentar o campo.")

    items = (
        ScheduleItem.objects.filter(wedding=wedding)
        .select_related("event", "location")
        .order_by("display_order", "start_time")
    )
    return render(
        request,
        "events/schedule.html",
        {
            "wedding": wedding,
            "items": items,
            "schedule_fields": wedding.schedule_fields,
            "field_form": field_form,
            "capabilities": capabilities,
        },
    )


@require_POST
@require_wedding("can_manage_events")
def schedule_field_delete(request: HttpRequest, wedding, key: str) -> HttpResponse:
    services.remove_schedule_field(
        wedding=wedding, key=key, actor=request.user, request=request
    )
    messages.info(request, "Campo removido do programa.")
    return redirect("events:schedule", wedding_id=wedding.pk)


@require_wedding("can_manage_events")
def schedule_create(request: HttpRequest, wedding) -> HttpResponse:
    if request.method == "POST":
        form = ScheduleItemForm(request.POST, wedding=wedding)
        if form.is_valid():
            services.create_schedule_item(
                wedding=wedding, form=form, actor=request.user, request=request
            )
            messages.success(request, "Item adicionado ao programa.")
            return redirect("events:schedule", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = ScheduleItemForm(wedding=wedding, initial={"date": wedding.main_date})

    return render(
        request,
        "events/schedule_form.html",
        {"wedding": wedding, "form": form, "capabilities": capability_flags(wedding, request.user)},
    )


@require_wedding("can_manage_events")
def schedule_edit(request: HttpRequest, wedding, item_id) -> HttpResponse:
    item = get_object_or_404(ScheduleItem, pk=item_id, wedding=wedding)

    if request.method == "POST":
        form = ScheduleItemForm(request.POST, instance=item, wedding=wedding)
        if form.is_valid():
            services.update_schedule_item(
                item=item, form=form, actor=request.user, request=request
            )
            messages.success(request, "Item actualizado.")
            return redirect("events:schedule", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = ScheduleItemForm(instance=item, wedding=wedding)

    return render(
        request,
        "events/schedule_form.html",
        {
            "wedding": wedding,
            "form": form,
            "item": item,
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_POST
@require_wedding("can_manage_events")
def schedule_delete(request: HttpRequest, wedding, item_id) -> HttpResponse:
    item = get_object_or_404(ScheduleItem, pk=item_id, wedding=wedding)
    services.delete_schedule_item(item=item, actor=request.user, request=request)
    messages.info(request, "Item removido do programa.")
    return redirect("events:schedule", wedding_id=wedding.pk)


@require_POST
@require_wedding("can_manage_events")
def schedule_reorder(request: HttpRequest, wedding) -> JsonResponse:
    """
    Endpoint used by SortableJS.

    Expects `{"order": ["<uuid>", ...]}`. Ids outside this wedding are
    silently ignored by the service.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
        ordered_ids = payload["order"]
        if not isinstance(ordered_ids, list) or len(ordered_ids) > 500:
            raise ValueError("Lista inválida.")
    except (ValueError, KeyError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Pedido inválido."}, status=400)

    updated = services.reorder(model=ScheduleItem, wedding=wedding, ordered_ids=ordered_ids)
    return JsonResponse({"ok": True, "updated": updated})


@require_POST
@require_wedding("can_manage_events")
def event_reorder(request: HttpRequest, wedding) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode("utf-8"))
        ordered_ids = payload["order"]
        if not isinstance(ordered_ids, list) or len(ordered_ids) > 500:
            raise ValueError("Lista inválida.")
    except (ValueError, KeyError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Pedido inválido."}, status=400)

    updated = services.reorder(model=WeddingEvent, wedding=wedding, ordered_ids=ordered_ids)
    return JsonResponse({"ok": True, "updated": updated})
