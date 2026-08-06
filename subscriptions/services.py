"""
Regras de negócio das subscrições.

Todo o resto da plataforma pergunta aqui o que um evento pode fazer —
`limits(wedding)` é o único ponto de verdade sobre limites, para que
nenhuma view tenha de saber como os planos estão organizados.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from audit.models import AuditAction
from audit.services import log_action

from .models import (
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
    Voucher,
    VoucherRedemption,
)
from .payzeno import (
    PayzenoAPIError,
    PayzenoClient,
    PayzenoConfigurationError,
    response_data,
)

# Usado quando ainda não existe nenhum plano na base de dados (instalação
# nova, antes de correr `seed_plans`): a plataforma continua utilizável.
FALLBACK_GUEST_LIMIT = 5
FALLBACK_SMS_LIMIT = 0


@dataclass(frozen=True)
class Limits:
    """O que este evento pode fazer, já resolvido."""

    plan_name: str
    max_guests: int
    max_events: int
    max_sms: int
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

    def sms_usage_percent(self, current: int) -> int:
        if self.max_sms <= 0:
            return 100 if current else 0
        return min(int(current / self.max_sms * 100), 100)


def default_plan() -> Plan | None:
    return (
        Plan.objects.active().filter(is_default=True).first()
        or Plan.objects.active().order_by("max_guests").first()
    )


def get_subscription(wedding) -> Subscription | None:
    return getattr(wedding, "subscription", None)


@transaction.atomic
def ensure_subscription(wedding, *, allow_free: bool = True) -> Subscription | None:
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
        status=SubscriptionStatus.ACTIVE if allow_free else SubscriptionStatus.PENDING,
        guest_allowance=plan.max_guests,
        sms_allowance=plan.max_sms,
    )


def event_requires_upgrade(wedding) -> bool:
    """Eventos adicionais começam bloqueados: cada conta recebe um único evento grátis."""
    subscription = get_subscription(wedding)
    return bool(
        subscription
        and subscription.plan.is_free
        and subscription.status == SubscriptionStatus.PENDING
    )


def limits(wedding) -> Limits:
    """Limites em vigor para este evento."""
    subscription = get_subscription(wedding)
    redemption = getattr(wedding, "voucher_redemption", None)

    if event_requires_upgrade(wedding):
        return Limits(
            plan_name=str(_("Aguardando upgrade")),
            max_guests=0,
            max_events=1,
            max_sms=0,
            allows_qr_checkin=True,
            allows_seating=False,
            allows_team=False,
            allows_exports=False,
            removes_branding=False,
            templates_limit=0,
            is_free=False,
            status=SubscriptionStatus.PENDING,
            days_remaining=None,
        )

    def with_voucher(resolved: Limits) -> Limits:
        if redemption is None:
            return resolved
        return Limits(
            plan_name=f"{resolved.plan_name} + Voucher {redemption.voucher.code}",
            max_guests=max(resolved.max_guests, redemption.guest_allowance),
            max_events=resolved.max_events,
            max_sms=max(resolved.max_sms, redemption.sms_allowance),
            allows_qr_checkin=resolved.allows_qr_checkin,
            allows_seating=resolved.allows_seating,
            allows_team=resolved.allows_team,
            allows_exports=resolved.allows_exports,
            removes_branding=resolved.removes_branding,
            templates_limit=resolved.templates_limit,
            is_free=resolved.is_free,
            status=resolved.status,
            days_remaining=resolved.days_remaining,
        )

    if subscription is None or not subscription.is_active:
        plan = subscription.plan if subscription else default_plan()
        if plan is None:
            return with_voucher(Limits(
                plan_name=str(_("Gratuito")),
                max_guests=FALLBACK_GUEST_LIMIT,
                max_events=1,
                max_sms=FALLBACK_SMS_LIMIT,
                allows_qr_checkin=True,
                allows_seating=False,
                allows_team=True,
                allows_exports=False,
                removes_branding=False,
                templates_limit=0,
                is_free=True,
                status=SubscriptionStatus.ACTIVE,
                days_remaining=None,
            ))
        # Subscrição expirada: volta-se ao plano inicial, sem perder dados.
        fallback = default_plan() or plan
        return with_voucher(Limits(
            plan_name=fallback.name,
            max_guests=fallback.max_guests,
            max_events=fallback.max_events,
            max_sms=0 if fallback.is_free else fallback.max_sms,
            allows_qr_checkin=True,
            allows_seating=fallback.allows_seating,
            allows_team=True,
            allows_exports=fallback.allows_exports,
            removes_branding=fallback.removes_branding,
            templates_limit=0,
            is_free=fallback.is_free,
            status=subscription.status if subscription else SubscriptionStatus.ACTIVE,
            days_remaining=subscription.days_remaining if subscription else None,
        ))

    plan = subscription.plan
    return with_voucher(Limits(
        plan_name=plan.name,
        # O que foi comprado manda, mesmo que o plano mude depois.
        max_guests=subscription.guest_allowance or plan.max_guests,
        max_events=plan.max_events,
        # O plano gratuito nunca envia SMS, mesmo que uma subscrição antiga
        # ainda guarde uma quota anterior no respectivo snapshot.
        max_sms=0 if plan.is_free else subscription.sms_allowance,
        allows_qr_checkin=True,
        allows_seating=plan.allows_seating,
        allows_team=True,
        allows_exports=plan.allows_exports,
        removes_branding=plan.removes_branding,
        templates_limit=0,
        is_free=plan.is_free,
        status=subscription.status,
        days_remaining=subscription.days_remaining,
    ))


@transaction.atomic
def apply_voucher(*, wedding, code: str, actor=None, request=None) -> VoucherRedemption:
    """Valida e consome um voucher sem permitir reutilização no mesmo evento."""
    normalised = (code or "").strip().upper()
    if not normalised:
        raise ValidationError(_("Introduza o código do voucher."))
    if VoucherRedemption.objects.select_for_update().filter(wedding=wedding).exists():
        raise ValidationError(_("Este evento já utilizou um voucher."))

    try:
        voucher = Voucher.objects.select_for_update().get(code__iexact=normalised)
    except Voucher.DoesNotExist as exc:
        raise ValidationError(_("O código do voucher não existe.")) from exc

    today = timezone.localdate()
    if not voucher.is_active:
        raise ValidationError(_("Este voucher está desactivado."))
    if voucher.valid_from and today < voucher.valid_from:
        raise ValidationError(_("Este voucher ainda não está disponível."))
    if voucher.valid_until and today > voucher.valid_until:
        raise ValidationError(_("Este voucher expirou."))
    if voucher.max_redemptions and voucher.redemptions.count() >= voucher.max_redemptions:
        raise ValidationError(_("Este voucher já atingiu o limite de utilizações."))

    redemption = VoucherRedemption.objects.create(
        voucher=voucher,
        wedding=wedding,
        redeemed_by=actor,
        guest_allowance=voucher.max_guests,
        sms_allowance=voucher.max_sms if voucher.sms_enabled else 0,
    )
    log_action(
        action=AuditAction.CREATE, actor=actor, request=request,
        instance=redemption, wedding=wedding,
    )
    return redemption


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
    """Convidados cobertos pelo plano, respeitando uma selecção manual."""
    related = getattr(wedding, "guests", None)
    if related is None:
        return set()
    maximum = limits(wedding).max_guests if allowance is None else allowance
    active = related.filter(is_active=True)
    if active.filter(plan_access__isnull=False).exists():
        active = active.filter(plan_access=True)
    return set(
        active.order_by("created_at", "pk").values_list("pk", flat=True)[:maximum]
    )


@transaction.atomic
def set_guest_plan_access(*, wedding, guest, enabled: bool) -> None:
    """Inclui ou retira um convidado, preservando os restantes lugares actuais."""
    related = wedding.guests.select_for_update().filter(is_active=True)
    current_ids = enabled_guest_ids(wedding)

    # Na primeira alteração convertemos a selecção automática numa escolha
    # explícita. Isso impede que a vaga libertada seja ocupada pelo convidado
    # seguinte antes de o utilizador escolher quem pretende incluir.
    if not related.filter(plan_access__isnull=False).exists():
        related.filter(pk__in=current_ids).update(plan_access=True)

    maximum = limits(wedding).max_guests
    if enabled:
        selected = related.filter(plan_access=True).exclude(pk=guest.pk).count()
        if selected >= maximum:
            raise ValidationError(
                _(
                    "O plano já tem %(max)s convidados activos. "
                    "Retire primeiro um convidado do limite."
                )
                % {"max": maximum}
            )
        guest.plan_access = True
    else:
        guest.plan_access = False
    guest.save(update_fields=["plan_access", "updated_at"])


def select_new_guest_if_capacity(*, wedding, guest) -> None:
    """Em modo manual, usa automaticamente uma vaga ainda disponível."""
    active = wedding.guests.filter(is_active=True)
    if not active.filter(plan_access__isnull=False).exists():
        return
    if active.filter(plan_access=True).count() < limits(wedding).max_guests:
        guest.plan_access = True
        guest.save(update_fields=["plan_access", "updated_at"])


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


def sms_count(wedding) -> int:
    """Número de tentativas de envio por SMS consumidas pelo evento."""
    related = getattr(wedding, "invitation_deliveries", None)
    if related is None:
        return 0
    return related.filter(channel="sms", counts_toward_limit=True).count()


def check_can_send_sms(wedding) -> None:
    """Impede envios quando a quota de SMS do pacote foi atingida."""
    allowed = limits(wedding)
    if allowed.max_sms <= 0:
        raise ValidationError(
            _(
                "A subscrição actual não inclui envios por SMS. "
                "Subscreva um pacote ou aplique um voucher com SMS."
            )
        )
    if sms_count(wedding) >= allowed.max_sms:
        raise ValidationError(
            _(
                "O pacote %(plan)s inclui %(max)s envio(s) por SMS e o limite já foi atingido. "
                "Actualize a subscrição para continuar a enviar por SMS."
            )
            % {"plan": allowed.plan_name, "max": allowed.max_sms}
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
    from platform_admin.models import configured_value

    return {
        "mpesa_number": configured_value("mpesa_number"),
        "mpesa_name": configured_value("mpesa_account_name"),
        "whatsapp_number": configured_value("whatsapp_number"),
    }


def payzeno_configuration() -> dict:
    """Configuração efectiva, sem nunca devolver a chave para templates."""
    from django.conf import settings
    from platform_admin.models import PlatformConfiguration, configured_value

    configuration = PlatformConfiguration.load()
    return {
        "enabled": bool(
            configuration.payzeno_enabled or getattr(settings, "PAYZENO_ENABLED", False)
        ),
        "api_key": configured_value("payzeno_api_key"),
        "webhook_secret": configured_value("payzeno_webhook_secret"),
        "base_url": configuration.payzeno_base_url
        or getattr(settings, "PAYZENO_BASE_URL", "https://api.payzeno.io"),
        "timeout": getattr(settings, "PAYZENO_TIMEOUT_SECONDS", 20),
    }


def payzeno_is_ready() -> bool:
    configuration = payzeno_configuration()
    return bool(
        configuration["enabled"]
        and configuration["api_key"]
        and configuration["webhook_secret"]
    )


def payzeno_client() -> PayzenoClient:
    configuration = payzeno_configuration()
    if not configuration["enabled"]:
        raise PayzenoConfigurationError("Os pagamentos Payzeno ainda não estão activos.")
    return PayzenoClient(
        api_key=configuration["api_key"],
        base_url=configuration["base_url"],
        timeout=configuration["timeout"],
    )


def amount_in_minor_units(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _safe_provider_payload(data: dict) -> dict:
    allowed = {
        "checkout_id", "payment_id", "reference", "amount", "currency",
        "status", "payment_method", "expires_at", "paid_at",
    }
    return {key: data[key] for key in allowed if key in data and data[key] is not None}


def initiate_payzeno_checkout(
    *, wedding, plan: Plan, actor, payer_phone: str, method: str,
    success_url: str, cancel_url: str, request=None,
) -> Payment:
    """Cria (ou reutiliza) um checkout mobile money alojado pela Payzeno."""
    if plan.is_free:
        raise ValidationError(_("O plano gratuito não precisa de pagamento."))
    if plan.max_guests <= limits(wedding).max_guests:
        raise ValidationError(_("Escolha um pacote superior ao pacote actual."))
    if method not in {PaymentMethod.MPESA, PaymentMethod.EMOLA}:
        raise ValidationError(_("Escolha M-Pesa ou e-Mola."))
    if not payer_phone.startswith("+"):
        raise ValidationError(_("Indique o número no formato +258 84 000 0000."))

    client = payzeno_client()
    payment = Payment.objects.filter(
        wedding=wedding,
        plan=plan,
        provider=PaymentProvider.PAYZENO,
        method=method,
        payer_phone=payer_phone,
        status=PaymentStatus.PENDING_GATEWAY,
    ).order_by("-created_at").first()
    if payment and payment.provider_checkout_url and (
        not payment.provider_expires_at or payment.provider_expires_at > timezone.now()
    ):
        return payment

    if payment is None:
        payment = Payment.objects.create(
            wedding=wedding,
            plan=plan,
            requested_by=actor,
            amount_mzn=plan.price_mzn,
            method=method,
            payer_phone=payer_phone,
            provider=PaymentProvider.PAYZENO,
            status=PaymentStatus.PENDING_GATEWAY,
        )
    else:
        payment.payer_phone = payer_phone
        payment.save(update_fields=["payer_phone", "updated_at"])

    customer_name = actor.get_full_name() or actor.get_short_name()
    payload = {
        "amount": amount_in_minor_units(payment.amount_mzn),
        "currency": "MZN",
        "language": getattr(actor, "preferred_language", "pt") or "pt",
        "description": f"MeuConvite — {plan.name}",
        "reference": payment.reference,
        "customer": {
            "name": customer_name,
            "email": actor.email,
            "phone": payer_phone,
        },
        "payment_methods": [method],
        "success_url": success_url.replace("REFERENCE", payment.reference),
        "cancel_url": cancel_url.replace("REFERENCE", payment.reference),
    }
    response = response_data(
        client.create_checkout(
            payload, idempotency_key=f"meuconvite-checkout-{payment.pk}"
        )
    )
    checkout_id = str(response.get("checkout_id") or "").strip()
    checkout_url = str(response.get("checkout_url") or "").strip()
    parsed_checkout = urlparse(checkout_url)
    if (
        not checkout_id
        or parsed_checkout.scheme != "https"
        or parsed_checkout.hostname != "checkout.payzeno.io"
    ):
        raise PayzenoAPIError("A Payzeno não devolveu um checkout válido.")

    payment.provider_checkout_id = checkout_id
    payment.provider_checkout_url = checkout_url
    payment.provider_status = str(response.get("status") or "pending")[:40]
    payment.provider_payload = _safe_provider_payload(response)
    expires_at = parse_datetime(str(response.get("expires_at") or ""))
    payment.provider_expires_at = expires_at
    payment.provider_checked_at = timezone.now()
    payment.save(update_fields=[
        "provider_checkout_id", "provider_checkout_url", "provider_status",
        "provider_payload", "provider_expires_at", "provider_checked_at", "updated_at",
    ])
    log_action(
        action=AuditAction.CREATE, actor=actor, wedding=wedding, request=request,
        instance=payment,
        new_data={
            "provider": PaymentProvider.PAYZENO,
            "plan": plan.code,
            "amount": str(plan.price_mzn),
            "reference": payment.reference,
        },
    )
    return payment


def verify_payzeno_payment(*, payment: Payment, request=None) -> tuple[Payment, bool]:
    """Consulta a Payzeno e activa apenas um pagamento integralmente coerente."""
    if payment.provider != PaymentProvider.PAYZENO:
        raise ValidationError(_("Este pagamento não pertence à Payzeno."))
    data = response_data(payzeno_client().checkout_status(payment.provider_checkout_id))
    status = str(data.get("status") or "").lower()

    payment.provider_status = status[:40]
    payment.provider_payment_id = str(data.get("payment_id") or "")[:100]
    payment.provider_checked_at = timezone.now()
    payment.provider_payload = _safe_provider_payload(data)
    payment.save(update_fields=[
        "provider_status", "provider_payment_id", "provider_checked_at",
        "provider_payload", "updated_at",
    ])

    if status in {"paid", "succeeded"}:
        expected = {
            "checkout_id": payment.provider_checkout_id,
            "reference": payment.reference,
            "amount": amount_in_minor_units(payment.amount_mzn),
            "currency": "MZN",
            "payment_method": payment.method,
        }
        received = {
            "checkout_id": str(data.get("checkout_id") or ""),
            "reference": str(data.get("reference") or ""),
            "amount": data.get("amount"),
            "currency": str(data.get("currency") or "").upper(),
            "payment_method": str(data.get("payment_method") or "").lower(),
        }
        try:
            received["amount"] = int(received["amount"])
        except (TypeError, ValueError):
            received["amount"] = None
        if received != expected:
            raise PayzenoAPIError(
                "A confirmação da Payzeno não corresponde ao pedido criado."
            )
        payment.method = received["payment_method"]
        if payment.provider_payment_id:
            payment.transaction_id = payment.provider_payment_id
        payment.save(update_fields=["method", "transaction_id", "updated_at"])
        confirm_payment(
            payment=payment, actor=None, request=request,
            notes="Confirmado automaticamente pela Payzeno.",
        )
        return Payment.objects.get(pk=payment.pk), True

    mapped = {
        "expired": PaymentStatus.EXPIRED,
        "cancelled": PaymentStatus.CANCELLED,
        "refunded": PaymentStatus.REFUNDED,
        "chargeback": PaymentStatus.CHARGEBACK,
    }.get(status)
    if mapped and (
        payment.status != PaymentStatus.CONFIRMED
        or mapped in {PaymentStatus.REFUNDED, PaymentStatus.CHARGEBACK}
    ):
        payment.status = mapped
        payment.save(update_fields=["status", "updated_at"])
    return payment, False


def whatsapp_url(payment: Payment) -> str:
    """Ligação que abre o WhatsApp com a mensagem do comprovativo pronta."""
    from urllib.parse import quote

    from platform_admin.models import configured_value

    number = configured_value("whatsapp_number").lstrip("+")
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
        paid_to=payment_instructions()["mpesa_number"],
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
    payment = Payment.objects.select_for_update().select_related(
        "wedding__subscription", "plan"
    ).get(pk=payment.pk)
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
            "sms_allowance": plan.max_sms,
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
