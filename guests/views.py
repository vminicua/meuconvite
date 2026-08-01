from django.contrib import messages
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import segno

from audit.models import AuditAction
from audit.services import log_action, log_create, log_delete, log_update, model_to_dict
from subscriptions.services import enabled_guest_ids, limits
from weddings.permissions import capability_flags, require_wedding

from .forms import GuestForm, SendInvitationForm
from .models import Guest, RSVPStatus
from . import messaging


def _guest_invitation_url(request: HttpRequest, guest: Guest) -> str:
    return request.build_absolute_uri(reverse("guest_invitation", args=[guest.invitation_token]))


def _qr_data_uri(url: str) -> str:
    return segno.make(url, error="h").svg_data_uri(scale=5, border=2)


@require_wedding("can_manage_guests")
def guest_list(request: HttpRequest, wedding) -> HttpResponse:
    if request.method == "POST":
        form = GuestForm(request.POST, wedding=wedding)
        if form.is_valid():
            guest = form.save(commit=False)
            guest.wedding = wedding
            guest.save()
            form.instance = guest
            form.save_m2m()
            log_create(guest, actor=request.user, wedding=wedding, request=request)
            messages.success(request, "Convidado acrescentado.")
            return redirect("guests:list", wedding_id=wedding.pk)
    else:
        form = GuestForm(wedding=wedding)

    guests = list(
        Guest.objects.filter(wedding=wedding, is_active=True)
        .prefetch_related("allowed_events", "invitation_deliveries")
        .order_by("full_name")
    )
    current_limits = limits(wedding)
    enabled_ids = enabled_guest_ids(wedding, current_limits.max_guests)
    guest_rows = []
    for guest in guests:
        is_enabled = guest.pk in enabled_ids
        invitation_url = _guest_invitation_url(request, guest) if is_enabled else ""
        deliveries = list(guest.invitation_deliveries.all())
        guest_rows.append({
            "guest": guest,
            "is_enabled": is_enabled,
            "invitation_url": invitation_url,
            "qr_data_uri": _qr_data_uri(invitation_url) if is_enabled else "",
            "allowed_events": list(guest.allowed_events.all()),
            "latest_delivery": deliveries[0] if deliveries else None,
            "edit_form": GuestForm(
                instance=guest,
                wedding=wedding,
                auto_id=f"edit-{guest.pk}-%s",
            ),
        })
    guest_rows.sort(key=lambda row: (not row["is_enabled"], row["guest"].full_name.casefold()))
    for position, row in enumerate(guest_rows, start=1):
        row["ord"] = position
    return render(
        request,
        "guests/guest_list.html",
        {
            "wedding": wedding,
            "guests": guests,
            "guest_rows": guest_rows,
            "form": form,
            "limits": current_limits,
            "guest_count": len(guests),
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding("can_manage_guests")
def guest_export_excel(request: HttpRequest, wedding) -> HttpResponse:
    """Exporta a lista filtrada num ficheiro Excel real (.xlsx)."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    queryset = Guest.objects.filter(wedding=wedding, is_active=True).prefetch_related(
        "allowed_events"
    )
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    programme = request.GET.get("programme", "").strip()
    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        )
    if status:
        queryset = queryset.filter(rsvp_status=status)
    if programme:
        queryset = queryset.filter(allowed_events__name__iexact=programme)

    enabled_ids = enabled_guest_ids(wedding)
    guests = list(queryset.distinct())
    guests.sort(key=lambda guest: (guest.pk not in enabled_ids, guest.full_name.casefold()))

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Convidados"
    headers = ["Ord.", "Convidado", "Telefone", "Email", "Lugares", "Programa autorizado", "Confirmação", "Estado"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="B5903E")

    for position, guest in enumerate(guests, start=1):
        allowed_events = list(guest.allowed_events.all())
        sheet.append([
            position,
            guest.full_name,
            guest.phone,
            guest.email,
            guest.party_size,
            ", ".join(event.name for event in allowed_events) or "Programa completo",
            guest.get_rsvp_status_display(),
            "Activo" if guest.pk in enabled_ids else "Bloqueado — requer subscrição",
        ])

    widths = {"A": 8, "B": 30, "C": 20, "D": 32, "E": 10, "F": 34, "G": 20, "H": 32}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    output = BytesIO()
    workbook.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="convidados.xlsx"'
    return response


@require_wedding("can_manage_guests")
def guest_edit(request: HttpRequest, wedding, guest_id) -> HttpResponse:
    guest = get_object_or_404(Guest, pk=guest_id, wedding=wedding, is_active=True)
    if request.method == "POST":
        old_data = model_to_dict(guest)
        form = GuestForm(request.POST, instance=guest, wedding=wedding)
        if form.is_valid():
            form.save()
            log_update(guest, old_data, actor=request.user, wedding=wedding, request=request)
            messages.success(request, "Convidado actualizado.")
            return redirect("guests:list", wedding_id=wedding.pk)
    else:
        form = GuestForm(instance=guest, wedding=wedding)
    return render(
        request,
        "guests/guest_form.html",
        {"wedding": wedding, "guest": guest, "form": form,
         "capabilities": capability_flags(wedding, request.user)},
    )


@require_POST
@require_wedding("can_manage_guests")
def guest_send_invitation(request: HttpRequest, wedding, guest_id) -> HttpResponse:
    guest = get_object_or_404(Guest, pk=guest_id, wedding=wedding, is_active=True)
    if guest.pk not in enabled_guest_ids(wedding):
        messages.error(request, "Este convidado requer uma subscrição activa antes do envio.")
        return redirect("guests:list", wedding_id=wedding.pk)

    form = SendInvitationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Escolha SMS ou WhatsApp para enviar o convite.")
        return redirect("guests:list", wedding_id=wedding.pk)

    invitation_url = _guest_invitation_url(request, guest)
    if form.cleaned_data["channel"] == "whatsapp":
        try:
            return redirect(
                messaging.whatsapp_invitation_url(
                    guest=guest,
                    invitation_url=invitation_url,
                )
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("guests:list", wedding_id=wedding.pk)

    try:
        delivery = messaging.send_invitation(
            guest=guest,
            channel=form.cleaned_data["channel"],
            invitation_url=invitation_url,
            actor=request.user,
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        log_action(
            action=AuditAction.INVITE_SENT,
            actor=request.user,
            wedding=wedding,
            request=request,
            instance=delivery,
            new_data={"channel": delivery.channel, "status": delivery.status},
        )
        messages.success(
            request,
            f"Convite de {guest.full_name} colocado na fila por {delivery.get_channel_display()}.",
        )
    return redirect("guests:list", wedding_id=wedding.pk)


@require_POST
@require_wedding("can_manage_guests")
def guest_remove(request: HttpRequest, wedding, guest_id) -> HttpResponse:
    guest = get_object_or_404(Guest, pk=guest_id, wedding=wedding, is_active=True)
    log_delete(guest, actor=request.user, wedding=wedding, request=request)
    guest.is_active = False
    guest.save(update_fields=["is_active", "updated_at"])
    messages.info(request, "Convidado removido.")
    return redirect("guests:list", wedding_id=wedding.pk)


def guest_invitation(request: HttpRequest, token: str) -> HttpResponse:
    """Individual invitation and RSVP surface addressed by an opaque token."""
    from templates_manager import registry
    from templates_manager.services import invitation_context

    guest = get_object_or_404(
        Guest.objects.select_related("wedding", "wedding__category").prefetch_related("allowed_events"),
        invitation_token=token,
        is_active=True,
    )
    wedding = guest.wedding
    if wedding.status in {"archived", "blocked"}:
        raise Http404
    if guest.pk not in enabled_guest_ids(wedding):
        raise Http404

    if request.method == "POST":
        response = request.POST.get("rsvp")
        if response in {RSVPStatus.CONFIRMED, RSVPStatus.DECLINED}:
            guest.rsvp_status = response
            guest.responded_at = timezone.now()
            guest.save(update_fields=["rsvp_status", "responded_at", "updated_at"])
            messages.success(request, "A sua resposta foi registada. Obrigado!")
            return redirect("guest_invitation", token=guest.invitation_token)

    template = registry.get_template(wedding.selected_template)
    if template is None:
        raise Http404
    context = invitation_context(wedding, template, guest=guest, is_preview=False)
    context["css_variables"] = template.css_variables(
        wedding.primary_color, wedding.secondary_color
    )
    return render(request, "invitations/preview.html", context)


@csrf_exempt
@require_POST
def twilio_message_status(request: HttpRequest) -> HttpResponse:
    """Webhook assinado do Twilio para estados de entrega e leitura."""
    auth_token = settings.TWILIO_AUTH_TOKEN
    signature = request.headers.get("X-Twilio-Signature", "")
    if not auth_token or not signature:
        return HttpResponse(status=403)

    from twilio.request_validator import RequestValidator

    callback_url = f"{settings.SITE_BASE_URL.rstrip('/')}{request.path}"
    if not RequestValidator(auth_token).validate(callback_url, request.POST, signature):
        return HttpResponse(status=403)
    messaging.update_delivery_status(
        provider_sid=request.POST.get("MessageSid", ""),
        status=request.POST.get("MessageStatus", ""),
        error_code=request.POST.get("ErrorCode", ""),
    )
    return HttpResponse(status=204)
