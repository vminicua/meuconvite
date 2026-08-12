from __future__ import annotations

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from . import services
from .models import (
    Payment, PaymentProvider, PaymentStatus, PaymentWebhookEvent, Plan,
    Subscription, Voucher, VoucherRedemption,
)


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "max_guests", "sms_enabled", "max_sms", "is_active")
    list_filter = ("is_active", "sms_enabled")
    search_fields = ("code", "name")


@admin.register(VoucherRedemption)
class VoucherRedemptionAdmin(admin.ModelAdmin):
    list_display = ("voucher", "wedding", "guest_allowance", "sms_allowance", "created_at")
    search_fields = ("voucher__code", "wedding__primary_name", "wedding__secondary_name")
    autocomplete_fields = ("voucher", "wedding", "redeemed_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "event_family",
        "max_guests",
        "max_sms",
        "max_team",
        "price_display",
        "duration_days",
        "is_default",
        "is_active",
        "display_order",
    )
    list_filter = ("event_family", "is_active", "is_default")
    search_fields = ("name", "code")
    ordering = ("display_order", "max_guests")
    list_editable = ("display_order", "is_active")

    fieldsets = (
        (None, {"fields": ("code", "name", "description", "event_family", "display_order")}),
        (_("Limites"), {"fields": ("max_guests", "max_sms", "max_team")}),
        (_("Preço"), {"fields": ("price_mzn", "duration_days")}),
        (
            _("Funcionalidades"),
            {
                "fields": (
                    "allows_seating",
                    "allows_exports",
                    "removes_branding",
                )
            },
        ),
        (_("Estado"), {"fields": ("is_active", "is_default")}),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("wedding", "plan", "status", "guest_allowance", "sms_allowance", "starts_on", "ends_on")
    list_filter = ("status", "plan")
    search_fields = ("wedding__primary_name", "wedding__secondary_name", "wedding__slug")
    autocomplete_fields = ["wedding", "plan"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Verificação dos comprovativos.

    As duas acções em massa activam ou recusam pacotes através do serviço,
    para que a subscrição e o registo de auditoria fiquem sempre coerentes.
    """

    list_display = (
        "reference",
        "wedding",
        "plan",
        "amount_mzn",
        "method",
        "provider",
        "status",
        "transaction_id",
        "created_at",
    )
    list_filter = ("status", "provider", "method", "plan", "created_at")
    search_fields = (
        "reference",
        "transaction_id",
        "payer_phone",
        "wedding__primary_name",
        "wedding__slug",
    )
    date_hierarchy = "created_at"
    autocomplete_fields = ["wedding", "plan"]
    readonly_fields = (
        "reference", "provider_checkout_id", "provider_payment_id", "provider_status",
        "provider_checkout_url", "provider_expires_at", "provider_checked_at",
        "provider_payload", "created_at", "updated_at", "reviewed_by", "reviewed_at",
    )
    actions = ("action_confirm", "action_reject")

    fieldsets = (
        (None, {"fields": ("reference", "wedding", "plan", "requested_by")}),
        (
            _("Pagamento"),
            {"fields": (
                "method", "provider", "amount_mzn", "paid_to", "payer_phone",
                "transaction_id", "proof", "provider_checkout_id",
                "provider_payment_id", "provider_status", "provider_checkout_url",
                "provider_expires_at", "provider_checked_at", "provider_payload",
            )},
        ),
        (_("Verificação"), {"fields": ("status", "review_notes", "reviewed_by", "reviewed_at")}),
        (_("Datas"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.action(description=_("Confirmar pagamento e activar o pacote"))
    def action_confirm(self, request, queryset) -> None:
        confirmed = 0
        for payment in queryset.exclude(status=PaymentStatus.CONFIRMED):
            if payment.provider == PaymentProvider.PAYZENO:
                try:
                    _payment, paid = services.verify_payzeno_payment(payment=payment, request=request)
                except Exception:
                    continue
                if not paid:
                    continue
                confirmed += 1
                continue
            services.confirm_payment(
                payment=payment,
                actor=request.user,
                request=request,
                notes="Confirmado na administração.",
            )
            confirmed += 1
        self.message_user(
            request,
            ngettext(
                "%(count)d pagamento confirmado e pacote activado.",
                "%(count)d pagamentos confirmados e pacotes activados.",
                confirmed,
            )
            % {"count": confirmed},
            messages.SUCCESS,
        )

    @admin.action(description=_("Recusar pagamento"))
    def action_reject(self, request, queryset) -> None:
        rejected = 0
        for payment in queryset.filter(
            status__in=[
                PaymentStatus.PENDING_GATEWAY,
                PaymentStatus.AWAITING_PROOF,
                PaymentStatus.UNDER_REVIEW,
            ]
        ):
            services.reject_payment(
                payment=payment,
                actor=request.user,
                request=request,
                notes="Recusado na administração.",
            )
            rejected += 1
        self.message_user(
            request, _("%(count)d pagamento(s) recusado(s).") % {"count": rejected}, messages.WARNING
        )


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "checkout_id", "payment", "processed", "created_at")
    list_filter = ("processed", "event_type")
    search_fields = ("checkout_id", "event_key", "payment__reference")
    readonly_fields = [field.name for field in PaymentWebhookEvent._meta.fields]
    actions = None
