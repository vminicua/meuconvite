from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
import hashlib
import hmac
import json

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from weddings.permissions import capability_flags, require_wedding

from . import services
from .forms import PayzenoCheckoutForm, UpgradeRequestForm, VoucherApplyForm
from .models import Payment, PaymentProvider, PaymentStatus, PaymentWebhookEvent, Plan
from .payzeno import PayzenoError


@login_required
def account_subscription(request: HttpRequest) -> HttpResponse:
    """Compatibilidade com o antigo endereço global da subscrição."""
    wedding = request.user.owned_weddings.order_by("-created_at").first()
    if wedding is None:
        return redirect("weddings:list")
    return redirect("subscriptions:detail", wedding_id=wedding.pk)


@require_wedding()
def subscription_detail(request: HttpRequest, wedding) -> HttpResponse:
    """Pacote actual, opções de upgrade e pagamentos em curso."""
    capabilities = capability_flags(wedding, request.user)
    selected_plan_code = ""
    billing_phone = (
        request.user.phone
        or wedding.notification_phone_primary
        or wedding.notification_phone_secondary
        or ""
    )
    upgrade_form = PayzenoCheckoutForm(initial={"payer_phone": billing_phone})

    if request.method == "POST":
        if not capabilities["can_manage_billing"]:
            raise Http404
        selected_plan_code = request.POST.get("plan_code", "")
        plan = get_object_or_404(services.plans_for(wedding), code=selected_plan_code)
        upgrade_form = PayzenoCheckoutForm(request.POST)
        if upgrade_form.is_valid():
            try:
                success_url = request.build_absolute_uri(reverse(
                    "subscriptions:payzeno_success",
                    kwargs={"wedding_id": wedding.pk, "reference": "REFERENCE"},
                ))
                cancel_url = request.build_absolute_uri(reverse(
                    "subscriptions:payzeno_cancel",
                    kwargs={"wedding_id": wedding.pk, "reference": "REFERENCE"},
                ))
                # A referência nasce com Payment; o serviço substitui o marcador
                # depois de persistir o pedido.
                payment = services.initiate_payzeno_checkout(
                    wedding=wedding,
                    plan=plan,
                    actor=request.user,
                    request=request,
                    payer_phone=upgrade_form.cleaned_data["payer_phone"],
                    method=upgrade_form.cleaned_data["method"],
                    success_url=success_url,
                    cancel_url=cancel_url,
                )
            except (ValidationError, PayzenoError) as exc:
                error_messages = getattr(exc, "messages", [str(exc)])
                for message in error_messages:
                    messages.error(request, message)
            else:
                return redirect(payment.provider_checkout_url)
        else:
            messages.error(request, "Corrija os dados de pagamento assinalados.")

    current = services.limits(wedding)
    used = services.guest_count(wedding)
    sms_used = services.sms_count(wedding)

    return render(
        request,
        "subscriptions/subscription_detail.html",
        {
            "wedding": wedding,
            "limits": current,
            "guests_used": used,
            "sms_used": sms_used,
            "sms_usage_percent": current.sms_usage_percent(sms_used),
            "guests_remaining": current.guests_remaining(used),
            "usage_percent": current.usage_percent(used),
            "plans": services.plans_for(wedding)
            .order_by("display_order", "max_guests"),
            "upgrades": services.upgrade_options(wedding),
            "open_payments": Payment.objects.filter(
                wedding=wedding,
            status__in=[
                PaymentStatus.PENDING_GATEWAY,
                PaymentStatus.AWAITING_PROOF,
                PaymentStatus.UNDER_REVIEW,
            ],
            ).select_related("plan"),
            "history": Payment.objects.filter(wedding=wedding)
            .exclude(status__in=[
                PaymentStatus.PENDING_GATEWAY,
                PaymentStatus.AWAITING_PROOF,
                PaymentStatus.UNDER_REVIEW,
            ])
            .select_related("plan")[:10],
            "instructions": services.payment_instructions(),
            "capabilities": capabilities,
            "upgrade_form": upgrade_form,
            "selected_plan_code": selected_plan_code,
            "billing_phone": billing_phone,
            "voucher_form": VoucherApplyForm(),
            "voucher_redemption": getattr(wedding, "voucher_redemption", None),
            "payzeno_ready": services.payzeno_is_ready(),
        },
    )


