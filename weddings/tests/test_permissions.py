from __future__ import annotations

from django.http import Http404
from django.test import TestCase
from django.urls import reverse

from weddings.models import WeddingRole
from weddings.permissions import capability_flags, get_wedding_or_404, is_owner, user_can

from .factories import DEFAULT_PASSWORD, add_member, create_user, create_wedding


class CapabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = create_user("noiva@example.com")
        cls.planner = create_user("planner@example.com")
        cls.receptionist = create_user("recepcao@example.com")
        cls.stranger = create_user("estranho@example.com")
        cls.wedding = create_wedding(cls.owner)
        add_member(cls.wedding, cls.planner, role=WeddingRole.WEDDING_PLANNER)
        add_member(cls.wedding, cls.receptionist, role=WeddingRole.RECEPTIONIST)

    def test_owner_can_do_everything(self) -> None:
        self.assertTrue(is_owner(self.wedding, self.owner))
        for capability in ("can_manage_guests", "can_manage_events", "can_manage_billing"):
            self.assertTrue(user_can(self.wedding, self.owner, capability))

    def test_planner_manages_but_does_not_bill(self) -> None:
        self.assertTrue(user_can(self.wedding, self.planner, "can_manage_events"))
        self.assertFalse(user_can(self.wedding, self.planner, "can_manage_billing"))

    def test_receptionist_only_checks_in(self) -> None:
        self.assertTrue(user_can(self.wedding, self.receptionist, "can_check_in"))
        self.assertFalse(user_can(self.wedding, self.receptionist, "can_manage_events"))

    def test_stranger_has_no_capability(self) -> None:
        self.assertFalse(user_can(self.wedding, self.stranger, "can_view_reports"))

    def test_unknown_capability_is_a_programming_error(self) -> None:
        with self.assertRaises(ValueError):
            user_can(self.wedding, self.planner, "can_do_magic")

    def test_get_wedding_or_404_hides_weddings_from_strangers(self) -> None:
        with self.assertRaises(Http404):
            get_wedding_or_404(self.stranger, self.wedding.pk)

    def test_get_wedding_or_404_enforces_the_capability(self) -> None:
        with self.assertRaises(Http404):
            get_wedding_or_404(self.receptionist, self.wedding.pk, "can_manage_events")

    def test_capability_flags_for_template_usage(self) -> None:
        flags = capability_flags(self.wedding, self.receptionist)
        self.assertFalse(flags["is_owner"])
        self.assertTrue(flags["can_check_in"])
        self.assertFalse(flags["manage_members"])


class ViewLevelPermissionTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user("noiva@example.com")
        self.receptionist = create_user("recepcao@example.com")
        self.wedding = create_wedding(self.owner)
        add_member(self.wedding, self.receptionist, role=WeddingRole.RECEPTIONIST)
        self.client.login(email="recepcao@example.com", password=DEFAULT_PASSWORD)

    def test_member_without_permission_cannot_open_settings(self) -> None:
        response = self.client.get(reverse("weddings:settings", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 404)

    def test_member_without_permission_cannot_create_events(self) -> None:
        response = self.client.get(reverse("events:create", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 404)

    def test_member_can_still_read_the_dashboard(self) -> None:
        response = self.client.get(reverse("weddings:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)

    def test_member_cannot_manage_the_team(self) -> None:
        response = self.client.get(reverse("weddings:team", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 404)
