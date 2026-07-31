from __future__ import annotations

from datetime import time

from django.test import TestCase
from django.urls import reverse

from events.models import EventType, ScheduleItem, WeddingEvent, WeddingLocation
from weddings.tests.factories import (
    DEFAULT_PASSWORD,
    create_event,
    create_location,
    create_schedule_item,
    create_user,
    create_wedding,
)


class EventModelTests(TestCase):
    def setUp(self) -> None:
        self.wedding = create_wedding()

    def test_event_inherits_the_main_wedding_date(self) -> None:
        event = WeddingEvent.objects.create(wedding=self.wedding, name="Lobolo")
        self.assertEqual(event.date, self.wedding.main_date)

    def test_traditional_events_are_ordinary_independent_events(self) -> None:
        lobolo = create_event(
            self.wedding,
            name="Lobolo",
            event_type=EventType.LOBOLO,
            host_family="Família Matola",
            requires_rsvp=True,
        )
        xiguiane = create_event(
            self.wedding,
            name="Xiguiane",
            event_type=EventType.XIGUIANE,
            show_to_all_guests=False,
        )
        self.assertEqual(lobolo.host_family, "Família Matola")
        self.assertFalse(xiguiane.show_to_all_guests)
        self.assertEqual(WeddingEvent.objects.for_wedding(self.wedding).count(), 2)

    def test_two_events_cannot_share_a_name_in_the_same_wedding(self) -> None:
        from django.db import IntegrityError, transaction

        create_event(self.wedding, name="Recepção")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WeddingEvent.objects.create(wedding=self.wedding, name="Recepção")

    def test_the_same_name_is_fine_in_a_different_wedding(self) -> None:
        other = create_wedding(create_user("outra@example.com"))
        create_event(self.wedding, name="Recepção")
        create_event(other, name="Recepção")
        self.assertEqual(WeddingEvent.objects.filter(name="Recepção").count(), 2)

    def test_map_url_falls_back_to_the_location(self) -> None:
        location = create_location(
            self.wedding, map_url="https://maps.example.com/igreja"
        )
        event = create_event(self.wedding, location=location)
        self.assertEqual(event.effective_map_url, "https://maps.example.com/igreja")

    def test_time_range_display(self) -> None:
        event = create_event(self.wedding, start_time=time(9, 0), end_time=time(11, 30))
        self.assertEqual(event.time_range_display, "09:00 — 11:30")


class EventViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def _payload(self, **overrides) -> dict:
        data = {
            "event_type": EventType.RELIGIOUS,
            "name": "Cerimónia Religiosa",
            "description": "",
            "date": self.wedding.main_date.isoformat(),
            "start_time": "09:00",
            "end_time": "11:00",
            "location": "",
            "map_url": "",
            "host_family": "",
            "dress_code": "",
            "instructions": "",
            "requires_rsvp": "on",
            "show_to_all_guests": "on",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_create_event(self) -> None:
        response = self.client.post(
            reverse("events:create", args=[self.wedding.pk]), data=self._payload()
        )
        self.assertRedirects(response, reverse("events:list", args=[self.wedding.pk]))
        self.assertTrue(WeddingEvent.objects.filter(wedding=self.wedding).exists())

    def test_dress_code_is_an_optional_dropdown(self) -> None:
        response = self.client.get(reverse("events:create", args=[self.wedding.pk]))
        self.assertContains(response, '<select name="dress_code"', html=False)
        self.assertContains(response, "— Não especificar —")
        self.assertContains(response, "Traje formal")

        self.client.post(
            reverse("events:create", args=[self.wedding.pk]),
            data=self._payload(dress_code="Traje tradicional"),
        )
        event = WeddingEvent.objects.get(wedding=self.wedding)
        self.assertEqual(event.dress_code, "Traje tradicional")

    def test_end_time_before_start_time_is_rejected(self) -> None:
        response = self.client.post(
            reverse("events:create", args=[self.wedding.pk]),
            data=self._payload(start_time="15:00", end_time="09:00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "posterior à hora de início")
        self.assertFalse(WeddingEvent.objects.exists())

    def test_duplicate_name_is_rejected_with_a_message(self) -> None:
        create_event(self.wedding, name="Cerimónia Religiosa")
        response = self.client.post(
            reverse("events:create", args=[self.wedding.pk]), data=self._payload()
        )
        self.assertContains(response, "Já existe um evento com este nome")

    def test_delete_event(self) -> None:
        event = create_event(self.wedding)
        self.client.post(reverse("events:delete", args=[self.wedding.pk, event.pk]))
        self.assertFalse(WeddingEvent.objects.filter(pk=event.pk).exists())


class LocationViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_create_location(self) -> None:
        response = self.client.post(
            reverse("events:location_create", args=[self.wedding.pk]),
            data={
                "name": "Igreja de São José",
                "address": "Av. Julius Nyerere, Maputo",
                "description": "",
                "map_url": "",
                "latitude": "",
                "longitude": "",
                "contact_phone": "+258841234567",
                "parking_information": "",
                "transport_information": "",
            },
        )
        self.assertRedirects(
            response, reverse("events:location_list", args=[self.wedding.pk])
        )
        location = WeddingLocation.objects.get(wedding=self.wedding)
        self.assertIn("google.com/maps", location.directions_url)

    def test_deleting_a_location_keeps_the_events(self) -> None:
        location = create_location(self.wedding)
        event = create_event(self.wedding, location=location)
        self.client.post(
            reverse("events:location_delete", args=[self.wedding.pk, location.pk])
        )
        event.refresh_from_db()
        self.assertIsNone(event.location_id)


class ScheduleViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_create_schedule_item(self) -> None:
        response = self.client.post(
            reverse("events:schedule_create", args=[self.wedding.pk]),
            data={
                "title": "Cerimónia Religiosa",
                "description": "",
                "date": self.wedding.main_date.isoformat(),
                "start_time": "09:00",
                "end_time": "",
                "event": "",
                "location": "",
                "icon": "",
                "is_public": "on",
            },
        )
        self.assertRedirects(response, reverse("events:schedule", args=[self.wedding.pk]))
        item = ScheduleItem.objects.get(wedding=self.wedding)
        self.assertEqual(item.time_display, "09h00")

    def test_reorder_persists_the_new_order(self) -> None:
        first = create_schedule_item(self.wedding, title="Cerimónia Religiosa")
        second = create_schedule_item(self.wedding, title="Copo de Água")

        response = self.client.post(
            reverse("events:schedule_reorder", args=[self.wedding.pk]),
            data={"order": [str(second.pk), str(first.pk)]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertLess(second.display_order, first.display_order)

    def test_reorder_rejects_malformed_payloads(self) -> None:
        response = self.client.post(
            reverse("events:schedule_reorder", args=[self.wedding.pk]),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
