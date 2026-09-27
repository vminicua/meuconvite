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

    def test_engagement_collection_uses_script_typography(self) -> None:
        templates = InvitationTemplate.objects.filter(
            code__startswith="noivado-", layout=InvitationLayout.ENGAGEMENT
        )
        self.assertEqual(templates.count(), 7)
        for template in templates:
            with self.subTest(template=template.code):
                self.assertIn("Great Vibes", template.display_font)
                self.assertIn("Great+Vibes", template.google_fonts)

    def test_featured_templates_include_social_and_corporate_collections(self) -> None:
        featured = InvitationTemplate.objects.featured().order_by("display_order")
        codes = [template.code for template in featured]
        self.assertIn("carta-selada", codes)
        self.assertIn("envelope-botanico", codes)
        self.assertIn("corporate-executive-summit", codes)
        self.assertIn("corporate-innovation-forum", codes)
        self.assertIn("corporate-gala", codes)

    def test_featured_templates_use_the_supported_layouts(self) -> None:
        layouts = set(
            InvitationTemplate.objects.featured().values_list("layout", flat=True)
        )
        self.assertEqual(
            layouts,
            {
                InvitationLayout.SEALED_LETTER,
                InvitationLayout.BOTANICAL,
                InvitationLayout.CORPORATE,
                InvitationLayout.ENGAGEMENT,
                InvitationLayout.EDITORIAL,
            },
        )

    def test_corporate_category_only_receives_corporate_templates(self) -> None:
        from events.models import EventCategory

        corporate = EventCategory.objects.get(code="evento-corporativo")
        templates = list(registry.all_templates(corporate))
        self.assertEqual(
            {template.code for template in templates},
            {
                "corporate-executive-summit",
                "corporate-innovation-forum",
                "corporate-gala",
            },
        )
        self.assertTrue(all(template.layout == InvitationLayout.CORPORATE for template in templates))
        self.assertTrue(all(not template.supports_music for template in templates))
        self.assertTrue(all(template.cover_image for template in templates))

    def test_engagement_category_has_its_curated_templates(self) -> None:
        from events.models import EventCategory

        engagement = EventCategory.objects.get(code="noivado")
        templates = list(registry.all_templates(engagement))
        self.assertEqual(len(templates), 8)
        self.assertEqual(templates[0].code, "noivado-editorial-rose")
        self.assertEqual(
            {template.layout for template in templates},
            {InvitationLayout.ENGAGEMENT, InvitationLayout.EDITORIAL},
        )
        self.assertTrue(all(template.cover_image for template in templates))


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
            "classico-dourado": "Allura",
            "luxo-preto": "Parisienne",
            "capulana": "Allura",
            "floral-rosa": "Great Vibes",
            "minimal-branco": "Parisienne",
            "azul-marinho": "Allura",
            "terracota": "Great Vibes",
            "tropical": "Italianno",
            "lavanda": "Parisienne",
            "areia-dourada": "Allura",
            "noite-estrelada": "Italianno",
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
        self.assertContains(response, "data-sealed-intro")
        self.assertContains(response, "burgundy-wax-seal-v1.png")
        self.assertContains(response, "inv--cover-pending")
        self.assertNotContains(response, "Onde será")
        self.assertNotContains(response, "data-music-player")

    def test_cover_only_skips_the_opening_scene(self) -> None:
        response = self.client.get(
            reverse("weddings:invitation_preview", args=[self.wedding.pk]),
            {"cover_only": "1"},
        )
        self.assertNotContains(response, "data-sealed-intro")
        self.assertContains(response, "burgundy-wax-seal-v1.png")

    def test_custom_cover_is_not_repeated_inside_the_invitation(self) -> None:
        self.wedding.cover_image.save(
            "personalizada.png",
            SimpleUploadedFile(
                "personalizada.png",
                b"custom-cover-test",
                content_type="image/png",
            ),
            save=True,
        )
        preview_urls = [
            reverse("weddings:invitation_preview", args=[self.wedding.pk]),
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "capulana"],
            ),
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "envelope-botanico"],
            ),
        ]
        for preview_url in preview_urls:
            with self.subTest(url=preview_url):
                response = self.client.get(preview_url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "inv-hero__photo")

    def test_classic_template_respects_its_cover_setting(self) -> None:
        response = self.client.get(
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "capulana"],
            )
        )
        self.assertContains(response, 'id="inv-cover"')
        self.assertContains(response, "data-themed-intro")
        self.assertContains(response, "Abrir o convite")
        self.assertContains(response, 'id="inv-main" hidden')

    def test_requested_classic_templates_have_themed_openings(self) -> None:
        animated_codes = [
            "classico-dourado", "luxo-preto", "capulana", "floral-rosa",
            "azul-marinho", "terracota", "tropical", "lavanda",
            "areia-dourada", "noite-estrelada",
        ]
        for code in animated_codes:
            with self.subTest(template=code):
                response = self.client.get(
                    reverse(
                        "weddings:invitation_preview_template",
                        args=[self.wedding.pk, code],
                    )
                )
                self.assertContains(response, "data-themed-intro")
                self.assertContains(response, f"{code}-seal-v1.png", count=2)

    def test_engagement_templates_have_a_cinematic_opening(self) -> None:
        response = self.client.get(
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "noivado-jardim-promessas"],
            )
        )
        self.assertContains(response, "data-engagement-scene")
        self.assertContains(response, "inv-engagement-petal", count=14)
        self.assertContains(response, "inv-engagement-curtain--left")
        self.assertContains(response, "inv-engagement-ring")

    def test_thematic_collections_have_category_aware_cinematic_openings(self) -> None:
        templates = [
            ("lobolo", "lobolo-heranca-dourada"),
            ("aniversario", "aniversario-festa-vibrante"),
            ("batismo", "batismo-luz-serena"),
            ("formatura", "graduacao-conquista-academica"),
            ("cha-de-bebe", "cha-bebe-nuvem-doce"),
            ("outro", "outro-celebracao-livre"),
        ]
        for category_code, code in templates:
            with self.subTest(template=code):
                category = create_category(code=category_code, name=category_code.title())
                invitation_template = InvitationTemplate.objects.create(
                    code=code,
                    name=code,
                    layout=InvitationLayout.THEMATIC,
                    cover_image=f"templates/covers/tests/{code}.png",
                )
                invitation_template.categories.add(category)
                self.wedding.category = category
                self.wedding.save(update_fields=["category", "updated_at"])
                response = self.client.get(
                    reverse(
                        "weddings:invitation_preview_template",
                        args=[self.wedding.pk, code],
                    )
                )
                self.assertContains(response, "data-theme-cinematic")
                self.assertContains(response, "theme-cinematic-particle", count=8)
                self.assertContains(response, "theme-cinematic-curtain--left")

    def test_minimal_template_keeps_its_quiet_opening(self) -> None:
        response = self.client.get(
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "minimal-branco"],
            )
        )
        self.assertNotContains(response, "data-themed-intro")

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

    def test_all_layouts_show_locations_only_inside_the_program(self) -> None:
        location = create_location(
            self.wedding,
            name="Salão Acácias",
            address="Av. da Marginal, Maputo",
        )
        create_event(self.wedding, name="Recepção", location=location)
        preview_urls = [
            reverse("weddings:invitation_preview", args=[self.wedding.pk]),
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "classico-dourado"],
            ),
            reverse(
                "weddings:invitation_preview_template",
                args=[self.wedding.pk, "envelope-botanico"],
            ),
        ]
        for preview_url in preview_urls:
            with self.subTest(url=preview_url):
                response = self.client.get(preview_url)
                self.assertNotContains(response, "Onde será")
                self.assertContains(response, "inv-map__toggle")
                self.assertContains(response, "output=embed")
                self.assertContains(response, '<div class="inv-map__frame">', html=False)
                self.assertNotContains(response, "inv-venue__map")

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


