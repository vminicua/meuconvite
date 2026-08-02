"""Planos, subscrições e pagamentos."""

from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel
from core.utils import generate_short_code


class PlanQuerySet(models.QuerySet):
    def active(self) -> "PlanQuerySet":
        return self.filter(is_active=True)

    def paid(self) -> "PlanQuerySet":
        return self.active().filter(price_mzn__gt=0)


class Plan(BaseModel):
    """
    Um pacote comercial.

    Os limites são dados, não código: a equipa MeuConvite pode criar,
    alterar ou desactivar pacotes na administração sem alterações no
    software.
    """

    code = models.SlugField(_("código"), max_length=40, unique=True)
    name = models.CharField(_("nome"), max_length=80)
    description = models.CharField(_("descrição"), max_length=200, blank=True)

    max_guests = models.PositiveIntegerField(
        _("convidados incluídos"),
        help_text=_("Número máximo de convidados por evento."),
    )
    max_events = models.PositiveIntegerField(
        _("eventos incluídos"),
        default=1,
        help_text=_("Quantos eventos o utilizador pode ter em simultâneo."),
    )
    max_sms = models.PositiveIntegerField(
        _("SMS incluídos"),
        default=0,
        help_text=_("Número máximo de convites por SMS em cada evento."),
    )
    price_mzn = models.DecimalField(
        _("preço (MZN)"), max_digits=10, decimal_places=2, default=0
    )
    duration_days = models.PositiveIntegerField(
        _("duração (dias)"),
        default=365,
        help_text=_("Quanto tempo a subscrição fica activa depois de confirmada."),
    )

    # --- Funcionalidades incluídas ---
    allows_qr_checkin = models.BooleanField(_("check-in com QR Code"), default=False)
    allows_seating = models.BooleanField(_("gestão de mesas"), default=False)
    allows_team = models.BooleanField(_("equipa"), default=False)
    allows_exports = models.BooleanField(_("exportações"), default=False)
    removes_branding = models.BooleanField(_("sem marca MeuConvite"), default=False)
    templates_limit = models.PositiveIntegerField(
        _("templates disponíveis"),
        default=1,
        help_text=_("0 = todos os templates."),
    )

    is_active = models.BooleanField(_("activo"), default=True, db_index=True)
    is_default = models.BooleanField(
        _("plano inicial"),
        default=False,
        help_text=_("O plano atribuído automaticamente a cada evento novo."),
    )
    display_order = models.PositiveIntegerField(_("ordem"), default=0)

    objects = PlanQuerySet.as_manager()

    class Meta:
        verbose_name = _("plano")
        verbose_name_plural = _("planos")
        ordering = ["display_order", "max_guests"]

    def __str__(self) -> str:
        return f"{self.name} ({self.max_guests} convidados)"

    @property
    def is_free(self) -> bool:
        return self.price_mzn <= 0

    @property
    def price_display(self) -> str:
        if self.is_free:
            return str(_("Gratuito"))
        return f"{self.price_mzn:,.0f} MZN".replace(",", " ")


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", _("Activa")
    PENDING = "pending", _("À espera de confirmação de pagamento")
    EXPIRED = "expired", _("Expirada")
    CANCELLED = "cancelled", _("Cancelada")


