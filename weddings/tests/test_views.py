from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from templates_manager.models import InvitationTemplate
from weddings.models import Wedding, WeddingMember, WeddingRole

from .factories import (
    DEFAULT_PASSWORD,
    add_member,
    create_category,
    create_event,
    create_location,
    create_plan,
    create_user,
    create_wedding,
)


class EventCreationViewTests(TestCase):
    """Criar um evento: escolher o tipo e preencher o mínimo."""

    def setUp(self) -> None:
        self.user = create_user()
        self.client.login(email=self.user.email, password=DEFAULT_PASSWORD)
        self.plan = create_plan()
        self.category = create_category(
            default_moments=[{"name": "Recepção", "event_type": "reception", "start_time": "19:30"}],
            default_schedule=[{"title": "Corte do bolo", "start_time": "18:30", "icon": "bi-cake2"}],
        )
        self.birthday = create_category(
            code="aniversario",
            name="Aniversário",
            uses_two_names=False,
            primary_label="Nome do aniversariante",
            secondary_label="",
            field_schema=[{"key": "idade", "label": "Idade a celebrar", "type": "number"}],
        )
        self.url = reverse("weddings:create")
        self.template = InvitationTemplate.objects.filter(is_active=True).first()

    def _payload(self, **overrides) -> dict:
        data = {
            "category": self.category.code,
            "template": self.template.code,
            "primary_name": "Ivone Alice Sitoe",
            "secondary_name": "Dário José Machava",
            "main_date": (timezone.localdate() + timedelta(days=100)).isoformat(),
            "city": "Maputo",
        }
        data.update(overrides)
        return data

    def _form_url(self, category: str = "", template: str = "") -> str:
        return (
            f"{self.url}?tipo={category or self.category.code}"
            f"&template={template or self.template.code}"
        )

    def test_without_a_type_the_choices_are_shown(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Que tipo de evento")
        self.assertContains(response, "Aniversário")

    def test_unknown_type_falls_back_to_the_choices(self) -> None:
        response = self.client.get(self.url, {"tipo": "nao-existe"})
        self.assertContains(response, "Que tipo de evento")

    def test_choosing_a_type_asks_for_the_template(self) -> None:
        response = self.client.get(self.url, {"tipo": self.category.code})
        self.assertContains(response, "Escolha o convite")
        self.assertContains(response, self.template.name)

    def test_the_form_uses_the_labels_of_the_chosen_type(self) -> None:
        response = self.client.get(self._form_url(category="aniversario"))
        self.assertContains(response, "Nome do aniversariante")
        self.assertContains(response, "Idade a celebrar")
        # Um só protagonista: o segundo nome não é pedido.
        self.assertNotContains(response, 'name="secondary_name"')

    def test_creates_the_event_and_goes_to_the_dashboard(self) -> None:
        response = self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertRedirects(response, reverse("weddings:detail", args=[wedding.pk]))
        self.assertEqual(wedding.category, self.category)

    def test_short_names_are_derived_from_the_full_names(self) -> None:
        self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(wedding.primary_short_name, "Ivone")
        self.assertEqual(wedding.secondary_short_name, "Dário")
        self.assertEqual(wedding.display_names, "Ivone & Dário")

    def test_category_defaults_are_applied(self) -> None:
        """O evento não nasce vazio: momentos e programa já vêm sugeridos."""
        from events.models import ScheduleItem, WeddingEvent

        self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(WeddingEvent.objects.filter(wedding=wedding).count(), 1)
        self.assertEqual(ScheduleItem.objects.filter(wedding=wedding).count(), 1)

    def test_a_free_subscription_is_created(self) -> None:
        self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(wedding.subscription.plan, self.plan)
        self.assertEqual(wedding.subscription.guest_allowance, 20)

    def test_extra_fields_of_the_type_are_saved(self) -> None:
        self.client.post(
            self._form_url(category="aniversario"),
            data={
                "category": "aniversario",
                "template": self.template.code,
                "primary_name": "Amélia Nhaca",
                "main_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
                "city": "Beira",
                "extra__idade": "40",
            },
        )
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(wedding.extra_data.get("idade"), "40")
        self.assertEqual(wedding.display_names, "Amélia")

    def test_rejects_a_date_in_the_past(self) -> None:
        response = self.client.post(
            self._form_url(),
            data=self._payload(main_date=(timezone.localdate() - timedelta(days=1)).isoformat()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Wedding.objects.exists())

    def test_the_second_name_is_required_for_two_name_types(self) -> None:
        response = self.client.post(self._form_url(), data=self._payload(secondary_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Wedding.objects.exists())


class DashboardViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_dashboard_shows_the_checklist(self) -> None:
        response = self.client.get(reverse("weddings:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O que falta")
        self.assertEqual(len(response.context["checklist"]), 8)

    def test_setup_progress_grows_with_completed_items(self) -> None:
        before = self.client.get(reverse("weddings:setup", args=[self.wedding.pk]))
        create_event(self.wedding, location=create_location(self.wedding))
        after = self.client.get(reverse("weddings:setup", args=[self.wedding.pk]))
        self.assertGreater(after.context["progress"], before.context["progress"])
        self.assertTrue(after.context["can_publish"])

    def test_publish_flow_reports_missing_requirements(self) -> None:
        response = self.client.post(
            reverse("weddings:publish", args=[self.wedding.pk]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, "draft")
        self.assertContains(response, "Falta completar")

    def test_wedding_list_only_shows_accessible_weddings(self) -> None:
        other = create_wedding(create_user("outra@example.com"))
        response = self.client.get(reverse("weddings:list"))
        weddings = list(response.context["weddings"])
        self.assertIn(self.wedding, weddings)
        self.assertNotIn(other, weddings)


class DesignViewTests(TestCase):
    """Galeria de templates de convite."""

    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)
        self.url = reverse("weddings:design", args=[self.wedding.pk])

    def test_gallery_lists_every_template(self) -> None:
        from templates_manager import registry

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["templates"]), len(registry.all_templates()))
        self.assertGreaterEqual(len(registry.all_templates()), 10)
        for template in registry.all_templates():
            self.assertContains(response, template.name)

    def _payload(self, **overrides) -> dict:
        data = {
            "selected_template": "capulana",
            "primary_color": "#C1502E",
            "secondary_color": "#1B6B5A",
        }
        data.update(overrides)
        return data

    def test_choosing_a_template_is_saved(self) -> None:
        response = self.client.post(self.url, data=self._payload())
        self.assertRedirects(response, self.url)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.selected_template, "capulana")
        self.assertEqual(self.wedding.primary_color, "#C1502E")

    def test_unknown_template_code_is_rejected(self) -> None:
        response = self.client.post(self.url, data=self._payload(selected_template="pirata"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escolha um dos templates disponíveis")
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.selected_template, "carta-selada")

    def test_member_without_design_permission_cannot_open_it(self) -> None:
        other = create_user("comissao@example.com")
        add_member(self.wedding, other, role=WeddingRole.RECEPTIONIST)
        self.client.login(email=other.email, password=DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class TeamViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.helper = create_user("comissao@example.com")
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_owner_adds_a_member_by_email(self) -> None:
        response = self.client.post(
            reverse("weddings:team", args=[self.wedding.pk]),
            data={"email": self.helper.email, "role": WeddingRole.COMMITTEE, "notes": ""},
        )
        self.assertRedirects(response, reverse("weddings:team", args=[self.wedding.pk]))
        self.assertTrue(
            WeddingMember.objects.filter(wedding=self.wedding, user=self.helper).exists()
        )

    def test_unknown_email_is_rejected_with_a_clear_message(self) -> None:
        response = self.client.post(
            reverse("weddings:team", args=[self.wedding.pk]),
            data={"email": "ninguem@example.com", "role": WeddingRole.COMMITTEE},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não existe nenhuma conta com este email")

    def test_owner_membership_cannot_be_removed(self) -> None:
        membership = WeddingMember.objects.get(wedding=self.wedding, user=self.owner)
        self.client.post(
            reverse("weddings:team_remove", args=[self.wedding.pk, membership.pk])
        )
        membership.refresh_from_db()
        self.assertTrue(membership.is_active)

    def test_permissions_can_be_narrowed_for_a_member(self) -> None:
        membership = add_member(self.wedding, self.helper, role=WeddingRole.COMMITTEE)
        self.client.post(
            reverse("weddings:team_edit", args=[self.wedding.pk, membership.pk]),
            data={
                "role": WeddingRole.VIEWER,
                "can_view_reports": "on",
                "notes": "Apenas consulta",
            },
        )
        membership.refresh_from_db()
        self.assertEqual(membership.role, WeddingRole.VIEWER)
        self.assertFalse(membership.can_manage_guests)
        self.assertTrue(membership.can_view_reports)
