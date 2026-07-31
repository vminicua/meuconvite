from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from audit.models import AuditAction, AuditLog
from weddings import services
from weddings.models import WeddingMember, WeddingRole, WeddingStatus

from .factories import create_event, create_location, create_user, create_wedding


class CreateWeddingTests(TestCase):
    def test_creates_wedding_and_owner_membership(self) -> None:
        owner = create_user()
        wedding = services.create_wedding(
            owner=owner,
            data={
                "primary_name": "Natércia Alice Matola",
                "secondary_name": "Hivaldo José Cossa",
                "primary_short_name": "Natércia",
                "secondary_short_name": "Hivaldo",
                "main_date": timezone.localdate() + timedelta(days=90),
                "city": "Maputo",
                "country": "Moçambique",
            },
        )

        self.assertEqual(wedding.owner, owner)
        self.assertEqual(wedding.status, WeddingStatus.DRAFT)
        membership = WeddingMember.objects.get(wedding=wedding, user=owner)
        self.assertEqual(membership.role, WeddingRole.OWNER)
        self.assertIsNotNone(membership.accepted_at)

    def test_creation_is_recorded_in_the_audit_trail(self) -> None:
        owner = create_user()
        wedding = services.create_wedding(
            owner=owner,
            data={
                "primary_name": "Natércia Alice Matola",
                "secondary_name": "Hivaldo José Cossa",
                "primary_short_name": "Natércia",
                "secondary_short_name": "Hivaldo",
                "main_date": timezone.localdate() + timedelta(days=90),
                "city": "Maputo",
                "country": "Moçambique",
            },
        )
        log = AuditLog.objects.get(action=AuditAction.CREATE, object_id=str(wedding.pk))
        self.assertEqual(log.wedding_id, wedding.pk)
        self.assertEqual(log.user_id, owner.pk)


class PublishWeddingTests(TestCase):
    def setUp(self) -> None:
        self.wedding = create_wedding()

    def test_cannot_publish_without_events_and_locations(self) -> None:
        with self.assertRaises(ValidationError):
            services.publish_wedding(wedding=self.wedding, actor=self.wedding.owner)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, WeddingStatus.DRAFT)

    def test_publishes_once_the_required_items_are_done(self) -> None:
        location = create_location(self.wedding)
        create_event(self.wedding, location=location)

        services.publish_wedding(wedding=self.wedding, actor=self.wedding.owner)

        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, WeddingStatus.PUBLISHED)
        self.assertIsNotNone(self.wedding.published_at)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.PUBLISH, object_id=str(self.wedding.pk)
            ).exists()
        )

    def test_checklist_reports_what_is_missing(self) -> None:
        codes = {item.code for item in services.missing_requirements(self.wedding)}
        self.assertEqual(codes, {"events", "locations"})

    def test_unpublish_returns_to_draft(self) -> None:
        create_event(self.wedding, location=create_location(self.wedding))
        services.publish_wedding(wedding=self.wedding, actor=self.wedding.owner)
        services.unpublish_wedding(wedding=self.wedding, actor=self.wedding.owner)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, WeddingStatus.DRAFT)

    def test_archiving_keeps_all_data(self) -> None:
        create_event(self.wedding, location=create_location(self.wedding))
        services.archive_wedding(wedding=self.wedding, actor=self.wedding.owner)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, WeddingStatus.ARCHIVED)
        self.assertEqual(self.wedding.events.count(), 1)
        self.assertEqual(self.wedding.locations.count(), 1)


class TeamServiceTests(TestCase):
    def setUp(self) -> None:
        self.wedding = create_wedding()
        self.helper = create_user("comissao@example.com")

    def test_add_member_applies_role_defaults(self) -> None:
        membership = services.add_member(
            wedding=self.wedding,
            user=self.helper,
            role=WeddingRole.COMMITTEE,
            actor=self.wedding.owner,
        )
        self.assertTrue(membership.can_manage_guests)
        self.assertFalse(membership.can_manage_billing)

    def test_add_member_accepts_explicit_overrides(self) -> None:
        membership = services.add_member(
            wedding=self.wedding,
            user=self.helper,
            role=WeddingRole.COMMITTEE,
            permissions={"can_manage_guests": False},
            actor=self.wedding.owner,
        )
        self.assertFalse(membership.can_manage_guests)

    def test_owner_cannot_be_added_twice(self) -> None:
        with self.assertRaises(ValidationError):
            services.add_member(
                wedding=self.wedding,
                user=self.wedding.owner,
                role=WeddingRole.SPOUSE,
                actor=self.wedding.owner,
            )

    def test_deactivating_a_member_revokes_access_without_deleting(self) -> None:
        membership = services.add_member(
            wedding=self.wedding,
            user=self.helper,
            role=WeddingRole.COMMITTEE,
            actor=self.wedding.owner,
        )
        services.deactivate_member(membership=membership, actor=self.wedding.owner)
        membership.refresh_from_db()
        self.assertFalse(membership.is_active)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditAction.MEMBER_REMOVED).exists()
        )
