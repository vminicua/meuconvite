from django.test import TestCase
from django.urls import reverse

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
