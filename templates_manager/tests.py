"""Catálogo de templates e página do convite."""

from __future__ import annotations

from io import BytesIO
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from templates_manager import registry, services
from templates_manager.models import InvitationLayout, InvitationTemplate
from weddings.tests.factories import (
    DEFAULT_PASSWORD,
    create_category,
    create_location,
    create_schedule_item,
    create_user,
    create_wedding,
)


class CatalogueTests(TestCase):
    """O catálogo é semeado pela migração de dados."""

    def test_the_two_featured_templates_exist(self) -> None:
        featured = InvitationTemplate.objects.featured().order_by("display_order")
        codes = [template.code for template in featured]
        self.assertEqual(codes, ["carta-selada", "envelope-botanico"])

    def test_each_featured_template_has_its_own_layout(self) -> None:
        layouts = set(
            InvitationTemplate.objects.featured().values_list("layout", flat=True)
        )
        self.assertEqual(
            layouts, {InvitationLayout.SEALED_LETTER, InvitationLayout.BOTANICAL}
        )

    def test_palettes_are_also_available(self) -> None:
        self.assertGreaterEqual(InvitationTemplate.objects.active().count(), 10)

    def test_unknown_code_falls_back_to_the_default(self) -> None:
        self.assertEqual(registry.get_template("nao-existe").code, "carta-selada")

    def test_is_valid_code(self) -> None:
        self.assertTrue(registry.is_valid_code("envelope-botanico"))
        self.assertFalse(registry.is_valid_code("pirata"))

    def test_templates_can_be_restricted_to_a_category(self) -> None:
        wedding_category = create_category()
        birthday = create_category(
            code="aniversario", name="Aniversário", uses_two_names=False, secondary_label=""
        )
        exclusive = InvitationTemplate.objects.create(
            code="so-casamento", name="Só casamento", layout=InvitationLayout.CLASSIC_CARD
        )
        exclusive.categories.add(wedding_category)

        for_wedding = registry.all_templates(wedding_category)
        for_birthday = registry.all_templates(birthday)
        self.assertIn(exclusive, for_wedding)
        self.assertNotIn(exclusive, for_birthday)

    def test_fonts_url_is_built_from_the_families(self) -> None:
        template = registry.get_template("carta-selada")
        self.assertIn("fonts.googleapis.com", template.fonts_url)
        self.assertIn("family=Playfair+Display", template.fonts_url)

    def test_event_colours_win_over_the_template_palette(self) -> None:
        template = registry.get_template("carta-selada")
        variables = template.css_variables("#123456", "#654321")
        self.assertIn("--inv-primary: #123456", variables)
        self.assertIn("--inv-secondary: #654321", variables)


class InvitationContextTests(TestCase):
    def setUp(self) -> None:
        self.wedding = create_wedding(category=create_category())
        create_schedule_item(self.wedding, title="Corte do bolo")
        create_location(self.wedding)

    def test_context_has_everything_the_layout_needs(self) -> None:
        template = registry.get_template("carta-selada")
        context = services.invitation_context(
            self.wedding, template, guest_name="Élio Nhaca", seats=2, is_preview=True
        )
        self.assertEqual(context["guest_name"], "Élio Nhaca")
        self.assertEqual(context["seats"], 2)
        self.assertEqual(len(context["schedule"]), 1)
        self.assertEqual(len(context["locations"]), 1)
        self.assertIsNotNone(context["countdown_target"])
        self.assertIn("--inv-primary", context["css_variables"])

    def test_monogram_uses_both_initials(self) -> None:
        context = services.invitation_context(
            self.wedding, registry.get_template("carta-selada")
        )
        self.assertEqual(context["monogram"], "NH")

    def test_private_schedule_items_stay_out_of_the_invitation(self) -> None:
        create_schedule_item(self.wedding, title="Reunião da comissão", is_public=False)
        context = services.invitation_context(
            self.wedding, registry.get_template("carta-selada")
        )
        titles = [item.title for item in context["schedule"]]
        self.assertNotIn("Reunião da comissão", titles)

    def test_branding_is_shown_on_the_free_plan(self) -> None:
        context = services.invitation_context(
            self.wedding, registry.get_template("carta-selada")
        )
        self.assertTrue(context["show_branding"])


class InvitationPreviewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner, category=create_category())
        create_schedule_item(self.wedding, title="Corte do bolo")
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_preview_uses_the_event_template(self) -> None:
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "inv--carta_selada")
        self.assertContains(response, self.wedding.primary_short_name)

    def test_preview_can_show_another_template(self) -> None:
        response = self.client.get(
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "envelope-botanico"],
            )
        )
        self.assertContains(response, "inv--envelope_botanico")

    def test_preview_shows_the_schedule_and_a_demo_guest(self) -> None:
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk])
        )
        self.assertContains(response, "Corte do bolo")
        self.assertContains(response, services.DEMO_GUEST_NAME)

    def test_rsvp_is_disabled_in_the_preview(self) -> None:
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk])
        )
        self.assertContains(response, "inv-btn--disabled")

    def test_another_user_cannot_preview_this_invitation(self) -> None:
        stranger = create_user("estranho@example.com")
        self.client.login(email=stranger.email, password=DEFAULT_PASSWORD)
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_every_layout_renders(self) -> None:
        """Cada layout tem de desenhar sem erros com os dados reais."""
        for template in InvitationTemplate.objects.active():
            with self.subTest(template=template.code):
                response = self.client.get(
                    reverse(
                        "weddings:invitation_preview_template",
                        args=[self.wedding.pk, template.code],
                    )
                )
                self.assertEqual(response.status_code, 200)


class TemplateAdminTests(TestCase):
    def setUp(self) -> None:
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.media_settings = self.settings(MEDIA_ROOT=self.media.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.staff = create_user("suporte@example.com", is_staff=True)
        self.client.login(email=self.staff.email, password=DEFAULT_PASSWORD)

    def test_list_shows_the_catalogue(self) -> None:
        response = self.client.get(reverse("platform:templates"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carta Selada")

    def test_creating_a_template(self) -> None:
        response = self.client.post(
            reverse("platform:template_create"),
            data={
                "name": "Dourado Suave",
                "code": "dourado-suave",
                "description": "Teste",
                "layout": InvitationLayout.CLASSIC_CARD,
                "primary": "#C8A96A",
                "secondary": "#1F2933",
                "paper": "#FFFDF8",
                "ink": "#3A3226",
                "display_font": '"Great Vibes", cursive',
                "body_font": '"Cormorant Garamond", Georgia, serif',
                "google_fonts": "Great+Vibes",
                "tags": "dourado",
                "display_order": 200,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("platform:templates"))
        self.assertTrue(InvitationTemplate.objects.filter(code="dourado-suave").exists())

    def test_an_invalid_colour_is_rejected(self) -> None:
        response = self.client.post(
            reverse("platform:template_create"),
            data={
                "name": "Errado",
                "code": "errado",
                "layout": InvitationLayout.CLASSIC_CARD,
                "primary": "vermelho",
                "secondary": "#1F2933",
                "paper": "#FFFFFF",
                "ink": "#000000",
                "display_font": "serif",
                "body_font": "serif",
                "display_order": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InvitationTemplate.objects.filter(code="errado").exists())

    def test_a_client_cannot_manage_templates(self) -> None:
        client_user = create_user("cliente@example.com")
        self.client.login(email=client_user.email, password=DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse("platform:templates")).status_code, 302)

    def test_staff_can_define_an_image_cover(self) -> None:
        image_bytes = BytesIO()
        Image.new("RGB", (8, 10), "#C8A96A").save(image_bytes, format="PNG")
        cover = SimpleUploadedFile(
            "cover.png", image_bytes.getvalue(), content_type="image/png"
        )
        response = self.client.post(
            reverse("platform:template_create"),
            data={
                "name": "Com Cover",
                "code": "com-cover",
                "description": "Template com imagem de catálogo",
                "layout": InvitationLayout.CLASSIC_CARD,
                "primary": "#C8A96A",
                "secondary": "#1F2933",
                "paper": "#FFFDF8",
                "ink": "#3A3226",
                "display_font": "serif",
                "body_font": "serif",
                "cover_image": cover,
                "display_order": 210,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("platform:templates"))
        template = InvitationTemplate.objects.get(code="com-cover")
        self.assertTrue(template.cover_image.name.startswith("templates/covers/"))