class Subscription(BaseModel):
    """
    O plano em vigor num evento.

    Há sempre exactamente uma subscrição activa por evento: o plano
    gratuito é criado com o evento e é substituído quando um pagamento é
    confirmado.
    """

    wedding = models.OneToOneField(
        "weddings.Wedding",
        verbose_name=_("evento"),
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        Plan, verbose_name=_("plano"), on_delete=models.PROTECT, related_name="subscriptions"
    )
    status = models.CharField(
        _("estado"),
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
    )
    starts_on = models.DateField(_("início"), default=timezone.localdate)
    ends_on = models.DateField(_("fim"), null=True, blank=True)

    # Guardado no momento da activação: se o plano for alterado mais tarde,
    # quem já pagou mantém o que comprou.
    guest_allowance = models.PositiveIntegerField(_("convidados permitidos"))
    sms_allowance = models.PositiveIntegerField(
        _("SMS permitidos"),
        default=0,
        help_text=_("Limite guardado no momento em que a subscrição é activada."),
    )
    notes = models.CharField(_("notas"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("subscrição")
        verbose_name_plural = _("subscrições")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.wedding} — {self.plan.name}"

    @property
    def is_active(self) -> bool:
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        if self.ends_on and self.ends_on < timezone.localdate():
            return False
        return True

    @property
    def days_remaining(self) -> int | None:
        if not self.ends_on:
            return None
        return (self.ends_on - timezone.localdate()).days

    def expected_end(self, start: date | None = None) -> date | None:
        if not self.plan.duration_days:
            return None
        return (start or timezone.localdate()) + timedelta(days=self.plan.duration_days)


class Voucher(BaseModel):
    """Código promocional que concede limites a um único evento."""

    code = models.CharField(_("código"), max_length=40, unique=True, db_index=True)
    name = models.CharField(_("nome"), max_length=100)
    description = models.CharField(_("descrição"), max_length=240, blank=True)
    max_guests = models.PositiveIntegerField(_("limite de convidados"))
    sms_enabled = models.BooleanField(_("activar envio por SMS"), default=False)
    max_sms = models.PositiveIntegerField(_("limite de SMS"), default=0)
    valid_from = models.DateField(_("válido desde"), null=True, blank=True)
    valid_until = models.DateField(_("válido até"), null=True, blank=True)
    max_redemptions = models.PositiveIntegerField(
        _("número máximo de utilizações"), default=1,
        help_text=_("0 permite utilizações ilimitadas."),
    )
    is_active = models.BooleanField(_("activo"), default=True, db_index=True)

    class Meta:
        verbose_name = _("voucher")
        verbose_name_plural = _("vouchers")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def clean(self) -> None:
        super().clean()
        if self.sms_enabled and self.max_sms <= 0:
            raise ValidationError({"max_sms": _("Indique quantos SMS este voucher permite.")})
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": _("A data final não pode anteceder a inicial.")})

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        if not self.sms_enabled:
            self.max_sms = 0
        return super().save(*args, **kwargs)


class VoucherRedemption(BaseModel):
    """Utilização imutável de um voucher, com os benefícios em snapshot."""

    voucher = models.ForeignKey(
        Voucher, on_delete=models.PROTECT, related_name="redemptions", verbose_name=_("voucher")
    )
    wedding = models.OneToOneField(
        "weddings.Wedding", on_delete=models.CASCADE,
        related_name="voucher_redemption", verbose_name=_("evento"),
    )
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="voucher_redemptions", verbose_name=_("aplicado por"),
    )
    guest_allowance = models.PositiveIntegerField(_("convidados concedidos"))
    sms_allowance = models.PositiveIntegerField(_("SMS concedidos"), default=0)

    class Meta:
        verbose_name = _("utilização de voucher")
        verbose_name_plural = _("utilizações de vouchers")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.voucher.code} — {self.wedding}"


class PaymentMethod(models.TextChoices):
    MPESA = "mpesa", _("M-Pesa")
    EMOLA = "emola", _("e-Mola")
    BANK_TRANSFER = "bank_transfer", _("Transferência bancária")
    OTHER = "other", _("Outro")


class PaymentStatus(models.TextChoices):
    PENDING_GATEWAY = "pending_gateway", _("A aguardar pagamento")
    AWAITING_PROOF = "awaiting_proof", _("À espera do comprovativo")
    UNDER_REVIEW = "under_review", _("Em verificação")
    CONFIRMED = "confirmed", _("Confirmado")
    REJECTED = "rejected", _("Recusado")
    CANCELLED = "cancelled", _("Cancelado")
    EXPIRED = "expired", _("Expirado")
    REFUNDED = "refunded", _("Reembolsado")
    CHARGEBACK = "chargeback", _("Contestado")


class PaymentProvider(models.TextChoices):
    MANUAL = "manual", _("Manual")
    PAYZENO = "payzeno", _("Payzeno")


