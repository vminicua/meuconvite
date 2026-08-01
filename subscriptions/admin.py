from __future__ import annotations

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from . import services
from .models import Payment, PaymentStatus, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "max_guests",
        "max_sms",
        "price_display",
        "duration_days",
        "is_default",
        "is_active",
        "display_order",
    )
    list_filter = ("is_active", "is_default")
    search_fields = ("name", "code")
    ordering = ("display_order", "max_guests")
    list_editable = ("display_order", "is_active")

    fieldsets = (
        (None, {"fields": ("code", "name", "description", "display_order")}),
        (_("Limites"), {"fields": ("max_guests", "max_events", "max_sms", "templates_limit")}),
        (_("Preço"), {"fields": ("price_mzn", "duration_days")}),
        (
            _("Funcionalidades"),
            {
                "fields": (
                    "allows_qr_checkin",
                    "allows_seating",
                    "allows_team",
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
        "status",
        "transaction_id",
        "created_at",
    )
    list_filter = ("status", "method", "plan", "created_at")
    search_fields = (
        "reference",
        "transaction_id",
        "payer_phone",
        "wedding__primary_name",
        "wedding__slug",
    )
    date_hierarchy = "created_at"
    autocomplete_fields = ["wedding", "plan"]
    readonly_fields = ("reference", "created_at", "updated_at", "reviewed_by", "reviewed_at")
    actions = ("action_confirm", "action_reject")

    fieldsets = (
        (None, {"fields": ("reference", "wedding", "plan", "requested_by")}),
        (
            _("Pagamento"),
            {"fields": ("method", "amount_mzn", "paid_to", "payer_phone", "transaction_id", "proof")},
        ),
        (_("Verificação"), {"fields": ("status", "review_notes", "reviewed_by", "reviewed_at")}),
        (_("Datas"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.action(description=_("Confirmar pagamento e activar o pacote"))
    def action_confirm(self, request, queryset) -> None:
        confirmed = 0
        for payment in queryset.exclude(status=PaymentStatus.CONFIRMED):
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
            status__in=[PaymentStatus.AWAITING_PROOF, PaymentStatus.UNDER_REVIEW]
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
