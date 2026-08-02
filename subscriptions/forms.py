from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapForm
from core.utils import normalise_phone

from .models import PaymentMethod


class PayzenoCheckoutForm(BootstrapForm):
    payer_phone = forms.CharField(
        label=_("Número M-Pesa"),
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "+258 84 000 0000", "inputmode": "tel",
            "autocomplete": "tel",
        }),
        help_text=_("A Payzeno usará este número para concluir o pagamento M-Pesa."),
    )

    def clean_payer_phone(self) -> str:
        phone = normalise_phone(self.cleaned_data.get("payer_phone"))
        if not phone.startswith("+258") or len("".join(filter(str.isdigit, phone))) != 12:
            raise forms.ValidationError(_("Introduza um número moçambicano válido."))
        return phone


class UpgradeRequestForm(BootstrapForm):
    """
    Pedido de subscrição de um pacote.

    Tudo é opcional excepto o método: quem ainda não pagou avança só com o
    pedido e recebe as instruções; quem já pagou pode indicar logo o ID da
    transacção do M-Pesa, o que acelera a verificação.
    """

    method = forms.ChoiceField(
        label=_("Como vai pagar"),
        choices=PaymentMethod.choices,
        initial=PaymentMethod.MPESA,
    )
    payer_phone = forms.CharField(
        label=_("Número de quem paga"),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "+258 84 000 0000", "inputmode": "tel"}),
        help_text=_("Ajuda-nos a encontrar o seu pagamento mais depressa."),
    )
    transaction_id = forms.CharField(
        label=_("ID da transacção"),
        max_length=60,
        required=False,
        help_text=_("O código que o M-Pesa envia por SMS. Pode preencher depois."),
    )
    proof = forms.FileField(
        label=_("Comprovativo"),
        required=False,
        help_text=_("Opcional — também pode enviar por WhatsApp."),
    )

    def clean_payer_phone(self) -> str:
        return normalise_phone(self.cleaned_data.get("payer_phone"))

    def clean_proof(self):
        proof = self.cleaned_data.get("proof")
        if not proof:
            return proof
        if proof.size > 5 * 1024 * 1024:
            raise forms.ValidationError(_("O ficheiro é demasiado grande (máximo 5 MB)."))
        name = (proof.name or "").lower()
        allowed = (".jpg", ".jpeg", ".png", ".webp", ".pdf")
        if not name.endswith(allowed):
            raise forms.ValidationError(
                _("Envie uma imagem (JPG, PNG, WEBP) ou um PDF.")
            )
        return proof


class VoucherApplyForm(BootstrapForm):
    code = forms.CharField(
        label=_("Código do voucher"), max_length=40,
        widget=forms.TextInput(attrs={
            "placeholder": _("Ex.: CELEBRAR100"),
            "autocomplete": "off",
            "style": "text-transform:uppercase",
        }),
    )

    def clean_code(self) -> str:
        return (self.cleaned_data.get("code") or "").strip().upper()
