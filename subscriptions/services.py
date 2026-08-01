"""
Regras de negócio das subscrições.

Todo o resto da plataforma pergunta aqui o que um evento pode fazer —
`limits(wedding)` é o único ponto de verdade sobre limites, para que
nenhuma view tenha de saber como os planos estão organizados.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from audit.models import AuditAction
from audit.services import log_action

from .models import (
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
)

# Usado quando ainda não existe nenhum plano na base de dados (instalação
# nova, antes de correr `seed_plans`): a plataforma continua utilizável.
FALLBACK_GUEST_LIMIT = 20


@dataclass(frozen=True)
class Limits:
    """O que este evento pode fazer, já resolvido."""

    plan_name: str
    max_guests: int
    max_events: int
    allows_qr_checkin: bool
    allows_seating: bool
    allows_team: bool
    allows_exports: bool
    removes_branding: bool
    templates_limit: int
    is_free: bool
    status: str
    days_remaining: int | None

    def guests_remaining(self, current: int) -> int:
        return max(self.max_guests - current, 0)

    def usage_percent(self, current: int) -> int:
        if self.max_guests <= 0:
            return 0
        return min(int(current / self.max_guests * 100), 100)


def default_plan() -> Plan | None:
    return (
        Plan.objects.active().filter(is_default=True).first()
        or Plan.objects.active().order_by("max_guests").first()
    )


def get_subscription(wedding) -> Subscription | None:
    return getattr(wedding, "subscription", None)


@transaction.atomic
def ensure_subscription(wedding) -> Subscription | None:
    """
    Garante que o evento tem uma subscrição.

    Chamado ao criar o evento. Se ainda não existirem planos configurados,
    não falha: o evento fica sem subscrição e os limites caem no valor
    predefinido.
    """
    existing = get_subscription(wedding)
    if existing is not None:
        return existing

    plan = default_plan()
    if plan is None:
        return None

    return Subscription.objects.create(
        wedding=wedding,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        guest_allowance=plan.max_guests,
    )


def limits(wedding) -> Limits:
    """Limites em vigor para este evento."""
    subscription = get_subscription(wedding)

    if subscription is None or not subscription.is_active:
        plan = subscription.plan if subscription else default_plan()
        if plan is None:
            return Limits(
                plan_name=str(_("Gratuito")),
                max_guests=FALLBACK_GUEST_LIMIT,
                max_events=1,
                allows_qr_checkin=False,
                allows_seating=False,
                allows_team=False,
                allows_exports=False,
                removes_branding=False,
                templates_limit=1,
                is_free=True,
                status=SubscriptionStatus.ACTIVE,
                days_remaining=None,
            )
        # Subscrição expirada: volta-se ao plano inicial, sem perder dados.
        fallback = default_plan() or plan
        return Limits(
            plan_name=fallback.name,
            max_guests=fallback.max_guests,
            max_events=fallback.max_events,
            allows_qr_checkin=fallback.allows_qr_checkin,
            allows_seating=fallback.allows_seating,
            allows_team=fallback.allows_team,
            allows_exports=fallback.allows_exports,
            removes_branding=fallback.removes_branding,
            templates_limit=fallback.templates_limit,
            is_free=fallback.is_free,
            status=subscription.status if subscription else SubscriptionStatus.ACTIVE,
            days_remaining=subscription.days_remaining if subscription else None,
        )

    plan = subscription.plan
    return Limits(
        plan_name=plan.name,
        # O que foi comprado manda, mesmo que o plano mude depois.
        max_guests=subscription.guest_allowance or plan.max_guests,
        max_events=plan.max_events,
        allows_qr_checkin=plan.allows_qr_checkin,
        allows_seating=plan.allows_seating,
        allows_team=plan.allows_team,
        allows_exports=plan.allows_exports,
        removes_branding=plan.removes_branding,
        templates_limit=plan.templates_limit,
        is_free=plan.is_free,
        status=subscription.status,
        days_remaining=subscription.days_remaining,
    )


def guest_count(wedding) -> int:
    """
    Quantos convidados o evento já tem.

    A aplicação `guests` chega na fase 2; até lá o total é zero e os
    limites são apenas informativos.
    """
    related = getattr(wedding, "guests", None)
    if related is None:
        return 0
    return related.filter(is_active=True).count()


def enabled_guest_ids(wedding, allowance: int | None = None) -> set:
    """Convidados cobertos pelo plano, pela ordem em que foram adicionados."""
    related = getattr(wedding, "guests", None)
    if related is None:
        return set()
    maximum = limits(wedding).max_guests if allowance is None else allowance
    return set(
        related.filter(is_active=True)
        .order_by("created_at", "pk")
        .values_list("pk", flat=True)[:maximum]
    )


def check_can_add_guests(wedding, quantity: int = 1) -> None:
    """
    Levanta `ValidationError` se o plano não comportar mais convidados.

    Ponto único de verificação: a importação de Excel e a criação manual de
    convidados (fase 2) chamam esta função.
    """
    allowed = limits(wedding)
    current = guest_count(wedding)
    if current + quantity > allowed.max_guests:
        raise ValidationError(
            _(
                "O pacote %(plan)s inclui %(max)s convidados e já tem %(current)s. "
                "Para acrescentar mais, subscreva um pacote maior."
            )
            % {"plan": allowed.plan_name, "max": allowed.max_guests, "current": current}
        )


def upgrade_options(wedding) -> list[Plan]:
    """Planos que representam de facto um upgrade face ao actual."""
    current = limits(wedding)
    return list(
        Plan.objects.active()
        .filter(max_guests__gt=current.max_guests)
        .order_by("max_guests")
    )


# ---------------------------------------------------------------------
# Pagamentos
# ---------------------------------------------------------------------


def payment_instructions() -> dict:
    """Dados de pagamento mostrados ao utilizador (vêm das settings)."""
    return {
        "mpesa_number": getattr(settings, "MPESA_NUMBER", ""),
        "mpesa_name": getattr(settings, "MPESA_ACCOUNT_NAME", ""),
        "whatsapp_number": getattr(settings, "WHATSAPP_NUMBER", ""),
    }


def whatsapp_url(payment: Payment) -> str:
    """Ligação que abre o WhatsApp com a mensagem do comprovativo pronta."""
    from urllib.parse import quote

    number = getattr(settings, "WHATSAPP_NUMBER", "").lstrip("+")
    if not number:
        return ""
    return f"https://wa.me/{number}?text={quote(payment.whatsapp_message)}"


@transaction.atomic
def request_upgrade(*, wedding, plan: Plan, actor, request=None, **details) -> Payment:
    """
    Registra a intenção de subscrever um pacote.

    Não altera limites: a subscrição só muda quando o pagamento é
    confirmado por quem verifica os comprovativos.
    """
    if plan.is_free:
        raise ValidationError(_("O plano gratuito não precisa de pagamento."))

    # Um pedido em aberto por evento e plano evita referências duplicadas
    # para o mesmo pagamento.
    existing = Payment.objects.filter(
        wedding=wedding,
        plan=plan,
        status__in=[PaymentStatus.AWAITING_PROOF, PaymentStatus.UNDER_REVIEW],
    ).first()
    if existing is not None:
        return existing

    payment = Payment.objects.create(
        wedding=wedding,
        plan=plan,
        requested_by=actor,
        amount_mzn=plan.price_mzn,
        paid_to=getattr(settings, "MPESA_NUMBER", ""),
        payer_phone=(details.get("payer_phone") or "").strip(),
        transaction_id=(details.get("transaction_id") or "").strip(),
        proof=details.get("proof") or None,
        method=details.get("method") or "mpesa",
    )
    if payment.transaction_id or payment.proof:
        payment.status = PaymentStatus.UNDER_REVIEW
        payment.save(update_fields=["status", "updated_at"])

    log_action(
        action=AuditAction.CREATE,
        actor=actor,
        wedding=wedding,
        request=request,
        instance=payment,
        new_data={"plan": plan.code, "amount": str(plan.price_mzn), "reference": payment.reference},
    )
    return payment


@transaction.atomic
def submit_proof(*, payment: Payment, actor, request=None, **details) -> Payment:
    """O utilizador diz que já pagou e indica o ID da transacção."""
    payment.payer_phone = (details.get("payer_phone") or payment.payer_phone).strip()
    payment.transaction_id = (details.get("transaction_id") or payment.transaction_id).strip()
    if details.get("proof"):
        payment.proof = details["proof"]
    payment.status = PaymentStatus.UNDER_REVIEW
    payment.save()

    log_action(
        action=AuditAction.UPDATE,
        actor=actor,
        wedding=payment.wedding,
        request=request,
        instance=payment,
        new_data={"status": payment.status, "transaction_id": payment.transaction_id},
    )
    return payment


@transaction.atomic
def confirm_payment(*, payment: Payment, actor, request=None, notes: str = "") -> Subscription:
    """
    Confirma um pagamento e activa o pacote.

    Usado pela administração da plataforma. É idempotente na parte que
    importa: confirmar duas vezes não duplica subscrições.
    """
    if payment.status == PaymentStatus.CONFIRMED:
        return payment.wedding.subscription

    payment.status = PaymentStatus.CONFIRMED
    payment.reviewed_by = actor if getattr(actor, "pk", None) else None
    payment.reviewed_at = timezone.now()
    payment.review_notes = notes[:300]
    payment.save()

    today = timezone.localdate()
    plan = payment.plan
    ends_on = today + timedelta(days=plan.duration_days) if plan.duration_days else None

    subscription, _created = Subscription.objects.update_or_create(
        wedding=payment.wedding,
        defaults={
            "plan": plan,
            "status": SubscriptionStatus.ACTIVE,
            "starts_on": today,
            "ends_on": ends_on,
            "guest_allowance": plan.max_guests,
            "notes": f"Activada pelo pagamento {payment.reference}",
        },
    )

    log_action(
        action=AuditAction.ADMIN_ACTION,
        actor=actor,
        wedding=payment.wedding,
        request=request,
        instance=payment,
        new_data={
            "status": payment.status,
            "plan": plan.code,
            "guest_allowance": plan.max_guests,
            "reference": payment.reference,
        },
    )
    return subscription


@transaction.atomic
def reject_payment(*, payment: Payment, actor, request=None, notes: str = "") -> Payment:
    payment.status = PaymentStatus.REJECTED
    payment.reviewed_by = actor if getattr(actor, "pk", None) else None
    payment.reviewed_at = timezone.now()
    payment.review_notes = notes[:300]
    payment.save()

    log_action(
        action=AuditAction.ADMIN_ACTION,
        actor=actor,
        wedding=payment.wedding,
        request=request,
        instance=payment,
        new_data={"status": payment.status, "notes": notes[:300]},
    )
    return payment


def total_confirmed_mzn() -> Decimal:
    """Total recebido, para o painel da administração."""
    from django.db.models import Sum

    result = Payment.objects.filter(status=PaymentStatus.CONFIRMED).aggregate(
        total=Sum("amount_mzn")
    )
    return result["total"] or Decimal("0")