@require_POST
@require_wedding("can_manage_billing")
def apply_voucher(request: HttpRequest, wedding) -> HttpResponse:
    form = VoucherApplyForm(request.POST)
    if form.is_valid():
        try:
            redemption = services.apply_voucher(
                wedding=wedding, code=form.cleaned_data["code"],
                actor=request.user, request=request,
            )
        except ValidationError as exc:
            for message in exc.messages:
                messages.error(request, message)
        else:
            messages.success(
                request,
                f"Voucher {redemption.voucher.code} aplicado: "
                f"até {redemption.guest_allowance} convidados"
                + (f" e {redemption.sms_allowance} SMS." if redemption.sms_allowance else "."),
            )
    else:
        messages.error(request, "Introduza um código de voucher válido.")
    return redirect("subscriptions:detail", wedding_id=wedding.pk)


@require_wedding("can_manage_billing")
def upgrade(request: HttpRequest, wedding, plan_code: str) -> HttpResponse:
    """Compatibilidade: o checkout actual é iniciado na página de subscrição."""
    get_object_or_404(services.plans_for(wedding), code=plan_code)
    return redirect("subscriptions:detail", wedding_id=wedding.pk)


@require_wedding()
def payment_detail(request: HttpRequest, wedding, reference: str) -> HttpResponse:
    """Instruções de pagamento e envio do comprovativo."""
    payment = get_object_or_404(
        Payment.objects.select_related("plan"), wedding=wedding, reference=reference
    )
    capabilities = capability_flags(wedding, request.user)

    if payment.provider == PaymentProvider.PAYZENO:
        return render(request, "subscriptions/payment_detail.html", {
            "wedding": wedding, "payment": payment, "capabilities": capabilities,
            "is_payzeno": True,
        })

    if request.method == "POST":
        if not capabilities["can_manage_billing"]:
            messages.error(request, "Não tem permissão para gerir a subscrição.")
            return redirect("subscriptions:detail", wedding_id=wedding.pk)

        form = UpgradeRequestForm(request.POST, request.FILES)
        if form.is_valid():
            services.submit_proof(
                payment=payment,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
            messages.success(
                request,
                "Obrigado. Vamos verificar o pagamento e activar o pacote — "
                "normalmente em poucas horas.",
            )
            return redirect("subscriptions:detail", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = UpgradeRequestForm(
            initial={
                "method": payment.method,
                "payer_phone": payment.payer_phone,
                "transaction_id": payment.transaction_id,
            }
        )

    return render(
        request,
        "subscriptions/payment_detail.html",
        {
            "wedding": wedding,
            "payment": payment,
            "form": form,
            "instructions": services.payment_instructions(),
            "whatsapp_url": services.whatsapp_url(payment),
            "capabilities": capabilities,
        },
    )


@require_POST
@require_wedding("can_manage_billing")
def cancel_payment(request: HttpRequest, wedding, reference: str) -> HttpResponse:
    payment = get_object_or_404(Payment, wedding=wedding, reference=reference)
    if payment.is_open:
        payment.status = PaymentStatus.CANCELLED
        payment.save(update_fields=["status", "updated_at"])
        messages.info(request, "Pedido de pagamento cancelado.")
    return redirect("subscriptions:detail", wedding_id=wedding.pk)


@require_wedding("can_manage_billing")
def payzeno_success(request: HttpRequest, wedding, reference: str) -> HttpResponse:
    payment = get_object_or_404(
        Payment, wedding=wedding, reference=reference, provider=PaymentProvider.PAYZENO
    )
    try:
        _payment, confirmed = services.verify_payzeno_payment(payment=payment, request=request)
    except PayzenoError:
        messages.warning(request, "O pagamento ainda não pôde ser confirmado. Voltaremos a verificar automaticamente.")
    else:
        if confirmed:
            messages.success(request, f"Pagamento confirmado. O pacote {payment.plan.name} já está activo.")
        else:
            messages.info(request, "O pagamento ainda está a ser processado.")
    return redirect("subscriptions:detail", wedding_id=wedding.pk)


@require_wedding("can_manage_billing")
def payzeno_cancel(request: HttpRequest, wedding, reference: str) -> HttpResponse:
    get_object_or_404(
        Payment, wedding=wedding, reference=reference, provider=PaymentProvider.PAYZENO
    )
    messages.info(request, "O checkout foi fechado sem concluir o pagamento.")
    return redirect("subscriptions:detail", wedding_id=wedding.pk)


@require_POST
@require_wedding("can_manage_billing")
def verify_payzeno(request: HttpRequest, wedding, reference: str) -> HttpResponse:
    payment = get_object_or_404(
        Payment, wedding=wedding, reference=reference, provider=PaymentProvider.PAYZENO
    )
    try:
        _payment, confirmed = services.verify_payzeno_payment(payment=payment, request=request)
    except PayzenoError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Pagamento confirmado e pacote activado." if confirmed else "O pagamento continua pendente.")
    return redirect("subscriptions:detail", wedding_id=wedding.pk)


@csrf_exempt
@require_POST
def payzeno_webhook(request: HttpRequest) -> HttpResponse:
    """Webhook sem confiança implícita: o estado é sempre reconfirmado na API."""
    if len(request.body) > 64 * 1024:
        return JsonResponse({"received": False}, status=413)
    webhook_secret = services.payzeno_configuration()["webhook_secret"]
    if webhook_secret:
        supplied_signature = request.headers.get("X-Signature", "").strip()
        if supplied_signature.startswith("sha256="):
            supplied_signature = supplied_signature[7:]
        expected_signature = hmac.new(
            webhook_secret.encode("utf-8"), request.body, hashlib.sha256
        ).hexdigest()
        if not supplied_signature or not hmac.compare_digest(
            supplied_signature.lower(), expected_signature
        ):
            return JsonResponse({"received": False}, status=401)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"received": False}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"received": False}, status=400)

    checkout_id = str(payload.get("checkout_id") or "")[:100]
    reference = str(payload.get("reference") or "")[:20]
    event_type = str(payload.get("event") or "")[:50]
    if event_type not in {
        "payment.succeeded", "payment.refunded", "payment.chargeback",
        "payment.cancelled", "payment.expired",
    }:
        return JsonResponse({"received": True}, status=202)
    event_key = hashlib.sha256(
        f"payzeno|{event_type}|{checkout_id}|{reference}|{payload.get('payment_id', '')}|{payload.get('status', '')}".encode()
    ).hexdigest()
    payment = Payment.objects.filter(
        provider=PaymentProvider.PAYZENO, provider_checkout_id=checkout_id
    ).first()
    if payment is None and reference:
        payment = Payment.objects.filter(
            provider=PaymentProvider.PAYZENO, reference=reference
        ).first()
    if payment is None:
        return JsonResponse({"received": True}, status=202)
    event, created = PaymentWebhookEvent.objects.get_or_create(
        event_key=event_key,
        defaults={
            "event_type": event_type, "checkout_id": checkout_id, "payment": payment,
        },
    )
    if not created and event.processed:
        return JsonResponse({"received": True})
    try:
        services.verify_payzeno_payment(payment=payment)
    except PayzenoError:
        event.processing_error = "Falha ao confirmar estado remoto."
        event.save(update_fields=["processing_error", "updated_at"])
        return JsonResponse({"received": False}, status=503)
    event.processed = True
    event.processing_error = ""
    event.save(update_fields=["processed", "processing_error", "updated_at"])
    return JsonResponse({"received": True})
