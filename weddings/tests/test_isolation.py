"""
Data isolation between weddings.

This is the most critical property of the platform: one couple must never
be able to read or change another couple's data, whatever URL they try.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from events.models import ScheduleItem, WeddingEvent
from weddings.models import Wedding

from .factories import (
    DEFAULT_PASSWORD,
    add_member,
    create_event,
    create_location,
    create_schedule_item,
    create_user,
    create_wedding,
)


class WeddingQuerySetIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner_a = create_user("a@example.com")
        cls.owner_b = create_user("b@example.com")
        cls.wedding_a = create_wedding(cls.owner_a, city="Maputo")
        cls.wedding_b = create_wedding(cls.owner_b, city="Beira")

    def test_for_user_only_returns_own_weddings(self) -> None:
        self.assertEqual(
            list(Wedding.objects.for_user(self.owner_a)), [self.wedding_a]
        )
        self.assertEqual(
            list(Wedding.objects.for_user(self.owner_b)), [self.wedding_b]
        )

    def test_for_user_includes_weddings_where_user_is_member(self) -> None:
        add_member(self.wedding_a, self.owner_b)
        self.assertCountEqual(
            Wedding.objects.for_user(self.owner_b), [self.wedding_a, self.wedding_b]
        )

    def test_inactive_membership_loses_access(self) -> None:
        membership = add_member(self.wedding_a, self.owner_b)
        membership.is_active = False
        membership.save()
        self.assertEqual(list(Wedding.objects.for_user(self.owner_b)), [self.wedding_b])

    def test_anonymous_user_sees_nothing(self) -> None:
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(list(Wedding.objects.for_user(AnonymousUser())), [])


class CrossWeddingAccessTests(TestCase):
    """Every wedding-scoped URL must answer 404 to an outsider."""

    def setUp(self) -> None:
        self.owner_a = create_user("a@example.com")
        self.owner_b = create_user("b@example.com")
        self.wedding_a = create_wedding(self.owner_a)
        self.wedding_b = create_wedding(self.owner_b)
        self.location_a = create_location(self.wedding_a)
        self.event_a = create_event(self.wedding_a, location=self.location_a)
        self.item_a = create_schedule_item(self.wedding_a)
        self.client.login(email="b@example.com", password=DEFAULT_PASSWORD)

    def test_outsider_cannot_open_dashboard(self) -> None:
        response = self.client.get(reverse("weddings:detail", args=[self.wedding_a.pk]))
        self.assertEqual(response.status_code, 404)

    def test_outsider_cannot_open_settings(self) -> None:
        response = self.client.get(reverse("weddings:settings", args=[self.wedding_a.pk]))
        self.assertEqual(response.status_code, 404)

    def test_outsider_cannot_list_events(self) -> None:
        response = self.client.get(reverse("events:list", args=[self.wedding_a.pk]))
        self.assertEqual(response.status_code, 404)

    def test_outsider_cannot_edit_event(self) -> None:
        response = self.client.get(
            reverse("events:edit", args=[self.wedding_a.pk, self.event_a.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_outsider_cannot_delete_event(self) -> None:
        response = self.client.post(
            reverse("events:delete", args=[self.wedding_a.pk, self.event_a.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WeddingEvent.objects.filter(pk=self.event_a.pk).exists())

    def test_outsider_cannot_publish(self) -> None:
        response = self.client.post(reverse("weddings:publish", args=[self.wedding_a.pk]))
        self.assertEqual(response.status_code, 404)
        self.wedding_a.refresh_from_db()
        self.assertEqual(self.wedding_a.status, "published")

    def test_outsider_cannot_archive(self) -> None:
        response = self.client.post(reverse("weddings:archive", args=[self.wedding_a.pk]))
        self.assertEqual(response.status_code, 404)

    def test_outsider_cannot_read_team(self) -> None:
        response = self.client.get(reverse("weddings:team", args=[self.wedding_a.pk]))
        self.assertEqual(response.status_code, 404)

    def test_event_id_from_another_wedding_is_not_reachable_through_own_wedding(self) -> None:
        """Mixing a foreign object id with an accessible wedding id fails."""
        response = self.client.get(
            reverse("events:edit", args=[self.wedding_b.pk, self.event_a.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_reorder_ignores_items_from_other_weddings(self) -> None:
        item_b = create_schedule_item(self.wedding_b, title="Recepção")
        original_order = self.item_a.display_order

        response = self.client.post(
            reverse("events:schedule_reorder", args=[self.wedding_b.pk]),
            data={"order": [str(self.item_a.pk), str(item_b.pk)]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.display_order, original_order)
        item_b.refresh_from_db()
        self.assertEqual(item_b.display_order, 20)

    def test_event_form_only_offers_locations_of_the_same_wedding(self) -> None:
        from events.forms import WeddingEventForm

        form = WeddingEventForm(wedding=self.wedding_b)
        self.assertEqual(list(form.fields["location"].queryset), [])

        form_a = WeddingEventForm(wedding=self.wedding_a)
        self.assertEqual(list(form_a.fields["location"].queryset), [self.location_a])


class AnonymousAccessTests(TestCase):
    def setUp(self) -> None:
        self.wedding = create_wedding()

    def test_dashboard_requires_login(self) -> None:
        response = self.client.get(reverse("weddings:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_wedding_list_requires_login(self) -> None:
        response = self.client.get(reverse("weddings:list"))
        self.assertEqual(response.status_code, 302)

    def test_schedule_items_are_not_exposed_anonymously(self) -> None:
        create_schedule_item(self.wedding)
        response = self.client.get(reverse("events:schedule", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ScheduleItem.objects.count(), 1)
