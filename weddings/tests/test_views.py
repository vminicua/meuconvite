from __future__ import annotations

import base64
from datetime import timedelta

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from templates_manager.models import InvitationTemplate
from weddings.models import Wedding, WeddingGalleryPhoto, WeddingMember, WeddingRole

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


class EventCreationViewTests(TestCase):
    """Criar um evento: escolher o tipo e preencher o mínimo."""

    def setUp(self) -> None:
        self.user = create_user()
        self.client.login(email=self.user.email, password=DEFAULT_PASSWORD)
        self.plan = create_plan()
        self.category = create_category(
            field_schema=[
                {
                    "key": "traje",
                    "label": "Traje",
                    "type": "choice",
                    "choices": ["Traje formal", "Traje casual"],
                },
                {
                    "key": "lista_presentes",
                    "label": "Lista de presentes",
                    "type": "list",
                },
            ],
            default_moments=[{"name": "Recepção", "event_type": "reception", "start_time": "19:30"}],
            default_schedule=[{"title": "Corte do bolo", "start_time": "18:30", "icon": "bi-cake2"}],
        )
        self.birthday = create_category(
            code="aniversario",
            name="Aniversário",
            uses_two_names=False,
            primary_label="Nome do aniversariante",
            secondary_label="",
            field_schema=[{"key": "idade", "label": "Idade a celebrar", "type": "number"}],
        )
        self.url = reverse("weddings:create")
        self.template = InvitationTemplate.objects.filter(is_active=True).first()

    def _payload(self, **overrides) -> dict:
        data = {
            "category": self.category.code,
            "template": self.template.code,
            "primary_name": "Ivone Alice Sitoe",
            "secondary_name": "Dário José Machava",
            "main_date": (timezone.localdate() + timedelta(days=100)).isoformat(),
        }
        data.update(overrides)
        return data

    def _form_url(self, category: str = "", template: str = "") -> str:
        return (
            f"{self.url}?tipo={category or self.category.code}"
            f"&template={template or self.template.code}"
        )

    def test_without_a_type_the_choices_are_shown(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Que tipo de evento")
        self.assertContains(response, "Aniversário")

    def test_unknown_type_falls_back_to_the_choices(self) -> None:
        response = self.client.get(self.url, {"tipo": "nao-existe"})
        self.assertContains(response, "Que tipo de evento")

    def test_choosing_a_type_asks_for_the_template(self) -> None:
        response = self.client.get(self.url, {"tipo": self.category.code})
        self.assertContains(response, "Escolha o convite")
        self.assertContains(response, self.template.name)

    def test_the_form_uses_the_labels_of_the_chosen_type(self) -> None:
        response = self.client.get(self._form_url(category="aniversario"))
        self.assertContains(response, "Nome do aniversariante")
        self.assertNotContains(response, "Idade a celebrar")
        self.assertNotContains(response, "Cidade")
        self.assertNotContains(response, "Endereço")
        # Um só protagonista: o segundo nome não é pedido.
        self.assertNotContains(response, 'name="secondary_name"')

    def test_creates_the_event_and_opens_the_invitation_preview(self) -> None:
        response = self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertRedirects(response, reverse("weddings:preview", args=[wedding.pk]))
        self.assertEqual(wedding.category, self.category)
        self.assertEqual(wedding.city, "")
        self.assertEqual(wedding.extra_data, {})

    def test_short_names_are_derived_from_the_full_names(self) -> None:
        self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(wedding.primary_short_name, "Ivone")
        self.assertEqual(wedding.secondary_short_name, "Dário")
        self.assertEqual(wedding.display_names, "Ivone & Dário")

    def test_category_defaults_are_applied(self) -> None:
        """O evento nasce com uma única sequência de programa sugerida."""
        from events.models import ScheduleItem, WeddingEvent

        self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(WeddingEvent.objects.filter(wedding=wedding).count(), 2)
        self.assertEqual(ScheduleItem.objects.filter(wedding=wedding).count(), 0)

    def test_a_free_subscription_is_created(self) -> None:
        self.client.post(self._form_url(), data=self._payload())
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(wedding.subscription.plan, self.plan)
        self.assertEqual(wedding.subscription.guest_allowance, 20)

    def test_extra_fields_are_only_added_after_creation(self) -> None:
        self.client.post(
            self._form_url(category="aniversario"),
            data={
                "category": "aniversario",
                "template": self.template.code,
                "primary_name": "Amélia Nhaca",
                "main_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
                "extra__idade": "40",
            },
        )
        wedding = Wedding.objects.get(owner=self.user)
        self.assertEqual(wedding.extra_data, {})
        self.assertEqual(wedding.display_names, "Amélia")

        settings_url = reverse("weddings:settings", args=[wedding.pk])
        response = self.client.get(settings_url)
        self.assertContains(response, "Idade a celebrar")

        response = self.client.post(
            settings_url,
            data={
                "primary_name": wedding.primary_name,
                "primary_short_name": wedding.primary_short_name,
                "main_date": wedding.main_date.isoformat(),
                "city": "Av. Julius Nyerere, Maputo",
                "country": wedding.country,
                "slug": wedding.slug,
                "show_seat_before_event": wedding.show_seat_before_event,
                "extra__idade": "40",
            },
        )
        self.assertRedirects(response, settings_url)
        wedding.refresh_from_db()
        self.assertEqual(wedding.city, "Av. Julius Nyerere, Maputo")
        self.assertEqual(wedding.extra_data.get("idade"), "40")

    def test_dress_code_and_gift_list_are_edited_after_creation(self) -> None:
        create_response = self.client.post(self._form_url(), data=self._payload())
        self.assertEqual(create_response.status_code, 302)
        wedding = Wedding.objects.get(owner=self.user)
        settings_url = reverse("weddings:settings", args=[wedding.pk])

        response = self.client.get(settings_url)
        self.assertContains(response, '<select name="extra__traje"', html=False)
        self.assertContains(response, "— Não especificar —")
        self.assertContains(response, "data-repeated-field")
        self.assertContains(response, "Adicionar linha")

        response = self.client.post(
            settings_url,
            data={
                "primary_name": wedding.primary_name,
                "secondary_name": wedding.secondary_name,
                "primary_short_name": wedding.primary_short_name,
                "secondary_short_name": wedding.secondary_short_name,
                "main_date": wedding.main_date.isoformat(),
                "city": "Matola",
                "country": wedding.country,
                "slug": wedding.slug,
                "show_seat_before_event": wedding.show_seat_before_event,
                "extra__traje": "Traje formal",
                "extra__lista_presentes": [
                    "Liquidificador",
                    "https://loja.example/presentes",
                ],
            },
        )
        self.assertRedirects(response, settings_url)
        wedding.refresh_from_db()
        self.assertEqual(wedding.extra_data["traje"], "Traje formal")
        self.assertEqual(
            wedding.extra_data["lista_presentes"],
            ["Liquidificador", "https://loja.example/presentes"],
        )

    def test_rejects_a_date_in_the_past(self) -> None:
        response = self.client.post(
            self._form_url(),
            data=self._payload(main_date=(timezone.localdate() - timedelta(days=1)).isoformat()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Wedding.objects.exists())

    def test_the_second_name_is_required_for_two_name_types(self) -> None:
        response = self.client.post(self._form_url(), data=self._payload(secondary_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Wedding.objects.exists())


class DashboardViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_dashboard_shows_the_checklist(self) -> None:
        response = self.client.get(reverse("weddings:detail", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estado da preparação")
        self.assertEqual(len(response.context["checklist"]), 7)

    def test_cover_and_invitation_messages_are_edited_in_event_details(self) -> None:
        url = reverse("weddings:detail", args=[self.wedding.pk])
        response = self.client.get(url)
        self.assertContains(response, "Capa do convite")
        self.assertContains(response, "Música do convite")
        self.assertContains(response, 'id="id_invitation_music"', html=False)
        self.assertContains(response, 'id="id_show_music"', html=False)
        self.assertContains(response, "Mensagem da capa")
        self.assertContains(response, "Mensagem principal do convite")

        response = self.client.post(url, {
            "primary_name": self.wedding.primary_name,
            "secondary_name": self.wedding.secondary_name,
            "primary_short_name": self.wedding.primary_short_name,
            "secondary_short_name": self.wedding.secondary_short_name,
            "main_date": self.wedding.main_date.isoformat(),
            "city": self.wedding.city,
            "country": self.wedding.country,
            "slug": self.wedding.slug,
            "cover_message": "O nosso grande dia começa aqui",
            "invitation_message": "É com muita alegria que queremos celebrar consigo.",
            "show_seat_before_event": self.wedding.show_seat_before_event,
        })
        self.assertRedirects(response, url)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.cover_message, "O nosso grande dia começa aqui")
        self.assertEqual(
            self.wedding.invitation_message,
            "É com muita alegria que queremos celebrar consigo.",
        )

        preview = self.client.get(reverse("weddings:invitation_preview", args=[self.wedding.pk]))
        self.assertContains(preview, "O nosso grande dia começa aqui")
        self.assertContains(preview, "É com muita alegria que queremos celebrar consigo.")

    def test_returning_to_the_original_cover_clears_the_uploaded_file(self) -> None:
        self.wedding.cover_image.save(
            "personalizada.png",
            SimpleUploadedFile(
                "personalizada.png",
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                ),
                content_type="image/png",
            ),
            save=True,
        )
        url = reverse("weddings:detail", args=[self.wedding.pk])
        response = self.client.post(url, {
            "primary_name": self.wedding.primary_name,
            "secondary_name": self.wedding.secondary_name,
            "primary_short_name": self.wedding.primary_short_name,
            "secondary_short_name": self.wedding.secondary_short_name,
            "main_date": self.wedding.main_date.isoformat(),
            "city": self.wedding.city,
            "country": self.wedding.country,
            "slug": self.wedding.slug,
            "cover_message": self.wedding.cover_message,
            "invitation_message": self.wedding.invitation_message,
            "cover_image-clear": "on",
        })
        self.assertRedirects(response, url)
        self.wedding.refresh_from_db()
        self.assertFalse(self.wedding.cover_image)

    def test_invitation_is_the_first_workspace_tab(self) -> None:
        response = self.client.get(reverse("weddings:preview", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pré-visualização do convite")
        self.assertContains(response, "?embedded=1")
        self.assertContains(response, "invitation-device")
        self.assertContains(response, "O scroll fica dentro do telemóvel")
        self.assertEqual(response.context["preview_sections"], ["Capa", "Convite", "RSVP"])
        self.assertContains(response, ">Convite</a>", html=False)
        self.assertContains(response, ">Detalhes do evento</a>", html=False)
        self.assertContains(response, ">Convidados</a>", html=False)
        self.assertNotContains(response, ">Momentos</a>", html=False)
        self.assertContains(response, ">Programa</a>", html=False)
        self.assertNotContains(response, ">Locais</a>", html=False)
        self.assertContains(
            response,
            f'href="{reverse("subscriptions:detail", args=[self.wedding.pk])}"',
            html=False,
        )

    def test_setup_progress_grows_with_completed_items(self) -> None:
        before = self.client.get(reverse("weddings:setup", args=[self.wedding.pk]))
        create_event(self.wedding, location=create_location(self.wedding))
        after = self.client.get(reverse("weddings:setup", args=[self.wedding.pk]))
        self.assertGreater(after.context["progress"], before.context["progress"])
        self.assertTrue(after.context["can_publish"])

    def test_publish_flow_reports_missing_requirements(self) -> None:
        response = self.client.post(
            reverse("weddings:publish", args=[self.wedding.pk]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.status, "draft")
        self.assertContains(response, "Falta completar")

    def test_wedding_list_only_shows_accessible_weddings(self) -> None:
        other = create_wedding(create_user("outra@example.com"))
        response = self.client.get(reverse("weddings:list"))
        weddings = list(response.context["weddings"])
        self.assertIn(self.wedding, weddings)
        self.assertNotIn(other, weddings)

    def test_wedding_list_embeds_the_template_carousel(self) -> None:
        category = create_category()
        response = self.client.get(reverse("weddings:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-template-carousel")
        self.assertContains(response, f'id="templates-{category.code}"')
        self.assertContains(response, "templates-gallery.css?v=20260731.2")
        self.assertContains(response, "template-carousel.js?v=20260731.2")
        self.assertGreater(len(response.context["categories"][0].template_options), 0)


class DesignViewTests(TestCase):
    """Galeria de templates de convite."""

    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)
        self.url = reverse("weddings:design", args=[self.wedding.pk])

    def test_gallery_lists_every_template(self) -> None:
        from templates_manager import registry

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["templates"]), len(registry.all_templates()))
        self.assertGreaterEqual(len(registry.all_templates()), 10)
        for template in registry.all_templates():
            self.assertContains(response, template.name)

    def test_selected_template_has_a_visible_selected_state(self) -> None:
        response = self.client.get(self.url)
        self.assertContains(response, 'template-choice is-selected')
        self.assertContains(response, 'template-card__selected-label')
        self.assertNotContains(response, 'id="apply-template-button"')
        self.assertContains(
            response,
            "Aplicar",
            count=len(response.context["templates"]) - 1,
        )
        self.assertNotContains(response, "Aplicar template")
        self.assertNotContains(response, "Guardar aspecto")
        self.assertNotContains(response, "Cores, capa e música")
        self.assertNotContains(response, "Template escolhido")
        self.assertNotContains(response, "Cor principal")
        self.assertNotContains(response, "Cor secundária")
        self.assertNotContains(response, 'id="id_cover_image"', html=False)
        self.assertNotContains(response, 'id="id_invitation_music"', html=False)
        self.assertEqual(
            response.content.count(b'class="template-choice '),
            len(response.context["templates"]),
        )

    def _payload(self, **overrides) -> dict:
        data = {"selected_template": "capulana"}
        data.update(overrides)
        return data

    def test_choosing_a_template_is_saved(self) -> None:
        response = self.client.post(self.url, data=self._payload())
        self.assertRedirects(response, self.url)
        self.wedding.refresh_from_db()
        from templates_manager import registry
        template = registry.get_template("capulana")
        self.assertEqual(self.wedding.selected_template, "capulana")
        self.assertEqual(self.wedding.primary_color, template.primary)
        self.assertEqual(self.wedding.secondary_color, template.secondary)

    def test_manual_colours_are_ignored_when_a_template_is_applied(self) -> None:
        response = self.client.post(self.url, data=self._payload(
            primary_color="#FFFFFF",
            secondary_color="#000000",
        ))
        self.assertRedirects(response, self.url)
        self.wedding.refresh_from_db()
        from templates_manager import registry
        template = registry.get_template("capulana")
        self.assertEqual(self.wedding.primary_color, template.primary)
        self.assertEqual(self.wedding.secondary_color, template.secondary)

    def test_unknown_template_code_is_rejected(self) -> None:
        response = self.client.post(self.url, data=self._payload(selected_template="pirata"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escolha um dos templates disponíveis")
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.selected_template, "carta-selada")

    def test_member_without_design_permission_cannot_open_it(self) -> None:
        other = create_user("comissao@example.com")
        add_member(self.wedding, other, role=WeddingRole.RECEPTIONIST)
        self.client.login(email=other.email, password=DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class TeamViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = create_user()
        self.helper = create_user("comissao@example.com")
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_owner_adds_a_member_by_email(self) -> None:
        response = self.client.post(
            reverse("weddings:team", args=[self.wedding.pk]),
            data={"email": self.helper.email, "role": WeddingRole.COMMITTEE, "notes": ""},
        )
        self.assertRedirects(response, reverse("weddings:team", args=[self.wedding.pk]))
        self.assertTrue(
            WeddingMember.objects.filter(wedding=self.wedding, user=self.helper).exists()
        )

    def test_unknown_email_is_rejected_with_a_clear_message(self) -> None:
        response = self.client.post(
            reverse("weddings:team", args=[self.wedding.pk]),
            data={"email": "ninguem@example.com", "role": WeddingRole.COMMITTEE},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não existe nenhuma conta com este email")

    def test_owner_membership_cannot_be_removed(self) -> None:
        membership = WeddingMember.objects.get(wedding=self.wedding, user=self.owner)
        self.client.post(
            reverse("weddings:team_remove", args=[self.wedding.pk, membership.pk])
        )
        membership.refresh_from_db()
        self.assertTrue(membership.is_active)

    def test_permissions_can_be_narrowed_for_a_member(self) -> None:
        membership = add_member(self.wedding, self.helper, role=WeddingRole.COMMITTEE)
        self.client.post(
            reverse("weddings:team_edit", args=[self.wedding.pk, membership.pk]),
            data={
                "role": WeddingRole.VIEWER,
                "can_view_reports": "on",
                "notes": "Apenas consulta",
            },
        )
        membership.refresh_from_db()
        self.assertEqual(membership.role, WeddingRole.VIEWER)
        self.assertFalse(membership.can_manage_guests)
        self.assertTrue(membership.can_view_reports)

class WeddingGalleryViewTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user(email="galeria@example.com")
        self.wedding = create_wedding(owner=self.user)
        self.client.login(email=self.user.email, password=DEFAULT_PASSWORD)
        self.url = reverse("weddings:gallery", args=[self.wedding.pk])

    def test_gallery_tab_is_available_to_the_couple(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Galeria do convite")
        self.assertContains(response, "Adicionar fotografias")

    def test_upload_adds_a_photo_to_the_wedding(self) -> None:
        # PNG 1x1 válido; mantém o teste pequeno e independente de fixtures.
        image = SimpleUploadedFile(
            "memoria.png",
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            ),
            content_type="image/png",
        )
        response = self.client.post(self.url, {"photos": image})
        self.assertRedirects(response, self.url)
        self.assertEqual(self.wedding.gallery_photos.count(), 1)

    def test_caption_and_visibility_can_be_updated(self) -> None:
        photo = WeddingGalleryPhoto.objects.create(
            wedding=self.wedding,
            external_url="https://example.com/couple.jpg",
        )
        response = self.client.post(
            reverse("weddings:gallery_photo_update", args=[self.wedding.pk, photo.pk]),
            {"caption": "O começo da nossa história"},
        )
        self.assertRedirects(response, self.url)
        photo.refresh_from_db()
        self.assertEqual(photo.caption, "O começo da nossa história")
        self.assertFalse(photo.is_visible)

    def test_photo_from_another_wedding_is_never_accessible(self) -> None:
        other = create_wedding(owner=create_user(email="outra@example.com"))
        photo = WeddingGalleryPhoto.objects.create(
            wedding=other,
            external_url="https://example.com/private.jpg",
        )
        response = self.client.post(
            reverse("weddings:gallery_photo_delete", args=[self.wedding.pk, photo.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WeddingGalleryPhoto.objects.filter(pk=photo.pk).exists())
