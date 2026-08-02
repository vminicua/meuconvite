"""Área de administração da plataforma."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from events.models import EventCategory
from subscriptions import services as subscription_services
from subscriptions.models import PaymentStatus, Plan, Voucher
from subscriptions.tests import create_paid_plan
from weddings.models import WeddingStatus
from weddings.tests.factories import (
    DEFAULT_PASSWORD,
    create_category,
    create_plan,
    create_user,
    create_wedding,
)
from .models import PlatformConfiguration

HTMX = {"HTTP_HX_REQUEST": "true"}


class AccessTests(TestCase):
    """Só a equipa MeuConvite entra."""

    def setUp(self) -> None:
        self.client_user = create_user("cliente@example.com")
        self.staff = create_user("suporte@example.com", is_staff=True)

    def test_anonymous_is_redirected(self) -> None:
        response = self.client.get(reverse("platform:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_ordinary_client_cannot_enter_any_section(self) -> None:
        self.client.login(email=self.client_user.email, password=DEFAULT_PASSWORD)
        for name in ("dashboard", "events", "users", "payments", "plans", "categories", "audit", "settings"):
            with self.subTest(section=name):
                self.assertEqual(self.client.get(reverse(f"platform:{name}")).status_code, 302)

    def test_staff_sees_every_section(self) -> None:
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)
        for name in ("dashboard", "events", "users", "payments", "plans", "categories", "audit", "settings"):
            with self.subTest(section=name):
                self.assertEqual(self.client.get(reverse(f"platform:{name}")).status_code, 200)

    def test_menu_entry_is_only_shown_to_staff(self) -> None:
        create_plan()
        self.client.login(email=self.client_user.email, password=DEFAULT_PASSWORD)
        self.assertNotContains(self.client.get(reverse("weddings:list")), "Administração")

        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)
        self.assertContains(self.client.get(reverse("weddings:list")), "Administração")


class LayoutTests(TestCase):
    """Casca completa no primeiro pedido, só a secção no HTMX."""

    def setUp(self) -> None:
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_full_page_includes_the_sidebar(self) -> None:
        response = self.client.get(reverse("platform:dashboard"))
        self.assertContains(response, "admin-sidebar")
        self.assertContains(response, "Visão geral")

    def test_htmx_request_returns_only_the_section(self) -> None:
        response = self.client.get(reverse("platform:events"), **HTMX)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "admin-sidebar")
        self.assertContains(response, 'data-section-title="Eventos"')


class ConfigurationTests(TestCase):
    def setUp(self) -> None:
        self.staff = create_user("config@example.com", is_staff=True)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_twilio_configuration_is_encrypted_and_reopens_masked(self) -> None:
        response = self.client.post(
            reverse("platform:settings"),
            {
                "twilio_account_sid": "AC123456",
                "twilio_api_key_sid": "SK123456",
                "twilio_api_key_secret": "api-secret-value",
                "twilio_auth_token": "auth-token-value",
                "twilio_sms_from": "+12025550123",
                "twilio_status_callback_url": "https://example.com/twilio/status/",
                "mpesa_number": "840000000",
                "mpesa_account_name": "MeuConvite",
                "whatsapp_number": "+258840000000",
            },
        )
        self.assertRedirects(response, reverse("platform:settings"))
        configuration = PlatformConfiguration.load()
        self.assertEqual(configuration.get_secret("twilio_api_key_secret"), "api-secret-value")
        self.assertNotIn("api-secret-value", configuration.twilio_api_key_secret_secret)
        self.assertContains(self.client.get(reverse("platform:settings")), "Configurado")


class DashboardTests(TestCase):
    def setUp(self) -> None:
        create_plan()
        self.paid = create_paid_plan()
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.owner = create_user("noiva@example.com")
        self.wedding = create_wedding(self.owner, category=create_category())
        subscription_services.ensure_subscription(self.wedding)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_kpis_are_calculated(self) -> None:
        response = self.client.get(reverse("platform:dashboard"))
        kpis = response.context["kpis"]
        self.assertEqual(kpis["events"]["total"], 1)
        self.assertEqual(kpis["users"]["total"], 2)
        self.assertEqual(kpis["payments"]["pending"], 0)

    def test_charts_receive_json(self) -> None:
        response = self.client.get(reverse("platform:dashboard"))
        self.assertIn("labels", response.context["chart_events"])
        self.assertIn("labels", response.context["chart_categories"])

    def test_pending_payment_appears(self) -> None:
        subscription_services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        response = self.client.get(reverse("platform:dashboard"))
        self.assertEqual(response.context["kpis"]["payments"]["pending"], 1)


class EventSectionTests(TestCase):
    def setUp(self) -> None:
        create_plan()
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.owner = create_user("noiva@example.com")
        self.category = create_category()
        self.wedding = create_wedding(self.owner, category=self.category)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_list_shows_the_event(self) -> None:
        response = self.client.get(reverse("platform:events"))
        # `display_names` traz "&", que sai escapado no HTML.
        self.assertContains(response, self.wedding.primary_short_name)
        self.assertContains(response, self.wedding.slug)

    def test_filter_by_status(self) -> None:
        response = self.client.get(reverse("platform:events"), {"estado": "published"})
        self.assertNotContains(response, self.wedding.slug)

    def test_search_by_owner_email(self) -> None:
        response = self.client.get(reverse("platform:events"), {"q": "noiva@example.com"})
        self.assertContains(response, self.wedding.slug)

    def test_detail_shows_subscription_and_audit(self) -> None:
        response = self.client.get(reverse("platform:event_detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Momentos")

    def test_blocking_requires_a_reason(self) -> None:
        self.client.post(
            reverse("platform:event_block", args=[self.wedding.pk]), data={"reason": ""}
        )
        self.wedding.refresh_from_db()
        self.assertNotEqual(self.wedding.status, WeddingStatus.BLOCKED)

    def test_blocking_and_unblocking(self) -> None:
        self.client.post(
            reverse("platform:event_block", args=[self.wedding.pk]),
            data={"reason": "Conteúdo denunciado"},
        )
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, WeddingStatus.BLOCKED)
        self.assertEqual(self.wedding.blocked_reason, "Conteúdo denunciado")

        self.client.post(reverse("platform:event_block", args=[self.wedding.pk]))
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, WeddingStatus.DRAFT)
        self.assertEqual(self.wedding.blocked_reason, "")

    def test_a_blocked_event_is_hidden_from_its_owner(self) -> None:
        self.client.post(
            reverse("platform:event_block", args=[self.wedding.pk]),
            data={"reason": "Conteúdo denunciado"},
        )
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)
        response = self.client.get(reverse("weddings:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 404)


class UserSectionTests(TestCase):
    def setUp(self) -> None:
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.person = create_user("cliente@example.com")
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_list_and_filters(self) -> None:
        response = self.client.get(reverse("platform:users"), {"filtro": "staff"})
        self.assertContains(response, self.staff.email)
        self.assertNotContains(response, self.person.email)

    def test_deactivating_a_user(self) -> None:
        self.client.post(
            reverse("platform:user_toggle", args=[self.person.pk]), data={"campo": "is_active"}
        )
        self.person.refresh_from_db()
        self.assertFalse(self.person.is_active)

    def test_granting_staff_access(self) -> None:
        self.client.post(
            reverse("platform:user_toggle", args=[self.person.pk]), data={"campo": "is_staff"}
        )
        self.person.refresh_from_db()
        self.assertTrue(self.person.is_staff)

    def test_cannot_change_own_permissions(self) -> None:
        self.client.post(
            reverse("platform:user_toggle", args=[self.staff.pk]), data={"campo": "is_staff"}
        )
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_staff)

    def test_unknown_field_is_rejected(self) -> None:
        self.client.post(
            reverse("platform:user_toggle", args=[self.person.pk]),
            data={"campo": "is_superuser"},
        )
        self.person.refresh_from_db()
        self.assertFalse(self.person.is_superuser)


class PaymentReviewTests(TestCase):
    def setUp(self) -> None:
        create_plan()
        self.paid = create_paid_plan()
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.owner = create_user("noiva@example.com")
        self.wedding = create_wedding(self.owner)
        subscription_services.ensure_subscription(self.wedding)
        self.payment = subscription_services.request_upgrade(
            wedding=self.wedding, plan=self.paid, actor=self.owner
        )
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)
        self.url = reverse("platform:payment_review", args=[self.payment.reference])

    def test_confirming_activates_the_plan(self) -> None:
        self.client.post(self.url, data={"decisao": "confirmar", "notas": "Visto no M-Pesa"})
        self.payment.refresh_from_db()
        self.wedding.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.CONFIRMED)
        self.assertEqual(self.wedding.subscription.plan, self.paid)
        self.assertEqual(subscription_services.limits(self.wedding).max_guests, 100)

    def test_rejecting_requires_a_reason(self) -> None:
        self.client.post(self.url, data={"decisao": "recusar", "notas": ""})
        self.payment.refresh_from_db()
        self.assertNotEqual(self.payment.status, PaymentStatus.REJECTED)

    def test_client_cannot_confirm(self) -> None:
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)
        self.client.post(self.url, data={"decisao": "confirmar"})
        self.payment.refresh_from_db()
        self.assertNotEqual(self.payment.status, PaymentStatus.CONFIRMED)


class PlanManagementTests(TestCase):
    def setUp(self) -> None:
        self.free = create_plan()
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def _payload(self, **overrides) -> dict:
        data = {
            "name": "Premium 300",
            "code": "premium-300",
            "description": "Até 300 convidados",
            "max_guests": 300,
            "max_events": 5,
            "templates_limit": 0,
            "price_mzn": "3000",
            "duration_days": 365,
            "display_order": 60,
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_creating_a_plan(self) -> None:
        response = self.client.post(reverse("platform:plan_create"), data=self._payload())
        self.assertRedirects(response, reverse("platform:plans"))
        self.assertTrue(Plan.objects.filter(code="premium-300").exists())

    def test_a_paid_plan_cannot_be_the_default_one(self) -> None:
        response = self.client.post(
            reverse("platform:plan_create"), data=self._payload(is_default="on")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tem de ser gratuito")

    def test_editing_a_plan(self) -> None:
        self.client.post(
            reverse("platform:plan_edit", args=[self.free.pk]),
            data=self._payload(
                name="Gratuito", code="gratuito", max_guests=25, price_mzn="0", duration_days=0
            ),
        )
        self.free.refresh_from_db()
        self.assertEqual(self.free.max_guests, 25)


class VoucherManagementTests(TestCase):
    def setUp(self) -> None:
        self.staff = create_user("vouchers@example.com", is_staff=True)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_staff_can_create_a_voucher(self) -> None:
        response = self.client.post(reverse("platform:voucher_create"), data={
            "name": "Casamento 120", "code": "casamento120", "max_guests": 120,
            "sms_enabled": "on", "max_sms": 40, "max_redemptions": 5,
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("platform:vouchers"))
        voucher = Voucher.objects.get()
        self.assertEqual(voucher.code, "CASAMENTO120")
        self.assertEqual(voucher.max_sms, 40)


class CategoryManagementTests(TestCase):
    def setUp(self) -> None:
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.category = create_category()
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def _payload(self, **overrides) -> dict:
        data = {
            "name": "Casamento",
            "code": "casamento",
            "description": "Cerimónias e recepção",
            "icon": "bi-suit-heart",
            "uses_two_names": "on",
            "primary_label": "Nome da noiva",
            "secondary_label": "Nome do noivo",
            "names_separator": "&",
            "invitation_greeting": "têm o prazer de o convidar",
            "default_moments": '[{"name": "Recepção", "start_time": "19:30"}]',
            "default_schedule": '[{"title": "Corte do bolo", "start_time": "18:30"}]',
            "display_order": 10,
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_editing_a_category(self) -> None:
        self.client.post(
            reverse("platform:category_edit", args=[self.category.pk]), data=self._payload()
        )
        self.category.refresh_from_db()
        self.assertEqual(len(self.category.default_moments), 1)
        self.assertEqual(self.category.default_moments[0]["name"], "Recepção")

    def test_invalid_json_is_reported(self) -> None:
        response = self.client.post(
            reverse("platform:category_edit", args=[self.category.pk]),
            data=self._payload(default_moments="isto não é json"),
        )
        self.assertEqual(response.status_code, 200)
        # O JSONField do Django rejeita primeiro, com a sua própria mensagem.
        self.assertContains(response, "JSON")
        self.category.refresh_from_db()
        self.assertEqual(self.category.default_moments, [])

    def test_moments_need_a_name(self) -> None:
        response = self.client.post(
            reverse("platform:category_edit", args=[self.category.pk]),
            data=self._payload(default_moments='[{"start_time": "19:30"}]'),
        )
        self.assertContains(response, "precisa de «name»")

    def test_adding_and_removing_a_custom_field(self) -> None:
        self.client.post(
            reverse("platform:category_field_add", args=[self.category.pk]),
            data={"label": "Traje dos convidados", "type": "text"},
        )
        self.category.refresh_from_db()
        self.assertEqual(
            [field["key"] for field in self.category.extra_fields], ["traje_dos_convidados"]
        )

        self.client.post(
            reverse(
                "platform:category_field_remove",
                args=[self.category.pk, "traje_dos_convidados"],
            )
        )
        self.category.refresh_from_db()
        self.assertEqual(self.category.extra_fields, [])

    def test_duplicate_custom_field_is_rejected(self) -> None:
        for _ in range(2):
            self.client.post(
                reverse("platform:category_field_add", args=[self.category.pk]),
                data={"label": "Traje", "type": "text"},
            )
        self.category.refresh_from_db()
        self.assertEqual(len(self.category.extra_fields), 1)

    def test_creating_a_new_category(self) -> None:
        self.client.post(
            reverse("platform:category_create"),
            data=self._payload(name="Jantar de gala", code="jantar-de-gala"),
        )
        self.assertTrue(EventCategory.objects.filter(code="jantar-de-gala").exists())


class AuditSectionTests(TestCase):
    def setUp(self) -> None:
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_login_appears_in_the_audit_section(self) -> None:
        response = self.client.get(reverse("platform:audit"))
        self.assertContains(response, "Início de sessão")

    def test_filter_by_action(self) -> None:
        response = self.client.get(reverse("platform:audit"), {"accao": "checkin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["entries"]), 0)
