"""Catálogo de templates e página do convite."""

from __future__ import annotations

from io import BytesIO
import tempfile
from urllib.parse import unquote

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from templates_manager import registry, services
from templates_manager.models import (
    InvitationLayout,
    InvitationTemplate,
    _contrast,
    _relative_luminance,
    readable_colour,
)
from weddings.tests.factories import (
    DEFAULT_PASSWORD,
    create_category,
    create_event,
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
        self.assertIn("family=Italianno", template.fonts_url)

    def test_each_template_has_curated_typography(self) -> None:
        expected_display_fonts = {
            "carta-selada": "Italianno",
            "envelope-botanico": "Great Vibes",
            "classico-dourado": "Cinzel",
            "luxo-preto": "Cinzel",
            "capulana": "Cinzel",
            "floral-rosa": "Great Vibes",
            "minimal-branco": "Cormorant Garamond",
            "azul-marinho": "Cinzel",
            "terracota": "Cormorant Garamond",
            "tropical": "Cormorant Garamond",
            "lavanda": "Cormorant Garamond",
            "areia-dourada": "Cormorant Garamond",
            "noite-estrelada": "Cinzel",
        }
        for code, family in expected_display_fonts.items():
            with self.subTest(template=code):
                template = registry.get_template(code)
                self.assertIn(family, template.display_font)
                self.assertIn(family.replace(" ", "+"), template.fonts_url)

    def test_event_colours_win_over_the_template_palette(self) -> None:
        template = registry.get_template("carta-selada")
        variables = template.css_variables("#123456", "#654321")
        self.assertIn("--inv-primary: #123456", variables)
        self.assertIn("--inv-secondary: #654321", variables)

    def test_every_palette_has_readable_semantic_colours(self) -> None:
        for template in InvitationTemplate.objects.active():
            with self.subTest(template=template.code):
                accent = readable_colour(
                    template.primary, template.paper, template.ink, minimum=7.0
                )
                self.assertGreaterEqual(_contrast(accent, template.paper), 7.0)

                variables = template.css_variables()
                self.assertIn(f"--inv-primary-text: {accent}", variables)
                self.assertIn("--inv-secondary-text:", variables)
                self.assertIn("--inv-on-primary:", variables)
                self.assertIn("--inv-on-secondary:", variables)
                self.assertIn("--inv-seal-bg:", variables)
                self.assertIn("--inv-on-seal:", variables)
                semantic = dict(
                    declaration.split(":", 1)
                    for declaration in variables.rstrip(";").split(";")
                )
                self.assertGreaterEqual(
                    _contrast(
                        semantic["--inv-seal-bg"], semantic["--inv-on-seal"]
                    ),
                    7.0,
                )


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

    def test_preview_includes_a_personal_qr_page_when_checkin_is_required(self) -> None:
        event = create_event(self.wedding, requires_qr_code=True)
        context = services.invitation_context(
            self.wedding,
            registry.get_template("carta-selada"),
            guest_name="Élio Nhaca",
            seats=2,
            is_preview=True,
        )
        self.assertEqual(context["qr_events"], [event])
        self.assertTrue(context["qr_data_uri"].startswith("data:image/svg+xml"))

    def test_qr_uses_the_high_contrast_paper_and_ink_pair(self) -> None:
        create_event(self.wedding, name="Recepção", requires_qr_code=True)
        template = registry.get_template("luxo-preto")
        context = services.invitation_context(self.wedding, template, is_preview=True)
        dark, light = sorted(
            (template.paper, template.ink), key=_relative_luminance
        )
        svg = unquote(context["qr_data_uri"]).lower()
        self.assertIn(f"fill='{light.lower()}'", svg)
        self.assertIn(f"stroke='{dark.lower()}'", svg)


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
        self.assertNotContains(response, "data-music-player")

    def test_classic_template_respects_its_cover_setting(self) -> None:
        response = self.client.get(
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "capulana"],
            )
        )
        self.assertContains(response, 'id="inv-cover"')
        self.assertContains(response, "Abrir o convite")
        self.assertContains(response, 'id="inv-main" hidden')

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

    def test_preview_shows_the_venue_and_a_collapsed_program_map(self) -> None:
        location = create_location(
            self.wedding,
            name="Salão Acácias",
            address="Av. da Marginal, Maputo",
        )
        create_event(self.wedding, name="Recepção", location=location)
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk])
        )
        self.assertContains(response, "Onde será")
        self.assertContains(response, "> Mapa</summary>", html=False)
        self.assertContains(response, "output=embed")
        self.assertContains(response, "inv-venue__map")

    def test_rsvp_is_disabled_in_the_preview(self) -> None:
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk])
        )
        self.assertContains(response, "inv-btn--disabled")

    def test_qr_page_uses_the_same_invitation_template(self) -> None:
        create_event(self.wedding, requires_qr_code=True)
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk])
        )
        self.assertContains(response, "O seu QR Code")
        self.assertContains(response, "QR de demonstração")
        self.assertContains(response, "data:image/svg+xml")

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

    def test_every_editorial_preview_background_exists(self) -> None:
        backgrounds = (
            "botanical-elegance-v1.webp",
            "classic-gold-v1.webp",
            "black-gold-v1.webp",
            "capulana-editorial-v1.webp",
            "minimal-paper-v1.webp",
            "navy-silver-v1.webp",
            "tropical-editorial-v1.webp",
            "lavender-editorial-v1.webp",
            "starry-night-v1.webp",
        )
        for background in backgrounds:
            with self.subTest(background=background):
                self.assertIsNotNone(finders.find(f"img/invitations/{background}"))


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

    def test_every_template_is_forced_to_have_an_interactive_cover(self) -> None:
        template = InvitationTemplate.objects.create(
            code="sem-capa", name="Sem capa", has_cover=False
        )
        self.assertTrue(template.has_cover)

    def test_admin_edit_page_contains_an_iphone_preview(self) -> None:
        create_wedding(self.staff, category=create_category())
        template = InvitationTemplate.objects.active().first()
        response = self.client.get(reverse("platform:template_edit", args=[template.pk]))
        self.assertContains(response, "admin-phone-preview")
        self.assertContains(response, reverse("platform:template_preview", args=[template.pk]))
        preview = self.client.get(reverse("platform:template_preview", args=[template.pk]))
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertContains(preview, "Abrir o convite")
        self.assertNotContains(preview, "data-music-player")
        self.assertContains(response, 'name="default_music"')
        self.assertNotContains(response, "Cada layout é um ficheiro")

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