class EditorialLayoutTests(TestCase):
    """Layout «Editorial romântico» e os templates semeados pela 0013."""

    migration = "templates_manager.migrations.0013_editorial_romantic_layout"

    def setUp(self) -> None:
        import importlib

        from django.apps import apps
        from events.models import EventCategory

        # Numa base nova a categoria «casamento» só existe depois do
        # seed_event_categories: criamo-la e voltamos a correr a migração,
        # como acontece em produção (e para provar que é idempotente).
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        media_settings = self.settings(MEDIA_ROOT=self.media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        if not EventCategory.objects.filter(code="casamento").exists():
            create_category()
        module = importlib.import_module(self.migration)
        module.forwards(apps, None)
        module.forwards(apps, None)
        self.module = module

    def test_both_templates_are_seeded_once_with_their_category(self) -> None:
        wedding = InvitationTemplate.objects.get(code="editorial-terracota")
        engagement = InvitationTemplate.objects.get(code="noivado-editorial-rose")
        for template, category in ((wedding, "casamento"), (engagement, "noivado")):
            with self.subTest(template=template.code):
                self.assertEqual(template.layout, InvitationLayout.EDITORIAL)
                self.assertEqual(list(template.categories.values_list("code", flat=True)), [category])
                self.assertTrue(template.is_featured)
                self.assertTrue(template.has_countdown and template.supports_music and template.has_cover)
                self.assertTrue(template.cover_image.name.startswith("templates/covers/editorial/"))
                self.assertIsNotNone(finders.find(f"img/templates/editorial/{template.cover_image.name.rsplit('/', 1)[1]}"))
        self.assertEqual(
            InvitationTemplate.objects.filter(layout=InvitationLayout.EDITORIAL).count(), 2
        )

    def test_editorial_templates_come_first_for_their_category(self) -> None:
        from events.models import EventCategory

        for code, template_code in (("casamento", "editorial-terracota"), ("noivado", "noivado-editorial-rose")):
            with self.subTest(category=code):
                category = EventCategory.objects.get(code=code)
                self.assertEqual(registry.all_templates(category).first().code, template_code)

    def test_static_assets_exist(self) -> None:
        for asset in (
            "css/invitation-editorial.css",
            "img/invitations/editorial/floral-corner-terracota.webp",
            "img/invitations/editorial/floral-corner-rose.webp",
            "img/invitations/editorial/floral-sprig-terracota.webp",
            "img/invitations/editorial/floral-sprig-rose.webp",
            "img/invitations/editorial/paper-grain.webp",
        ):
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))

    def _guest_page(self, template_code: str, **wedding_fields):
        from events.models import EventCategory, EventType
        from guests.models import Gift, Guest
        from weddings.models import WeddingGalleryPhoto

        template = InvitationTemplate.objects.get(code=template_code)
        category = template.categories.first()
        wedding = create_wedding(
            category=category, selected_template=template_code, show_story=True,
            story_verse="O amor é paciente.", story_verse_reference="1 Coríntios 13:4",
            primary_parents_names="Maria e Joaquim Mate", secondary_parents_names="Ana e Manuel Cossa",
            **wedding_fields,
        )
        location = create_location(wedding, name="Jardim da Polana", address="Av. Julius Nyerere, Maputo")
        reception = create_event(
            wedding, name="Recepção", event_type=EventType.RECEPTION,
            location=location, dress_code="Traje formal",
        )
        guest = Guest.objects.create(wedding=wedding, full_name="Élio Nhaca", party_size=2)
        guest.allowed_events.set([reception])
        Gift.objects.create(wedding=wedding, name="Jogo de copos")
        for order in range(3):
            WeddingGalleryPhoto.objects.create(
                wedding=wedding, external_url=f"https://example.com/foto-{order}.jpg", display_order=order
            )
        return self.client.get(reverse("guest_invitation", args=[guest.invitation_token]))

    def test_guest_page_renders_every_editorial_section(self) -> None:
        response = self._guest_page("editorial-terracota")
        self.assertEqual(response.status_code, 200)
        for fragment in (
            "inv--editorial_romantico",
            "css/invitation-editorial.css",
            'class="inv-cover inv-cover--editorial',
            "data-open-invitation",
            "Élio Nhaca",
            "Vamos casar!",
            "O amor é paciente.",
            "Pais de Natércia",
            "Maria e Joaquim Mate",
            "Nós,",
            "temos a alegria de o convidar para o nosso casamento",
            "data-countdown",
            "Onde celebramos",
            "Jardim da Polana",
            "Ver localização",
            "output=embed",
            "Itinerário",
            "#ed-i-dinner",
            "Traje formal",
            "Sugestão de presente",
            "Jogo de copos",
            'data-dialog-open="rsvp-dialog"',
            "Guardar na agenda",
            "Obrigado!",
            "https://example.com/foto-0.jpg",
            "data-ed-parallax",
            "ed-tear",
        ):
            with self.subTest(fragment=fragment):
                self.assertContains(response, fragment)
        self.assertNotContains(response, "Onde será")

    def test_engagement_template_uses_its_own_wording_and_florals(self) -> None:
        response = self._guest_page("noivado-editorial-rose", extra_data={"traje": "Traje semi-formal"})
        self.assertContains(response, "Dissemos sim!")
        self.assertContains(response, "o nosso noivado")
        self.assertContains(response, "Traje semi-formal")
        self.assertContains(response, "ed-set--rose")

    def test_editorial_page_without_photos_or_programme_still_renders(self) -> None:
        from events.models import EventCategory

        wedding = create_wedding(
            category=EventCategory.objects.get(code="casamento"),
            selected_template="editorial-terracota",
        )
        context = services.invitation_context(
            wedding, InvitationTemplate.objects.get(code="editorial-terracota"), is_preview=True
        )
        from django.template.loader import render_to_string

        html = render_to_string("invitations/preview.html", context)
        self.assertIn("ed-cover--paper", html)
        self.assertNotIn("ed-photo__img", html)
        self.assertNotIn("Itinerário", html)
        self.assertNotIn("Onde celebramos", html)

    def test_dress_codes_come_from_the_programme_and_category_fields(self) -> None:
        from events.models import EventCategory

        wedding = create_wedding(
            category=EventCategory.objects.get(code="noivado"), extra_data={"traje": "Traje formal"}
        )
        create_event(wedding, name="Jantar", dress_code="traje formal")
        create_event(wedding, name="Festa", dress_code="Branco")
        context = services.invitation_context(
            wedding, InvitationTemplate.objects.get(code="noivado-editorial-rose"), include_qr=False
        )
        self.assertEqual(
            context["dress_codes"],
            [{"event": "", "value": "Traje formal"}, {"event": "Festa", "value": "Branco"}],
        )


class TemplateAssetTagTests(TestCase):
    """Folha de estilos, script e camada decorativa por template são opcionais."""

    def test_missing_assets_render_nothing(self) -> None:
        from types import SimpleNamespace

        from django.template import Context, Template

        rendered = Template(
            "{% load template_assets %}"
            "{% template_stylesheet tpl %}{% template_script tpl %}{% template_decor tpl %}"
        ).render(Context({"tpl": SimpleNamespace(code="sem-recursos-proprios")}))
        self.assertEqual(rendered, "")
