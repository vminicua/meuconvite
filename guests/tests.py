from django.test import TestCase
from django.urls import reverse
from events.models import WeddingEvent

from weddings.tests.factories import DEFAULT_PASSWORD, create_user, create_wedding

from .models import Guest


class GuestViewTests(TestCase):
    def setUp(self):
        self.owner = create_user()
        self.wedding = create_wedding(self.owner)
        self.client.login(email=self.owner.email, password=DEFAULT_PASSWORD)

    def test_owner_can_add_and_edit_a_guest(self):
        url = reverse("guests:list", args=[self.wedding.pk])
        response = self.client.post(url, {"full_name": "Ana Mucavele", "phone": "841234567", "email": "", "party_size": 2, "notes": "Família"})
        self.assertRedirects(response, url)
        guest = Guest.objects.get(wedding=self.wedding)
        self.assertEqual(guest.party_size, 2)
        response = self.client.post(reverse("guests:edit", args=[self.wedding.pk, guest.pk]), {"full_name": "Ana Mucavele", "phone": "841234567", "email": "ana@example.com", "party_size": 3, "notes": ""})
        self.assertRedirects(response, url)
        guest.refresh_from_db()
        self.assertEqual(guest.party_size, 3)

    def test_guest_is_soft_removed(self):
        guest = Guest.objects.create(wedding=self.wedding, full_name="João")
        self.client.post(reverse("guests:remove", args=[self.wedding.pk, guest.pk]))
        guest.refresh_from_db()
        self.assertFalse(guest.is_active)

    def test_guest_composer_is_collapsed_and_table_has_management_tools(self):
        guest = Guest.objects.create(wedding=self.wedding, full_name="Valdimiro")
        response = self.client.get(reverse("guests:list", args=[self.wedding.pk]))
        self.assertContains(response, 'class="collapse" id="guestComposer"')
        self.assertContains(response, "Exportar CSV")
        self.assertContains(response, "data-copy-link")
        self.assertContains(response, "data-share-link")
        self.assertContains(response, 'id="shareInvitationModal"')
        self.assertContains(response, "Partilhar no WhatsApp")
        self.assertContains(response, "Enviar por email")
        self.assertContains(response, "data-table-search")
        self.assertContains(response, f'data-bs-target="#edit-{guest.pk}"')
        self.assertContains(response, f'id="edit-{guest.pk}"')
        self.assertContains(response, 'data-action-feedback')
        self.assertNotContains(response, f'href="{reverse("guests:edit", args=[self.wedding.pk, guest.pk])}"')

    def test_guest_can_be_limited_to_selected_programme_items(self):
        first = WeddingEvent.objects.create(wedding=self.wedding, name="Cerimónia")
        second = WeddingEvent.objects.create(wedding=self.wedding, name="Festa")
        url = reverse("guests:list", args=[self.wedding.pk])
        self.client.post(url, {
            "full_name": "Convidado limitado", "party_size": 1,
            "allowed_events": [first.pk],
        })
        guest = Guest.objects.get(full_name="Convidado limitado")
        self.assertEqual(list(guest.allowed_events.all()), [first])
        response = self.client.get(reverse("guest_invitation", args=[guest.invitation_token]))
        self.assertContains(response, "Cerimónia")
        self.assertNotContains(response, "Festa")

    def test_guest_can_confirm_from_individual_invitation(self):
        guest = Guest.objects.create(wedding=self.wedding, full_name="Ana")
        url = reverse("guest_invitation", args=[guest.invitation_token])
        response = self.client.post(url, {"rsvp": "confirmed"})
        self.assertRedirects(response, url)
        guest.refresh_from_db()
        self.assertEqual(guest.rsvp_status, "confirmed")
        self.assertIsNotNone(guest.responded_at)
