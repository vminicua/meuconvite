from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from weddings.permissions import capability_flags, require_wedding

from . import services
from .forms import UpgradeRequestForm
from .models import Payment, PaymentStatus, Plan


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
    current = services.limits(wedding)
    used = services.guest_count(wedding)

    return render(
        request,
        "subscriptions/subscription_detail.html",
        {
            "wedding": wedding,
            "limits": current,
            "guests_used": used,
            "guests_remaining": current.guests_remaining(used),
            "usage_percent": current.usage_percent(used),
            "plans": Plan.objects.active().order_by("display_order", "max_guests"),
            "upgrades": services.upgrade_options(wedding),
            "open_payments": Payment.objects.filter(
                wedding=wedding,
                status__in=[PaymentStatus.AWAITING_PROOF, PaymentStatus.UNDER_REVIEW],
            ).select_related("plan"),
            "history": Payment.objects.filter(wedding=wedding)
            .exclude(status__in=[PaymentStatus.AWAITING_PROOF, PaymentStatus.UNDER_REVIEW])
            .select_related("plan")[:10],
            "instructions": services.payment_instructions(),
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding("can_manage_billing")
def upgrade(request: HttpRequest, wedding, plan_code: str) -> HttpResponse:
    """Pede um pacote e mostra as instruções de pagamento."""
    plan = get_object_or_404(Plan.objects.active(), code=plan_code)

    if request.method == "POST":
        form = UpgradeRequestForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                payment = services.request_upgrade(
                    wedding=wedding,
                    plan=plan,
                    actor=request.user,
                    request=request,
                    **form.cleaned_data,
                )
            except ValidationError as exc:
                for message in exc.messages:
                    messages.error(request, message)
            else:
                messages.success(
                    request,
                    "Pedido registado. Siga as instruções de pagamento para concluir.",
                )
                return redirect(
                    "subscriptions:payment", wedding_id=wedding.pk, reference=payment.reference
                )
        else:
            messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = UpgradeRequestForm()

    return render(
        request,
        "subscriptions/upgrade.html",
        {
            "wedding": wedding,
            "plan": plan,
            "form": form,
            "limits": services.limits(wedding),
            "instructions": services.payment_instructions(),
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding()
def payment_detail(request: HttpRequest, wedding, reference: str) -> HttpResponse:
    """Instruções de pagamento e envio do comprovativo."""
    payment = get_object_or_404(
        Payment.objects.select_related("plan"), wedding=wedding, reference=reference
    )
    capabilities = capability_flags(wedding, request.user)

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
