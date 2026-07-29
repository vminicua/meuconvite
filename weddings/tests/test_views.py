from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from weddings.models import Wedding, WeddingMember, WeddingRole

from .factories import (
    DEFAULT_PASSWORD,
    add_member,
    create_event,
    create_location,
    create_user,
    create_wedding,
)


class WeddingCreationViewTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user()
        self.client.login(email=self.user.email, password=DEFAULT_PASSWORD)

    def _payload(self, **overrides) -> dict:
        data = {
            "bride_full_name": "Natércia Alice Matola",
            "groom_full_name": "Hivaldo José Cossa",
            "bride_short_name": "Natércia",
            "groom_short_name": "Hivaldo",
            "main_date": (timezone.localdate() + timedelta(days=100)).isoformat(),
            "city": "Maputo",
            "country": "Moçambique",
        }
        data.update(overrides)
        return data

    def test_creates_wedding_and_redirects_to_events(self) -> None:
        response = self.client.post(reverse("weddings:create"), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertRedirects(response, reverse("events:list", args=[wedding.pk]))

    def test_rejects_a_date_in_the_past(self) -> None:
        response = self.client.post(
            reverse("weddings:create"),
            data=self._payload(main_date=(timezone.localdate() - timedelta(days=1)).isoformat()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Wedding.objects.exists())

    def test_short_names_are_derived_when_left_empty(self) -> None:
        self.client.post(
            reverse("weddings:create"),
            data=self._payload(bride_short_name="", groom_short_name=""),
        )
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(wedding.bride_short_name, "Natércia")
        self.assertEqual(wedding.groom_short_name, "Hivaldo")


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
