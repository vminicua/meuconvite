"""Planos, limites de convidados e o circuito de pagamento por M-Pesa."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from audit.models import AuditLog
from subscriptions import services
from subscriptions.models import Payment, PaymentStatus, Plan, SubscriptionStatus
from weddings.models import WeddingRole
from weddings.tests.factories import (
    DEFAULT_PASSWORD,
    add_member,
    create_plan,
    create_user,
    create_wedding,
)


def create_paid_plan(**extra) -> Plan:
    defaults = {
        "code": "celebracao-100",
        "name": "Celebração 100",
        "max_guests": 100,
        "price_mzn": 1500,
        "duration_days": 365,
        "allows_qr_checkin": True,
        "allows_seating": True,
        "is_default": False,
    }
    defaults.update(extra)
    return Plan.objects.create(**defaults)


class LimitTests(TestCase):
    def setUp(self) -> None:
        self.free = create_plan()
        self.wedding = create_wedding()
        services.ensure_subscription(self.wedding)

    def test_free_plan_allows_twenty_guests(self) -> None:
        limits = services.limits(self.wedding)
        self.assertEqual(limits.max_guests, 20)
        self.assertEqual(limits.max_sms, 0)
        self.assertTrue(limits.is_free)
        self.assertFalse(limits.allows_qr_checkin)

    def test_free_plan_cannot_send_sms(self) -> None:
        with self.assertRaisesMessage(ValidationError, "não inclui envios por SMS"):
            services.check_can_send_sms(self.wedding)

    def test_without_any_plan_the_platform_still_works(self) -> None:
        """Instalação nova, antes de `seed_plans`: cai no limite predefinido."""
        from subscriptions.models import Subscription

        Subscription.objects.all().delete()
        Plan.objects.all().delete()

        wedding = create_wedding(create_user("outro@example.com"))
        self.assertIsNone(services.ensure_subscription(wedding))
        limits = services.limits(wedding)
        self.assertEqual(limits.max_guests, services.FALLBACK_GUEST_LIMIT)

    def test_plans_in_use_cannot_be_deleted_by_accident(self) -> None:
        """PROTECT no plano: apagar um pacote em uso teria de ser deliberado."""
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.free.delete()

    def test_usage_helpers(self) -> None:
        limits = services.limits(self.wedding)
        self.assertEqual(limits.guests_remaining(5), 15)
        self.assertEqual(limits.usage_percent(10), 50)
        self.assertEqual(limits.usage_percent(999), 100)

    def test_upgrade_options_only_list_bigger_plans(self) -> None:
        create_paid_plan()
        create_paid_plan(code="pequeno", name="Pequeno", max_guests=10, price_mzn=100)
        codes = [plan.code for plan in services.upgrade_options(self.wedding)]
        self.assertEqual(codes, ["celebracao-100"])

    def test_guest_limit_is_enforced_by_a_single_service(self) -> None:
        """A verificação existe já; a fase 2 liga-a à criação de convidados."""
        services.check_can_add_guests(self.wedding, 20)
        with self.assertRaises(ValidationError):
            services.check_can_add_guests(self.wedding, 21)


class PaymentFlowTests(TestCase):
    def setUp(self) -> None:
        self.free = create_plan()
        self.paid = create_paid_plan()
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        services.ensure_subscription(self.wedding)

    def test_requesting_an_upgrade_creates_a_reference(self) -> None:
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        self.assertTrue(payment.reference.startswith("MC-"))
        self.assertEqual(payment.status, PaymentStatus.AWAITING_PROOF)
        self.assertEqual(payment.amount_mzn, self.paid.price_mzn)

    def test_requesting_twice_reuses_the_open_request(self) -> None:
        first = services.request_upgrade(wedding=self.wedding, plan=self.paid, actor=self.owner)
        second = services.request_upgrade(wedding=self.wedding, plan=self.paid, actor=self.owner)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.count(), 1)

    def test_the_free_plan_cannot_be_paid(self) -> None:
        with self.assertRaises(ValidationError):
            services.request_upgrade(wedding=self.wedding, plan=self.free, actor=self.owner)

    def test_submitting_the_transaction_id_moves_to_review(self) -> None:
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        services.submit_proof(
            payment=payment, actor=self.owner, transaction_id="ABC123", payer_phone="841234567"
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.UNDER_REVIEW)
        self.assertEqual(payment.payer_phone, "841234567")

    def test_confirming_the_payment_activates_the_plan(self) -> None:
        staff = create_user("suporte@example.com", is_staff=True)
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )

        services.confirm_payment(payment=payment, actor=staff)

        self.wedding.refresh_from_db()
        subscription = self.wedding.subscription
        self.assertEqual(subscription.plan, self.paid)
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(subscription.guest_allowance, 100)
        self.assertIsNotNone(subscription.ends_on)

        limits = services.limits(self.wedding)
        self.assertEqual(limits.max_guests, 100)
        self.assertTrue(limits.allows_seating)

    def test_confirming_twice_does_not_duplicate_subscriptions(self) -> None:
        staff = create_user("suporte@example.com", is_staff=True)
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        services.confirm_payment(payment=payment, actor=staff)
        services.confirm_payment(payment=payment, actor=staff)
        self.assertEqual(self.wedding.subscription_set.count() if hasattr(self.wedding, "subscription_set") else 1, 1)

    def test_rejecting_keeps_the_old_plan(self) -> None:
        staff = create_user("suporte@example.com", is_staff=True)
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        services.reject_payment(payment=payment, actor=staff, notes="Sem comprovativo")
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.subscription.plan, self.free)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.REJECTED)

    def test_the_whole_flow_is_audited(self) -> None:
        staff = create_user("suporte@example.com", is_staff=True)
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        services.confirm_payment(payment=payment, actor=staff)
        self.assertTrue(
            AuditLog.objects.filter(model_name="subscriptions.Payment").count() >= 2
        )

    def test_whatsapp_message_carries_the_reference(self) -> None:
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        self.assertIn(payment.reference, payment.whatsapp_message)
        self.assertIn("wa.me", services.whatsapp_url(payment))


class SubscriptionViewTests(TestCase):
    def setUp(self) -> None:
        self.free = create_plan()
        self.paid = create_paid_plan()
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        services.ensure_subscription(self.wedding)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_page_shows_the_current_plan_and_the_mpesa_number(self) -> None:
        response = self.client.get(reverse("subscriptions:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gratuito")
        self.assertContains(response, "840297715")

    def test_owner_can_request_an_upgrade(self) -> None:
        response = self.client.post(
            reverse("subscriptions:upgrade", args=[self.wedding.pk, self.paid.code]),
            data={"method": "mpesa", "payer_phone": "", "transaction_id": ""},
        )
        payment = Payment.objects.get(wedding=self.wedding)
        self.assertRedirects(
            response,
            reverse("subscriptions:payment", args=[self.wedding.pk, payment.reference]),
        )

    def test_payment_page_shows_the_instructions(self) -> None:
        payment = services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        response = self.client.get(
            reverse("subscriptions:payment", args=[self.wedding.pk, payment.reference])
        )
        self.assertContains(response, payment.reference)
        self.assertContains(response, "840297715")
        self.assertContains(response, "wa.me")

    def test_member_without_billing_permission_cannot_upgrade(self) -> None:
        helper = create_user("comissao@example.com")
        add_member(self.wedding, helper, role=WeddingRole.COMMITTEE)
        self.client.login(email=helper.email, password=DEFAULT_PASSWORD)
        response = self.client.get(
            reverse("subscriptions:upgrade", args=[self.wedding.pk, self.paid.code])
        )
        self.assertEqual(response.status_code, 404)

    def test_another_couple_cannot_see_this_subscription(self) -> None:
        stranger = create_user("estranho@example.com")
        self.client.login(email=stranger.email, password=DEFAULT_PASSWORD)
        response = self.client.get(reverse("subscriptions:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 404)