class Payment(BaseModel):
    """
    Um pedido de pagamento feito pelo utilizador.

    O utilizador escolhe o plano, a plataforma gera uma **referência**
    curta, ele paga por M-Pesa e envia o comprovativo por WhatsApp. A
    equipa confirma aqui e a subscrição é activada pelo serviço
    `subscriptions.services.confirm_payment`.
    """

    wedding = models.ForeignKey(
        "weddings.Wedding",
        verbose_name=_("evento"),
        on_delete=models.CASCADE,
        related_name="payments",
    )
    plan = models.ForeignKey(
        Plan, verbose_name=_("plano"), on_delete=models.PROTECT, related_name="payments"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("pedido por"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="payment_requests",
    )

    reference = models.CharField(
        _("referência"),
        max_length=20,
        unique=True,
        editable=False,
        help_text=_("Código que o utilizador indica ao enviar o comprovativo."),
    )
    method = models.CharField(
        _("método"), max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.MPESA
    )
    amount_mzn = models.DecimalField(_("montante (MZN)"), max_digits=10, decimal_places=2)
    paid_to = models.CharField(
        _("pago para"),
        max_length=40,
        blank=True,
        help_text=_("Número ou conta que recebeu o pagamento."),
    )
    payer_phone = models.CharField(_("telefone de quem pagou"), max_length=20, blank=True)
    transaction_id = models.CharField(
        _("ID da transacção"),
        max_length=60,
        blank=True,
        help_text=_("Código que o M-Pesa envia por SMS."),
    )
    proof = models.FileField(
        _("comprovativo"),
        upload_to="payments/%Y/%m/",
        blank=True,
        null=True,
        help_text=_("Opcional: o comprovativo também pode ser enviado por WhatsApp."),
    )
    provider = models.CharField(
        _("processador"), max_length=20, choices=PaymentProvider.choices,
        default=PaymentProvider.MANUAL, db_index=True,
    )
    provider_checkout_id = models.CharField(
        _("checkout do processador"), max_length=100, blank=True, null=True, unique=True
    )
    provider_payment_id = models.CharField(
        _("pagamento do processador"), max_length=100, blank=True, null=True, db_index=True
    )
    provider_status = models.CharField(_("estado no processador"), max_length=40, blank=True)
    provider_checkout_url = models.URLField(_("URL do checkout"), max_length=600, blank=True)
    provider_expires_at = models.DateTimeField(_("checkout expira em"), null=True, blank=True)
    provider_checked_at = models.DateTimeField(_("processador verificado em"), null=True, blank=True)
    provider_payload = models.JSONField(_("metadados do processador"), default=dict, blank=True)

    status = models.CharField(
        _("estado"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.AWAITING_PROOF,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("verificado por"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_reviewed",
    )
    reviewed_at = models.DateTimeField(_("verificado em"), null=True, blank=True)
    review_notes = models.CharField(_("notas da verificação"), max_length=300, blank=True)

    class Meta:
        verbose_name = _("pagamento")
        verbose_name_plural = _("pagamentos")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="payment_status_date_idx"),
            models.Index(fields=["wedding", "-created_at"], name="payment_wedding_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.plan.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        return super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference() -> str:
        """Referência curta, legível ao telefone, sem caracteres ambíguos."""
        for _attempt in range(10):
            candidate = f"MC-{generate_short_code(6)}"
            if not Payment.objects.filter(reference=candidate).exists():
                return candidate
        return f"MC-{generate_short_code(10)}"

    @property
    def is_open(self) -> bool:
        return self.status in {
            PaymentStatus.PENDING_GATEWAY,
            PaymentStatus.AWAITING_PROOF,
            PaymentStatus.UNDER_REVIEW,
        }

    @property
    def whatsapp_message(self) -> str:
        """Mensagem pré-preenchida para o utilizador enviar o comprovativo."""
        return (
            f"Olá! Enviei {self.amount_mzn:,.0f} MZN por {self.get_method_display()} "
            f"para o pacote {self.plan.name} do MeuConvite.\n"
            f"Referência: {self.reference}\n"
            f"Evento: {self.wedding.display_names}"
        ).replace(",", " ")


class PaymentWebhookEvent(BaseModel):
    """Registo idempotente e sem dados pessoais dos webhooks recebidos."""

    provider = models.CharField(max_length=20, default=PaymentProvider.PAYZENO)
    event_key = models.CharField(max_length=64, unique=True, editable=False)
    event_type = models.CharField(max_length=50, blank=True)
    checkout_id = models.CharField(max_length=100, blank=True, db_index=True)
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="webhook_events",
    )
    processed = models.BooleanField(default=False)
    processing_error = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-created_at"]
