from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from weddings.models import Wedding, WeddingMember, WeddingRole

from .factories import add_member, create_user, create_wedding


class WeddingModelTests(TestCase):
    def test_slug_is_generated_from_the_couple_names(self) -> None:
        wedding = create_wedding()
        self.assertEqual(wedding.slug, "natercia-e-hivaldo")

    def test_slug_stays_unique_between_weddings(self) -> None:
        first = create_wedding(create_user("one@example.com"))
        second = create_wedding(create_user("two@example.com"))
        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith("natercia-e-hivaldo-"))

    def test_public_token_is_generated_and_unique(self) -> None:
        first = create_wedding(create_user("one@example.com"))
        second = create_wedding(create_user("two@example.com"))
        self.assertTrue(len(first.public_token) >= 32)
        self.assertNotEqual(first.public_token, second.public_token)

    def test_days_until_counts_from_today(self) -> None:
        wedding = create_wedding(main_date=timezone.localdate() + timedelta(days=10))
        self.assertEqual(wedding.days_until, 10)

    def test_rsvp_closes_after_the_deadline(self) -> None:
        wedding = create_wedding(
            status="published",
            rsvp_deadline=timezone.localdate() - timedelta(days=1),
        )
        self.assertFalse(wedding.rsvp_is_open)

    def test_public_url_uses_the_slug(self) -> None:
        wedding = create_wedding()
        self.assertTrue(wedding.get_public_url().endswith(f"/{wedding.slug}/"))

    def test_reserved_slug_is_rejected(self) -> None:
        wedding = create_wedding()
        wedding.slug = "admin"
        with self.assertRaises(ValidationError):
            wedding.full_clean()


class WeddingMemberModelTests(TestCase):
    def setUp(self) -> None:
        self.wedding = create_wedding()
        self.helper = create_user("comissao@example.com")

    def test_owner_membership_is_created_with_full_permissions(self) -> None:
        membership = WeddingMember.objects.get(
            wedding=self.wedding, user=self.wedding.owner
        )
        self.assertEqual(membership.role, WeddingRole.OWNER)
        self.assertTrue(membership.can_manage_guests)
        self.assertTrue(membership.can_manage_billing)

    def test_role_defaults_limit_a_receptionist(self) -> None:
        membership = add_member(self.wedding, self.helper, role=WeddingRole.RECEPTIONIST)
        self.assertTrue(membership.can_check_in)
        self.assertFalse(membership.can_manage_guests)
        self.assertFalse(membership.can_manage_billing)

    def test_a_user_can_only_be_added_once_per_wedding(self) -> None:
        add_member(self.wedding, self.helper)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WeddingMember.objects.create(wedding=self.wedding, user=self.helper)

    def test_the_same_user_can_help_in_several_weddings(self) -> None:
        other = create_wedding(create_user("outro@example.com"))
        add_member(self.wedding, self.helper)
        add_member(other, self.helper)
        self.assertEqual(
            WeddingMember.objects.filter(user=self.helper, is_active=True).count(), 2
        )
        self.assertCountEqual(
            Wedding.objects.for_user(self.helper), [self.wedding, other]
        )
