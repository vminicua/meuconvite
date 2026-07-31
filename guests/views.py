from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audit.services import log_create, log_delete, log_update, model_to_dict
from subscriptions.services import check_can_add_guests, limits
from weddings.permissions import capability_flags, require_wedding

from .forms import GuestForm
from .models import Guest


@require_wedding("can_manage_guests")
def guest_list(request: HttpRequest, wedding) -> HttpResponse:
    if request.method == "POST":
        form = GuestForm(request.POST)
        if form.is_valid():
            try:
                check_can_add_guests(wedding)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                guest = form.save(commit=False)
                guest.wedding = wedding
                guest.save()
                log_create(guest, actor=request.user, wedding=wedding, request=request)
                messages.success(request, "Convidado acrescentado.")
                return redirect("guests:list", wedding_id=wedding.pk)
    else:
        form = GuestForm()

    guests = Guest.objects.filter(wedding=wedding, is_active=True).order_by("full_name")
    current_limits = limits(wedding)
    return render(
        request,
        "guests/guest_list.html",
        {
            "wedding": wedding,
            "guests": guests,
            "form": form,
            "limits": current_limits,
            "guest_count": guests.count(),
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding("can_manage_guests")
def guest_edit(request: HttpRequest, wedding, guest_id) -> HttpResponse:
    guest = get_object_or_404(Guest, pk=guest_id, wedding=wedding, is_active=True)
    if request.method == "POST":
        old_data = model_to_dict(guest)
        form = GuestForm(request.POST, instance=guest)
        if form.is_valid():
            form.save()
            log_update(guest, old_data, actor=request.user, wedding=wedding, request=request)
            messages.success(request, "Convidado actualizado.")
            return redirect("guests:list", wedding_id=wedding.pk)
    else:
        form = GuestForm(instance=guest)
    return render(
        request,
        "guests/guest_form.html",
        {"wedding": wedding, "guest": guest, "form": form,
         "capabilities": capability_flags(wedding, request.user)},
    )


@require_POST
@require_wedding("can_manage_guests")
def guest_remove(request: HttpRequest, wedding, guest_id) -> HttpResponse:
    guest = get_object_or_404(Guest, pk=guest_id, wedding=wedding, is_active=True)
    log_delete(guest, actor=request.user, wedding=wedding, request=request)
    guest.is_active = False
    guest.save(update_fields=["is_active", "updated_at"])
    messages.info(request, "Convidado removido.")
    return redirect("guests:list", wedding_id=wedding.pk)
