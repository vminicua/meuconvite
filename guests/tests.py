from datetime import timedelta
from unittest.mock import patch
from io import BytesIO

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from events.models import WeddingEvent

from weddings.tests.factories import DEFAULT_PASSWORD, create_plan, create_user, create_wedding

from .models import DeliveryStatus, Guest, InvitationDelivery


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
        self.assertContains(response, "Exportar Excel")
        self.assertContains(response, "Todos")
        self.assertContains(response, "Ord.")
        self.assertContains(response, "data-copy-link")
        self.assertContains(response, "data-share-link")
        self.assertContains(response, 'id="shareInvitationModal"')
        self.assertContains(response, "Partilhar no WhatsApp")
        self.assertContains(response, "Enviar por email")
        self.assertContains(response, "data-table-search")
        self.assertContains(response, f'data-bs-target="#edit-{guest.pk}"')
        self.assertContains(response, f'data-bs-target="#send-{guest.pk}"')
        self.assertContains(response, "Enviar convite por SMS ou WhatsApp")
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

    def test_guests_over_subscription_limit_are_saved_but_disabled(self):
        for number in range(20):
            Guest.objects.create(wedding=self.wedding, full_name=f"Convidado {number:02}")

        url = reverse("guests:list", args=[self.wedding.pk])
        response = self.client.post(
            url,
            {"full_name": "Convidado excedente", "party_size": 1},
            follow=True,
        )

        extra = Guest.objects.get(full_name="Convidado excedente")
        self.assertContains(response, "guest-row--disabled")
        self.assertContains(response, f"Subscrever para activar {extra.full_name}")
        self.assertNotContains(response, f'data-bs-target="#qr-{extra.pk}"')
        self.assertEqual(
            self.client.get(reverse("guest_invitation", args=[extra.invitation_token])).status_code,
            404,
        )

    def test_upgrade_automatically_enables_the_next_guests(self):
        from subscriptions import services

        create_plan()
        services.ensure_subscription(self.wedding)
        guests = [
            Guest.objects.create(wedding=self.wedding, full_name=f"Convidado {number:02}")
            for number in range(21)
        ]
        self.wedding.subscription.guest_allowance = 21
        self.wedding.subscription.save(update_fields=["guest_allowance", "updated_at"])

        response = self.client.get(
            reverse("guest_invitation", args=[guests[-1].invitation_token])
        )
        self.assertEqual(response.status_code, 200)

    def test_excel_export_returns_a_real_xlsx_file(self):
        Guest.objects.create(wedding=self.wedding, full_name="Ana Mucavele")
        response = self.client.get(reverse("guests:export_excel", args=[self.wedding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertTrue(response.content.startswith(b"PK"))

    def test_enabled_guests_are_listed_before_disabled_guests(self):
        for number in range(19):
            Guest.objects.create(wedding=self.wedding, full_name=f"Convidado {number:02}")
        enabled = Guest.objects.create(wedding=self.wedding, full_name="Zúlia Activa")
        disabled = Guest.objects.create(wedding=self.wedding, full_name="Ana Bloqueada")
        Guest.objects.filter(pk=enabled.pk).update(created_at=timezone.now() - timedelta(days=1))
        Guest.objects.filter(pk=disabled.pk).update(created_at=timezone.now() + timedelta(days=1))

        response = self.client.get(reverse("guests:list", args=[self.wedding.pk]))

        rows = response.context["guest_rows"]
        ordered_names = [row["guest"].full_name for row in rows]
        self.assertLess(ordered_names.index(enabled.full_name), ordered_names.index(disabled.full_name))
        self.assertTrue(next(row for row in rows if row["guest"] == enabled)["is_enabled"])
        self.assertFalse(next(row for row in rows if row["guest"] == disabled)["is_enabled"])
        self.assertContains(response, 'data-enabled="0"')

    @patch("guests.messaging._client")
    def test_owner_can_open_pre_filled_whatsapp_invitation(self, client_factory):
        guest = Guest.objects.create(
            wedding=self.wedding, full_name="Ana Mucavele", phone="840297715"
        )

        response = self.client.post(
            reverse("guests:send_invitation", args=[self.wedding.pk, guest.pk]),
            {"channel": "whatsapp"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("https://wa.me/258840297715?text="))
        self.assertIn("convite", response.url.lower())
        self.assertIn(guest.invitation_token, response.url)
        client_factory.assert_not_called()
        self.assertFalse(InvitationDelivery.objects.filter(guest=guest).exists())

    @patch("guests.messaging._client")
    def test_disabled_guest_cannot_be_sent(self, client_factory):
        from subscriptions.services import enabled_guest_ids

        guests = [
            Guest.objects.create(wedding=self.wedding, full_name=f"Convidado {number:02}")
            for number in range(21)
        ]
        enabled = enabled_guest_ids(self.wedding)
        disabled = next(guest for guest in guests if guest.pk not in enabled)
        response = self.client.post(
            reverse("guests:send_invitation", args=[self.wedding.pk, disabled.pk]),
            {"channel": "sms"},
        )
        self.assertRedirects(response, reverse("guests:list", args=[self.wedding.pk]))
        client_factory.assert_not_called()
        self.assertFalse(InvitationDelivery.objects.exists())

    def test_sms_invitation_is_ascii_and_one_segment(self):
        from guests.messaging import invitation_message

        guest = Guest.objects.create(
            wedding=self.wedding, full_name="Ercília Tembe", phone="840297715"
        )
        body = invitation_message(
            guest,
            "https://meuconvite.co.mz/convite/abc123/",
            "sms",
        )

        self.assertIn("Ercilia", body)
        self.assertIn("*O Nosso Casamento*", body)
        self.assertIn("Sera uma alegria celebrar este dia contigo.", body)
        self.assertIn("https://meuconvite.co.mz/convite/abc123/", body)
        self.assertTrue(body.isascii())
        self.assertLessEqual(len(body), 160)

    def test_new_guest_has_four_character_invitation_code(self):
        first = Guest.objects.create(wedding=self.wedding, full_name="Ana")
        second = Guest.objects.create(wedding=self.wedding, full_name="Bento")

        self.assertEqual(len(first.invitation_token), 4)
        self.assertEqual(len(second.invitation_token), 4)
        self.assertNotEqual(first.invitation_token, second.invitation_token)

    def test_invitation_exposes_whatsapp_jpeg_and_default_music(self):
        guest = Guest.objects.create(wedding=self.wedding, full_name="Ana")

        invitation = self.client.get(reverse("guest_invitation", args=[guest.invitation_token]))
        image_url = reverse("guest_invitation_share_image", args=[guest.invitation_token])
        self.assertContains(invitation, image_url)
        self.assertContains(invitation, reverse("invitation_default_music"))

        image_response = self.client.get(image_url)
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response["Content-Type"], "image/jpeg")
        with Image.open(BytesIO(image_response.content)) as image:
            self.assertEqual(image.size, (1200, 630))

        audio_response = self.client.get(
            reverse("invitation_default_music"), HTTP_RANGE="bytes=0-1023"
        )
        self.assertEqual(audio_response.status_code, 206)
        self.assertEqual(audio_response["Content-Type"], "audio/wav")
        self.assertEqual(audio_response["Content-Length"], "1024")
        self.assertTrue(audio_response["Content-Range"].startswith("bytes 0-1023/"))

    def test_sms_settings_reject_unicode(self):
        from weddings.forms import WeddingSettingsForm

        data = {
            field.name: getattr(self.wedding, field.name)
            for field in self.wedding._meta.fields
            if field.name in WeddingSettingsForm.Meta.fields
        }
        data["sms_invitation_message"] = "Olá {nome}: {link}"
        form = WeddingSettingsForm(data=data, instance=self.wedding)

        self.assertFalse(form.is_valid())
        self.assertIn("sms_invitation_message", form.errors)

    @override_settings(SITE_BASE_URL="https://meuconvite.example", TWILIO_AUTH_TOKEN="secret")
    def test_twilio_status_callback_is_signed_and_updates_delivery(self):
        from twilio.request_validator import RequestValidator

        guest = Guest.objects.create(wedding=self.wedding, full_name="Ana", phone="+258840000000")
        delivery = InvitationDelivery.objects.create(
            wedding=self.wedding,
            guest=guest,
            channel="sms",
            destination=guest.phone,
            message_body="Convite",
            provider_sid="SM123",
            status=DeliveryStatus.QUEUED,
        )
        url = reverse("twilio_message_status")
        callback_url = f"https://meuconvite.example{url}"
        payload = {"MessageSid": "SM123", "MessageStatus": "delivered", "ErrorCode": ""}
        signature = RequestValidator("secret").compute_signature(callback_url, payload)

        response = self.client.post(url, payload, HTTP_X_TWILIO_SIGNATURE=signature)

        self.assertEqual(response.status_code, 204)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.DELIVERED)

    @override_settings(SITE_BASE_URL="https://meuconvite.example", TWILIO_AUTH_TOKEN="secret")
    def test_twilio_status_callback_rejects_invalid_signature(self):
        response = self.client.post(
            reverse("twilio_message_status"),
            {"MessageSid": "SM123", "MessageStatus": "delivered"},
            HTTP_X_TWILIO_SIGNATURE="invalid",
        )
        self.assertEqual(response.status_code, 403)
