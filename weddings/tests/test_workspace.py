"""Grouped workspace navigation and the "próximos passos" guide."""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import resolve, reverse

from guests.models import DeliveryStatus, Guest, InvitationChannel, InvitationDelivery, RSVPStatus
from weddings.models import WeddingRole
from weddings.permissions import capability_flags
from weddings.workspace import build_next_steps, build_workspace_nav

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

TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00"
    b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def lock(wedding):
    from subscriptions.models import SubscriptionStatus
    from subscriptions.services import ensure_subscription

    subscription = ensure_subscription(wedding)
    subscription.status = SubscriptionStatus.PENDING
    subscription.save(update_fields=["status", "updated_at"])


def corporate_category():
    from events.models import EventCategory

    category = EventCategory.objects.filter(code="evento-corporativo").first()
    return category or create_category(code="evento-corporativo", name="Corporativo")


def codes(groups):
    return {group.code: [item.code for item in group.items] for group in groups}


class WorkspaceNavBuilderTests(TestCase):
    def setUp(self) -> None:
        create_plan()
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)

    def nav(self, user=None, url_name="weddings:preview", args=None):
        user = user or self.owner
        match = resolve(reverse(url_name, args=args or [self.wedding.pk]))
        return build_workspace_nav(self.wedding, capability_flags(self.wedding, user), match)

    def test_owner_sees_four_areas_with_all_sections(self) -> None:
        self.assertEqual(
            codes(self.nav()),
            {
                "invitation": ["preview", "design"],
                "info": ["details", "programme", "story", "gallery"],
                "guests": ["guests", "gifts"],
                "settings": ["subscription", "team"],
            },
        )

    def test_active_state_follows_namespace_and_url_name(self) -> None:
        cases = {
            "weddings:preview": ("invitation", "preview"),
            "weddings:design": ("invitation", "design"),
            "weddings:detail": ("info", "details"),
            "weddings:settings": ("info", "details"),
            "weddings:category": ("info", "details"),
            "weddings:story": ("info", "story"),
            "weddings:gallery": ("info", "gallery"),
            "events:organisation": ("info", "programme"),
            "events:list": ("info", "programme"),
            "guests:list": ("guests", "guests"),
            "guests:gifts": ("guests", "gifts"),
            "weddings:team": ("settings", "team"),
            "subscriptions:detail": ("settings", "subscription"),
        }
        for url_name, (group_code, item_code) in cases.items():
            with self.subTest(url_name=url_name):
                groups = self.nav(url_name=url_name)
                active_groups = [group.code for group in groups if group.active]
                active_items = [item.code for group in groups for item in group.items if item.active]
                self.assertEqual(active_groups, [group_code])
                self.assertEqual(active_items, [item_code])

    def test_corporate_events_hide_the_story(self) -> None:
        self.wedding.category = corporate_category()
        self.wedding.save()
        self.assertEqual(codes(self.nav())["info"], ["details", "programme", "gallery"])

    def test_member_without_design_or_guest_rights_sees_fewer_areas(self) -> None:
        member = create_user("comissao@example.com")
        add_member(self.wedding, member, role=WeddingRole.COMMITTEE,
                   can_manage_guests=False, can_manage_design=False, can_manage_billing=False)
        self.assertEqual(
            codes(self.nav(user=member)),
            {"invitation": ["preview"], "info": ["details", "programme", "story"]},
        )

    def test_locked_event_turns_links_into_upgrade_prompts(self) -> None:
        lock(self.wedding)
        groups = {group.code: group for group in self.nav()}
        upgrade_url = reverse("subscriptions:detail", args=[self.wedding.pk])
        preview = groups["invitation"].items[0]
        self.assertTrue(preview.locked)
        self.assertEqual(preview.upgrade_feature, "Convite")
        self.assertEqual(preview.upgrade_url, upgrade_url)
        subscription, team = groups["settings"].items
        self.assertTrue(team.locked)
        self.assertEqual(team.upgrade_url, "")
        self.assertFalse(subscription.locked)
        # The "Definições" area leads to what still works: the subscription.
        self.assertEqual(groups["settings"].entry.code, "subscription")


