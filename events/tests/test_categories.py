"""Tipos de evento e campos personalizados do programa."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from events.models import EventCategory, ScheduleItem
from weddings.tests.factories import (
    DEFAULT_PASSWORD,
    create_category,
    create_schedule_item,
    create_user,
    create_wedding,
)


class EventCategoryTests(TestCase):
    def test_two_name_types_require_a_second_label(self) -> None:
        category = EventCategory(
            code="casamento", name="Casamento", uses_two_names=True, secondary_label=""
        )
        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_field_schema_is_validated(self) -> None:
        category = EventCategory(
            code="teste",
            name="Teste",
            field_schema=[{"label": "Sem chave"}],
        )
        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_unsupported_field_type_is_rejected(self) -> None:
        category = EventCategory(
            code="teste",
            name="Teste",
            field_schema=[{"key": "cor", "label": "Cor", "type": "colorpicker"}],
        )
        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_extra_fields_are_normalised(self) -> None:
        category = create_category(
            code="aniversario",
            name="Aniversário",
            uses_two_names=False,
            secondary_label="",
            field_schema=[{"key": "idade", "label": "Idade"}, "lixo", {"label": "sem chave"}],
        )
        fields = category.extra_fields
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["type"], "text")
        self.assertFalse(fields[0]["required"])

    def test_one_name_types_display_a_single_name(self) -> None:
        category = create_category(
            code="aniversario", name="Aniversário", uses_two_names=False, secondary_label=""
        )
        wedding = create_wedding(
            category=category,
            primary_name="Amélia Nhaca",
            primary_short_name="Amélia",
            secondary_name="",
            secondary_short_name="",
        )
        self.assertEqual(wedding.display_names, "Amélia")
        self.assertEqual(wedding.category_name, "Aniversário")

    def test_seed_command_creates_the_types(self) -> None:
        from django.core.management import call_command

        call_command("seed_event_categories", verbosity=0)
        self.assertGreaterEqual(EventCategory.objects.count(), 8)
        self.assertTrue(EventCategory.objects.filter(code="casamento").exists())
        self.assertTrue(EventCategory.objects.filter(code="lobolo").exists())

        # Correr outra vez não duplica nada.
        total = EventCategory.objects.count()
        call_command("seed_event_categories", verbosity=0)
        self.assertEqual(EventCategory.objects.count(), total)


class ScheduleCustomFieldTests(TestCase):
    """Campos que o próprio utilizador acrescenta ao programa."""

    def setUp(self) -> None:
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)
        self.url = reverse("events:schedule", args=[self.wedding.pk])

    def test_adding_a_field(self) -> None:
        response = self.client.post(
            self.url, data={"label": "Responsável", "type": "text"}
        )
        self.assertRedirects(response, self.url)
        self.wedding.refresh_from_db()
        self.assertEqual(
            [field["key"] for field in self.wedding.schedule_fields], ["responsavel"]
        )

    def test_the_key_is_derived_from_the_label(self) -> None:
        self.client.post(self.url, data={"label": "Duração prevista", "type": "text"})
        self.wedding.refresh_from_db()
        self.assertEqual(self.wedding.schedule_fields[0]["key"], "duracao_prevista")

    def test_duplicate_fields_are_rejected(self) -> None:
        self.client.post(self.url, data={"label": "Responsável", "type": "text"})
        response = self.client.post(self.url, data={"label": "Responsável", "type": "text"})
        self.assertContains(response, "Já existe um campo com este nome")
        self.wedding.refresh_from_db()
        self.assertEqual(len(self.wedding.schedule_fields), 1)

    def test_a_choice_field_needs_options(self) -> None:
        response = self.client.post(
            self.url, data={"label": "Espaço", "type": "choice", "choices": ""}
        )
        self.assertContains(response, "Indique as opções")

    def test_the_new_field_appears_in_the_item_form(self) -> None:
        self.client.post(self.url, data={"label": "Responsável", "type": "text"})
        response = self.client.get(
            reverse("events:schedule_create", args=[self.wedding.pk])
        )
        self.assertContains(response, "extra__responsavel")
        self.assertContains(response, "Responsável")

    def test_values_are_saved_and_shown(self) -> None:
        self.client.post(self.url, data={"label": "Responsável", "type": "text"})
        self.client.post(
            reverse("events:schedule_create", args=[self.wedding.pk]),
            data={
                "title": "Corte do bolo",
                "description": "",
                "date": self.wedding.main_date.isoformat(),
                "start_time": "18:30",
                "end_time": "",
                "event": "",
                "location": "",
                "icon": "",
                "is_public": "on",
                "extra__responsavel": "Maria Bila",
            },
        )
        item = ScheduleItem.objects.get(wedding=self.wedding, title="Corte do bolo")
        self.assertEqual(item.extra_data, {"responsavel": "Maria Bila"})

        response = self.client.get(self.url)
        self.assertContains(response, "Maria Bila")

    def test_removing_a_field_also_cleans_the_values(self) -> None:
        self.client.post(self.url, data={"label": "Responsável", "type": "text"})
        item = create_schedule_item(self.wedding, extra_data={"responsavel": "Maria Bila"})

        self.client.post(
            reverse("events:schedule_field_delete", args=[self.wedding.pk, "responsavel"])
        )

        self.wedding.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(self.wedding.schedule_fields, [])
        self.assertEqual(item.extra_data, {})

    def test_another_couple_cannot_add_fields_here(self) -> None:
        stranger = create_user("estranho@example.com")
        self.client.login(email=stranger.email, password=DEFAULT_PASSWORD)
        response = self.client.post(self.url, data={"label": "X", "type": "text"})
        self.assertEqual(response.status_code, 404)
