"""Smoke tests: every page of phase 1 must render without template errors."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.urls import reverse

from core.utils import generate_short_code, normalise_phone, unique_slugify
from weddings.tests.factories import (
    DEFAULT_PASSWORD,
    create_event,
    create_location,
    create_schedule_item,
    create_user,
    create_wedding,
    create_category,
)


class PublicPageTests(TestCase):
    def test_home_page_renders(self) -> None:
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Convites digitais")
        self.assertContains(response, "O seu momento começa aqui")
        self.assertContains(response, 'class="hero__banner-image"')
        self.assertNotContains(response, ">Começar agora<")
        self.assertNotContains(response, ">Já tenho conta<")
        self.assertNotContains(response, "<svg")
        self.assertContains(response, "Organize cada momento da celebração")
        self.assertContains(response, reverse("core:privacy"))
        self.assertContains(response, reverse("core:terms"))

    def test_public_legal_pages_render(self) -> None:
        pages = {
            "privacy": "Política de privacidade",
            "terms": "Termos e condições",
            "cookies": "Política de cookies",
            "security": "Segurança",
            "contact": "Contacto e apoio",
        }
        for name, heading in pages.items():
            with self.subTest(name=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading)

    def test_home_shows_templates_and_selection_requests_login(self) -> None:
        from templates_manager.models import InvitationTemplate

        category = create_category(code="evento-publico", name="Evento público")
        template = InvitationTemplate.objects.active().order_by(
            "-is_featured", "display_order", "name"
        ).first()
        self.assertIsNotNone(template)

        selection_url = (
            f"{reverse('weddings:create')}?tipo={category.code}&template={template.code}"
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Escolha um design para o seu evento")
        self.assertContains(response, template.name)
        self.assertContains(response, selection_url.replace("&", "&amp;"))

        redirect_response = self.client.get(selection_url)
        self.assertEqual(redirect_response.status_code, 302)
        location = urlparse(redirect_response["Location"])
        self.assertEqual(location.path, reverse("account_login"))
        self.assertEqual(parse_qs(location.query)["next"], [selection_url])

    def test_home_redirects_authenticated_users(self) -> None:
        create_user()
        self.client.login(email="noiva@example.com", password=DEFAULT_PASSWORD)
        response = self.client.get(reverse("core:home"))
        self.assertRedirects(response, reverse("weddings:list"))

    def test_health_endpoint(self) -> None:
        response = self.client.get(reverse("core:health"))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_login_page_renders(self) -> None:
        response = self.client.get(reverse("account_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-control")

    def test_signup_page_only_asks_for_name_email_and_password(self) -> None:
        response = self.client.get(reverse("account_signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')
        self.assertNotContains(response, 'name="password2"')
        self.assertNotContains(response, 'name="phone"')

    def test_password_reset_page_renders(self) -> None:
        response = self.client.get(reverse("account_reset_password"))
        self.assertEqual(response.status_code, 200)


class AuthenticatedPageTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.location = create_location(self.wedding)
        self.event = create_event(self.wedding, location=self.location)
        create_schedule_item(self.wedding, title="Cerimónia Religiosa")
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_all_wedding_pages_render(self) -> None:
        urls = [
            reverse("weddings:list"),
            reverse("weddings:detail", args=[self.wedding.pk]),
            reverse("weddings:setup", args=[self.wedding.pk]),
            reverse("weddings:settings", args=[self.wedding.pk]),
            reverse("weddings:design", args=[self.wedding.pk]),
            reverse("weddings:team", args=[self.wedding.pk]),
            reverse("events:list", args=[self.wedding.pk]),
            reverse("events:create", args=[self.wedding.pk]),
            reverse("events:edit", args=[self.wedding.pk, self.event.pk]),
            reverse("events:location_list", args=[self.wedding.pk]),
            reverse("events:location_create", args=[self.wedding.pk]),
            reverse("events:schedule", args=[self.wedding.pk]),
            reverse("events:schedule_create", args=[self.wedding.pk]),
            reverse("accounts:profile"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)


class UtilsTests(TestCase):
    def test_short_code_avoids_ambiguous_characters(self) -> None:
        code = generate_short_code(12)
        self.assertEqual(len(code), 12)
        for char in "01OI":
            self.assertNotIn(char, code)

    def test_phone_normalisation(self) -> None:
        cases = {
            "84 123 4567": "+258841234567",
            "084 123 4567": "+258841234567",
            "+258841234567": "+258841234567",
            "00258841234567": "+258841234567",
            "258841234567": "+258841234567",
            "": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalise_phone(raw), expected)

    def test_unique_slugify_avoids_collisions(self) -> None:
        first = create_wedding(create_user("a@example.com"))
        second = create_wedding(create_user("b@example.com"))
        generated = unique_slugify(second, "natercia-e-hivaldo")
        self.assertNotEqual(generated, first.slug)
