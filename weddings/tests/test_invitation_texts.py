"""Textos personalizáveis do convite (weddings/invitation_texts.py)."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from events.models import EventCategory
from guests.models import Gift, Guest
from templates_manager.models import InvitationTemplate
from weddings import invitation_texts as invtexts
from weddings.forms import WeddingSettingsForm
from weddings.invitation_texts import InvitationTexts

from .factories import DEFAULT_PASSWORD, create_user, create_wedding

INVITATION_TEMPLATES = Path(settings.BASE_DIR) / "templates" / "invitations"


def _category(code: str, **extra) -> EventCategory:
    defaults = {
        "name": "Casamento" if code == "casamento" else code.title(),
        "uses_two_names": True,
        "primary_label": "Nome da noiva",
        "secondary_label": "Nome do noivo",
        "names_separator": "&",
        "invitation_greeting": "têm o prazer de o convidar para celebrar o seu casamento",
        "field_schema": [],
        "default_moments": [],
        "default_schedule": [],
    }
    defaults.update(extra)
    category, _created = EventCategory.objects.get_or_create(code=code, defaults=defaults)
    return category


def _one_template_per_layout() -> dict[str, InvitationTemplate]:
    """Um template por ficheiro de layout (clona um se o catálogo não tiver)."""
    templates = {}
    for template in InvitationTemplate.objects.order_by("-is_active", "display_order", "code"):
        templates.setdefault(template.layout, template)
    base = next(iter(templates.values()))
    for path in sorted((INVITATION_TEMPLATES / "layouts").glob("*.html")):
        if path.stem not in templates:
            clone = InvitationTemplate.objects.get(pk=base.pk)
            clone.pk = None
            clone.code = f"test-{path.stem}".replace("_", "-")[:50]
            clone.layout = path.stem
            clone.save()
            templates[path.stem] = clone
    for template in templates.values():
        # Alguns layouts desenham a capa do template: basta ter um caminho.
        if not template.cover_image:
            template.cover_image = "invitation-templates/test-cover.jpg"
            template.save(update_fields=["cover_image"])
    return templates


class RegistryTests(TestCase):
    def test_every_key_used_in_the_templates_is_registered(self) -> None:
        used = set()
        for path in INVITATION_TEMPLATES.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            keys = set(re.findall(r'{%\s*invtext\s+"([a-z_]+)"', text))
            if keys:
                self.assertIn("invitation_texts", text.split("\n", 1)[0], path.name)
            used |= keys
        self.assertTrue(used)
        self.assertEqual(used - set(invtexts.REGISTRY), set())

    def test_every_stored_key_is_used_somewhere(self) -> None:
        sources = "".join(
            path.read_text(encoding="utf-8") for path in INVITATION_TEMPLATES.rglob("*.html")
        )
        sources += (Path(settings.BASE_DIR) / "guests" / "views.py").read_text(encoding="utf-8")
        for key in invtexts.REGISTRY:
            with self.subTest(key=key):
                self.assertIn(f'"{key}"', sources)

    def test_every_layout_on_disk_has_its_texts_resolved(self) -> None:
        for path in (INVITATION_TEMPLATES / "layouts").glob("*.html"):
            with self.subTest(layout=path.stem):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("Abrir o convite<", text)
                self.assertNotIn("Caro(a)", text)
                self.assertNotIn("Lugares reservados", text)

    def test_defaults_vary_by_layout_and_category(self) -> None:
        entry = invtexts.REGISTRY["open_button"]
        self.assertEqual(entry.default_for(layout="carta_selada"), "Abrir o convite")
        self.assertEqual(entry.default_for(layout="corporativo"), "Abrir convite")
        gallery = invtexts.REGISTRY["gallery_title"]
        self.assertEqual(gallery.default_for(category="casamento"), "Memórias de nós")
        self.assertEqual(gallery.default_for(category="evento-corporativo"), "Galeria")

    def test_keys_are_filtered_by_layout_and_category(self) -> None:
        corporate = {e.key for e in invtexts.keys_for(layout="corporativo", category="evento-corporativo")}
        self.assertIn("about_eyebrow", corporate)
        self.assertIn("partners_title", corporate)
        self.assertNotIn("music_play", corporate)
        self.assertNotIn("story_kicker", corporate)
        self.assertNotIn("parents_sentence", corporate)
        self.assertNotIn("cover_message", corporate)  # campo próprio

        wedding = {e.key for e in invtexts.keys_for(layout="carta_selada", category="casamento")}
        self.assertIn("parents_sentence", wedding)
        self.assertIn("intro_status", wedding)
        self.assertIn("music_play", wedding)
        self.assertNotIn("about_eyebrow", wedding)

        engagement = {e.key for e in invtexts.keys_for(layout="noivado_elegante", category="noivado")}
        self.assertNotIn("parents_sentence", engagement)
        self.assertNotIn("intro_status", engagement)

    def test_stored_data_is_sanitised(self) -> None:
        self.assertEqual(
            invtexts.sanitise_stored({
                "gallery_title": "  Os   nossos\nmomentos ",
                "unknown": "x",
                "cover_message": "campo próprio",
                "qr_title": 42,
                "rsvp_title": "",
                "open_button": "x" * 500,
            }),
            {"gallery_title": "Os nossos momentos", "open_button": "x" * 40},
        )
        self.assertEqual(invtexts.sanitise_stored(["not", "a", "dict"]), {})


class RenderingTests(TestCase):
    def setUp(self) -> None:
        self.wedding = create_wedding(category=_category("casamento"))

    def test_blank_uses_the_default(self) -> None:
        texts = InvitationTexts(self.wedding, "carta_selada", guest_name="Ana")
        self.assertEqual(texts.render("intro_status"), "A romper o lacre…")
        self.assertEqual(texts.render("greeting"), "Caro(a) Ana,")
        self.assertEqual(
            texts.plain("invitation_message"),
            "Natércia Alice Matola e Hivaldo José Cossa têm o prazer de o convidar para celebrar o seu casamento",
        )

    def test_custom_text_is_escaped_and_tokens_substituted(self) -> None:
        self.wedding.invitation_texts = {
            "greeting": "Olá <b>{convidado}</b> & família",
            "rsvp_deadline_text": "Responda até {data} {desconhecido}",
        }
        texts = InvitationTexts(self.wedding, "carta_selada", guest_name="<script>x</script>")
        self.assertEqual(
            texts.render("greeting"),
            "Olá &lt;b&gt;&lt;script&gt;x&lt;/script&gt;&lt;/b&gt; &amp; família",
        )
        self.assertEqual(
            texts.render("rsvp_deadline_text", data="01/02/2027"),
            "Responda até <strong>01/02/2027</strong> {desconhecido}",
        )
        self.assertEqual(texts.plain("greeting"), "Olá <b><script>x</script></b> & família")

    def test_multiline_model_field_keeps_line_breaks_safely(self) -> None:
        self.wedding.invitation_message = "Linha 1\n<i>Linha 2</i>"
        texts = InvitationTexts(self.wedding, "carta_selada")
        self.assertEqual(texts.render("invitation_message"), "Linha 1<br>&lt;i&gt;Linha 2&lt;/i&gt;")

    def test_template_tag_builds_texts_when_context_has_none(self) -> None:
        self.wedding.invitation_texts = {"qr_title": "A sua entrada"}
        template = Template('{% load invitation_texts %}{% invtext "qr_title" %}|{% invtext "open_button" as label %}{{ label }}')
        rendered = template.render(Context({"wedding": self.wedding}))
        self.assertEqual(rendered, "A sua entrada|Abrir o convite")


class GuestInvitationRenderingTests(TestCase):
    """Todos os layouts desenham os textos por omissão e os personalizados."""

    CUSTOM = {
        "open_button": "Entrar no convite",
        "greeting": "Querido(a) {convidado}!",
        "rsvp_button": "Diga-nos se vem",
        "rsvp_title": "Vem celebrar?",
        "rsvp_yes": "Claro que sim",
        "countdown_days": "dias ✨",
        "schedule_title": "O plano do dia",
        "qr_title": "A sua credencial",
        "page_title": "{nomes} convidam",
        "share_description": "Toque para abrir <já>",
        "gift_title": "Um mimo para nós",
        "music_play": "Tocar",
    }

    def setUp(self) -> None:
        from events.models import WeddingEvent
        from weddings.tests.factories import create_event, create_schedule_item

        self.owner = create_user()
        self.wedding = create_wedding(self.owner, category=_category("casamento"))
        create_schedule_item(self.wedding, title="Copo d'água")
        create_event(self.wedding, requires_qr_code=True)
        self.guest = Guest.objects.create(wedding=self.wedding, full_name="Ana <Mucavele>")
        self.guest.allowed_events.set(WeddingEvent.objects.filter(wedding=self.wedding))
        Gift.objects.create(wedding=self.wedding, name="Jogo de copos")

    def _render(self, template: InvitationTemplate):
        self.wedding.selected_template = template.code
        self.wedding.save(update_fields=["selected_template", "invitation_texts"])
        return self.client.get(reverse("guest_invitation", args=[self.guest.invitation_token]))

    def test_every_layout_renders_defaults_and_custom_texts(self) -> None:
        layouts = _one_template_per_layout()
        self.assertGreaterEqual(len(layouts), 6)
        self.assertLessEqual(
            {path.stem for path in (INVITATION_TEMPLATES / "layouts").glob("*.html")},
            set(layouts),
        )
        for layout, template in layouts.items():
            with self.subTest(layout=layout):
                self.wedding.invitation_texts = {}
                response = self._render(template)
                self.assertEqual(response.status_code, 200)
                texts = InvitationTexts(self.wedding, layout)
                self.assertContains(response, texts.default("open_button"))
                self.assertContains(response, "Caro(a) Ana &lt;Mucavele&gt;,")
                self.assertContains(response, "Confirmar presença")
                self.assertContains(response, "Escolha um presente")
                self.assertContains(response, "<small>dias</small>", html=False)

                self.wedding.invitation_texts = dict(self.CUSTOM)
                response = self._render(template)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Entrar no convite")
                self.assertContains(response, "Querido(a) Ana &lt;Mucavele&gt;!")
                self.assertContains(response, "Diga-nos se vem")
                self.assertContains(response, "Vem celebrar?")
                self.assertContains(response, "Claro que sim")
                self.assertContains(response, "dias ✨")
                self.assertContains(response, "O plano do dia")
                self.assertContains(response, "A sua credencial")
                self.assertContains(response, "Um mimo para nós")
                self.assertContains(response, "<title>Natércia &amp; Hivaldo convidam</title>", html=False)
                self.assertContains(response, 'content="Toque para abrir &lt;já&gt;"', html=False)
                self.assertNotContains(response, "Confirmar presença")
                self.assertNotContains(response, "Caro(a)")

    def test_rsvp_and_gift_toasts_use_custom_texts(self) -> None:
        self.wedding.invitation_texts = {
            "rsvp_thanks_toast": "Obrigado, {convidado}!",
            "gift_selected_toast": "Fica com «{presente}».",
        }
        self.wedding.save(update_fields=["invitation_texts"])
        url = reverse("guest_invitation", args=[self.guest.invitation_token])
        response = self.client.post(url, {"rsvp": "confirmed"}, follow=True)
        self.assertContains(response, 'data-message="Obrigado, Ana &lt;Mucavele&gt;!"', html=False)

        gift = Gift.objects.get(wedding=self.wedding)
        response = self.client.post(
            reverse("guest_gift_select", args=[self.guest.invitation_token, gift.pk]), follow=True
        )
        self.assertContains(response, "Fica com «Jogo de copos».")

    def test_corporate_layout_uses_corporate_texts(self) -> None:
        corporate = EventCategory.objects.get(code="evento-corporativo")
        self.wedding.category = corporate
        self.wedding.extra_data = {
            "organizacao": "True North",
            "tema_objetivo": "Estratégia",
            "patrocinadores": ["Parceiro A"],
        }
        self.wedding.invitation_texts = {
            "about_title": "A agenda",
            "partners_eyebrow": "Com o apoio de",
            "corporate_host": "Organizado por {organizacao}",
        }
        self.wedding.save()
        template = _one_template_per_layout()["corporativo"]
        response = self._render(template)
        self.assertContains(response, "A agenda")
        self.assertContains(response, "Com o apoio de")
        self.assertContains(response, "Organizado por <strong>True North</strong>", html=False)
        self.assertContains(response, "Organizações participantes")


class EditorFormTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner, category=_category("casamento"))
        self.url = reverse("weddings:detail", args=[self.wedding.pk])
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def _payload(self, **texts) -> dict:
        payload = {
            "primary_name": self.wedding.primary_name,
            "secondary_name": self.wedding.secondary_name,
            "main_date": self.wedding.main_date.isoformat(),
            "country": self.wedding.country,
            "invitation_host": self.wedding.invitation_host,
            "sms_invitation_message": self.wedding.sms_invitation_message,
            "whatsapp_invitation_message": self.wedding.whatsapp_invitation_message,
            "show_seat_before_event": self.wedding.show_seat_before_event,
        }
        payload.update({f"invtext__{key}": value for key, value in texts.items()})
        return payload

    def test_editor_lists_grouped_texts_with_defaults_as_placeholders(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, "Palavras que dão personalidade")
        self.assertContains(response, "Todas as frases que o convidado lê")
        for label in ("Capa e abertura", "Confirmação de presença", "Presentes", "QR Code e entrada", "Galeria", "Programa"):
            self.assertContains(response, label)
        self.assertContains(response, 'name="invtext__gallery_title"', html=False)
        self.assertContains(response, 'placeholder="Memórias de nós"', html=False)
        self.assertContains(response, 'placeholder="A romper o lacre…"', html=False)
        self.assertContains(response, 'maxlength="40"', html=False)
        self.assertContains(response, "data-invtext-reset", html=False)
        # Frase principal por omissão, com os nomes já preenchidos.
        self.assertContains(
            response,
            "Natércia Alice Matola e Hivaldo José Cossa têm o prazer de o convidar",
        )
        # Chaves de outros layouts/categorias não aparecem.
        self.assertNotContains(response, 'name="invtext__about_title"', html=False)

    def test_corporate_editor_shows_only_corporate_texts(self) -> None:
        self.wedding.category = EventCategory.objects.get(code="evento-corporativo")
        self.wedding.selected_template = _one_template_per_layout()["corporativo"].code
        self.wedding.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'name="invtext__about_title"', html=False)
        self.assertContains(response, 'name="invtext__partners_eyebrow"', html=False)
        self.assertNotContains(response, 'name="invtext__music_play"', html=False)
        self.assertNotContains(response, 'name="invtext__story_kicker"', html=False)
        self.assertNotContains(response, "O Nosso Casamento")

    def test_save_custom_text_and_reset_to_default(self) -> None:
        response = self.client.post(self.url, self._payload(
            gallery_title="  Os nossos   momentos ",
            rsvp_button="Vens?",
            qr_title="",
        ))
        self.assertRedirects(response, self.url)
        self.wedding.refresh_from_db()
        self.assertEqual(
            self.wedding.invitation_texts,
            {"gallery_title": "Os nossos momentos", "rsvp_button": "Vens?"},
        )

        # Campos ausentes do pedido mantêm-se; em branco repõe o original.
        response = self.client.post(self.url, self._payload(gallery_title=""))
        self.assertRedirects(response, self.url)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.invitation_texts, {"rsvp_button": "Vens?"})

        # Escrever exactamente o texto original também conta como «original».
        response = self.client.post(self.url, self._payload(rsvp_button="Confirmar presença"))
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.invitation_texts, {})

    def test_limits_and_unknown_tokens_are_validated(self) -> None:
        response = self.client.post(self.url, self._payload(
            open_button="x" * 41,
            greeting="Olá {amigo}",
        ))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("invtext__open_button", form.errors)
        self.assertIn("invtext__greeting", form.errors)
        self.assertIn("{amigo}", form.errors["invtext__greeting"][0])
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.invitation_texts, {})

    def test_unknown_and_hidden_keys_are_handled_safely(self) -> None:
        # Chave de outro layout (guardada antes de mudar de template) mantém-se;
        # chaves desconhecidas desaparecem.
        self.wedding.invitation_texts = {"about_title": "A agenda", "legacy": "x"}
        self.wedding.save(update_fields=["invitation_texts"])
        form = WeddingSettingsForm(
            data=self._payload(gallery_title="Fotografias", invented_key="y"),
            instance=self.wedding,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.invitation_texts(),
            {"about_title": "A agenda", "gallery_title": "Fotografias"},
        )
        self.assertNotIn("invtext__invented_key", form.fields)