class WorkspaceNavRenderingTests(TestCase):
    def setUp(self) -> None:
        create_plan()
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_preview_renders_areas_and_invitation_subsections(self) -> None:
        response = self.client.get(reverse("weddings:preview", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for label in ("O convite", "Informações", "Convidados", "Definições"):
            self.assertIn(f'<span class="workspace-area__label">{label}</span>', content)
        self.assertEqual(content.count('class="workspace-area is-active"'), 1)
        self.assertIn('data-workspace-area="invitation"', content)
        self.assertIn('data-workspace-section="design"', content)
        # Only the active area shows its sub-sections.
        self.assertNotIn('data-workspace-section="programme"', content)
        self.assertIn(f'href="{reverse("weddings:design", args=[self.wedding.pk])}"', content)
        self.assertNotIn("data-upgrade-modal", content.split("workspace-nav", 1)[1].split("</nav>")[0])

    def test_programme_page_shows_information_subsections(self) -> None:
        response = self.client.get(reverse("events:organisation", args=[self.wedding.pk]))
        self.assertContains(response, 'data-workspace-section="details"')
        self.assertContains(response, 'data-workspace-section="story"')
        self.assertContains(
            response,
            'class="workspace-subnav__link is-active"\n                   aria-current="page" data-workspace-section="programme"',
            html=False,
        )

    def test_subscription_page_does_not_highlight_event_details(self) -> None:
        response = self.client.get(reverse("subscriptions:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-workspace-section="subscription"')
        self.assertNotContains(response, 'data-workspace-section="details"')

    def test_corporate_event_nav_has_no_story(self) -> None:
        self.wedding.category = corporate_category()
        self.wedding.save()
        response = self.client.get(reverse("weddings:detail", args=[self.wedding.pk]))
        self.assertNotContains(response, 'data-workspace-section="story"')
        self.assertContains(response, 'data-workspace-section="gallery"')

    def test_locked_event_nav_opens_upgrade_modal(self) -> None:
        lock(self.wedding)
        response = self.client.get(reverse("weddings:preview", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "weddings/event_locked.html")
        content = response.content.decode()
        nav = content.split('class="workspace-nav"', 1)[1].split("</nav>", 1)[0]
        self.assertIn('data-upgrade-modal data-upgrade-feature="Convite"', nav)
        self.assertIn('data-upgrade-modal data-upgrade-feature="Detalhes do evento"', nav)
        subscription_url = reverse("subscriptions:detail", args=[self.wedding.pk])
        self.assertIn(f'data-workspace-nav href="{subscription_url}"', nav)
        self.assertNotIn("next-steps", content)

        # On the subscription page the "Definições" sub-sections are shown:
        # the subscription stays usable and the team opens the upgrade modal.
        response = self.client.get(subscription_url)
        nav = response.content.decode().split('class="workspace-nav"', 1)[1].split("</nav>", 1)[0]
        self.assertIn('data-upgrade-modal data-upgrade-feature="Este evento" href=', nav)
        self.assertIn('data-workspace-section="subscription"', nav)


class NextStepsTests(TestCase):
    def setUp(self) -> None:
        create_plan()
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)

    def steps(self, user=None):
        user = user or self.owner
        return build_next_steps(self.wedding, capability_flags(self.wedding, user))

    def status(self, result):
        return {step.code: step.done for step in result.steps}

    def test_new_event_starts_with_details_done(self) -> None:
        result = self.steps()
        self.assertEqual(
            self.status(result),
            {"details": True, "programme": False, "photos": False, "guests": False, "sent": False},
        )
        self.assertEqual(result.done_count, 1)
        self.assertEqual(result.percent, 20)
        self.assertEqual(result.next_step.code, "programme")
        self.assertEqual(result.next_step.url, reverse("events:organisation", args=[self.wedding.pk]))

    def test_progress_follows_existing_data(self) -> None:
        create_event(self.wedding, location=create_location(self.wedding))
        self.wedding.cover_image = SimpleUploadedFile("capa.gif", TINY_GIF, content_type="image/gif")
        self.wedding.save()
        guest = Guest.objects.create(wedding=self.wedding, full_name="Ana Sitoe", phone="+258840000000")
        result = self.steps()
        self.assertEqual(result.next_step.code, "sent")
        self.assertEqual(result.next_step.action_label, "Enviar convites")
        self.assertEqual(result.guest_count, 1)

        InvitationDelivery.objects.create(
            wedding=self.wedding, guest=guest, channel=InvitationChannel.SMS,
            destination=guest.phone, message_body="Olá", status=DeliveryStatus.FAILED,
        )
        self.assertFalse(self.status(self.steps())["sent"])

        guest.rsvp_status = RSVPStatus.CONFIRMED
        guest.save()
        result = self.steps()
        self.assertTrue(result.complete)
        self.assertIsNone(result.next_step)
        self.assertEqual(result.confirmed_count, 1)

    def test_optional_photos_do_not_block_completion(self) -> None:
        create_event(self.wedding, location=create_location(self.wedding))
        guest = Guest.objects.create(wedding=self.wedding, full_name="Ana Sitoe")
        self.assertEqual(self.steps().next_step.code, "sent")
        guest.rsvp_status = RSVPStatus.DECLINED
        guest.save()
        result = self.steps()
        self.assertFalse(self.status(result)["photos"])
        self.assertTrue(result.complete)
        self.assertEqual(result.remaining, 0)
        self.assertEqual(result.next_step.code, "photos")

    def test_steps_without_permission_have_no_link(self) -> None:
        member = create_user("comissao@example.com")
        add_member(self.wedding, member, role=WeddingRole.COMMITTEE,
                   can_manage_guests=False, can_manage_events=False, can_manage_design=False)
        result = self.steps(member)
        self.assertEqual(result.next_step, None)
        self.assertEqual({s.code for s in result.steps if s.url}, {"details"})

    def test_preview_page_shows_primary_next_action(self) -> None:
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)
        create_event(self.wedding, location=create_location(self.wedding))
        response = self.client.get(reverse("weddings:preview", args=[self.wedding.pk]))
        self.assertContains(response, "data-next-steps")
        self.assertContains(response, "2 de 5 concluídos")
        self.assertContains(response, "Faltam 2 passos")
        # Photos are optional: the main button goes to the guests first.
        self.assertContains(
            response,
            f'<a class="btn btn-primary next-steps__cta" href="{reverse("guests:list", args=[self.wedding.pk])}" data-workspace-nav>',
            html=False,
        )
        self.assertContains(response, "Adicionar convidados")
        self.assertContains(response, '<span class="next-step__tag">opcional</span>', html=False)
        self.assertContains(response, "Personalizar aspecto")
