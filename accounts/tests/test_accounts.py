from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from audit.models import AuditAction, AuditLog
from weddings.tests.factories import DEFAULT_PASSWORD, create_user

User = get_user_model()


class UserModelTests(TestCase):
    def test_email_is_normalised_and_lowercased(self) -> None:
        user = User.objects.create_user(email="Noiva@Example.COM", password=DEFAULT_PASSWORD)
        self.assertEqual(user.email, "noiva@example.com")

    def test_email_is_the_login_identifier(self) -> None:
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertEqual(User.REQUIRED_FIELDS, [])

    def test_user_without_email_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password=DEFAULT_PASSWORD)

    def test_superuser_flags(self) -> None:
        admin = User.objects.create_superuser(
            email="admin@example.com", password=DEFAULT_PASSWORD
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_email_verified)

    def test_display_name_and_initials(self) -> None:
        user = create_user()
        self.assertEqual(user.display_name, "Natércia Matola")
        self.assertEqual(user.initials, "NM")

    def test_password_is_hashed(self) -> None:
        user = create_user()
        self.assertNotEqual(user.password, DEFAULT_PASSWORD)
        self.assertTrue(user.check_password(DEFAULT_PASSWORD))


class SignupTests(TestCase):
    def _signup(self, **overrides):
        data = {
            "first_name": "Natércia",
            "last_name": "Matola",
            "email": "nova@example.com",
            "phone": "841234567",
            "password1": "CasamentoSeguro2026",
            "password2": "CasamentoSeguro2026",
        }
        data.update(overrides)
        return self.client.post(reverse("account_signup"), data=data)

    def test_signup_creates_the_account_with_the_extra_fields(self) -> None:
        response = self._signup()
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="nova@example.com")
        self.assertEqual(user.first_name, "Natércia")
        self.assertEqual(user.phone, "+258841234567")

    def test_signup_signs_the_user_in_immediately(self) -> None:
        """Verificar o email não pode bloquear a entrada na aplicação."""
        response = self._signup()
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(response, reverse("weddings:list"))

    def test_signup_still_sends_the_confirmation_email(self) -> None:
        self._signup()
        self.assertEqual(len(mail.outbox), 1)

    def test_email_must_be_unique(self) -> None:
        create_user("nova@example.com")
        self.client.post(
            reverse("account_signup"),
            data={
                "first_name": "Outra",
                "last_name": "Pessoa",
                "email": "nova@example.com",
                "password1": "CasamentoSeguro2026",
                "password2": "CasamentoSeguro2026",
            },
        )
        self.assertEqual(User.objects.filter(email="nova@example.com").count(), 1)


class LoginTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user()

    def test_login_with_email(self) -> None:
        response = self.client.post(
            reverse("account_login"),
            data={"login": self.user.email, "password": DEFAULT_PASSWORD},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_is_recorded_in_the_audit_trail(self) -> None:
        self.client.post(
            reverse("account_login"),
            data={"login": self.user.email, "password": DEFAULT_PASSWORD},
        )
        self.assertTrue(
            AuditLog.objects.filter(action=AuditAction.LOGIN, user=self.user).exists()
        )

    def test_login_works_even_with_an_unverified_email(self) -> None:
        unverified = create_user("porverificar@example.com", is_email_verified=False)
        self.client.post(
            reverse("account_login"),
            data={"login": unverified.email, "password": DEFAULT_PASSWORD},
        )
        self.assertIn("_auth_user_id", self.client.session)

    def test_wrong_password_does_not_authenticate(self) -> None:
        self.client.post(
            reverse("account_login"),
            data={"login": self.user.email, "password": "errada"},
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_sends_an_email(self) -> None:
        response = self.client.post(
            reverse("account_reset_password"), data={"email": self.user.email}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn(DEFAULT_PASSWORD, mail.outbox[0].body)

    def test_password_reset_does_not_reveal_unknown_accounts(self) -> None:
        response = self.client.post(
            reverse("account_reset_password"), data={"email": "ninguem@example.com"}
        )
        self.assertEqual(response.status_code, 302)


class ProfileTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user()
        self.client.login(email=self.user.email, password=DEFAULT_PASSWORD)

    def test_profile_requires_login(self) -> None:
        self.client.logout()
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)

    def test_profile_can_be_updated(self) -> None:
        response = self.client.post(
            reverse("accounts:profile"),
            data={
                "first_name": "Natércia",
                "last_name": "Cossa",
                "phone": "0841234567",
                "preferred_language": "pt",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Cossa")
        self.assertEqual(self.user.phone, "+258841234567")

    def test_profile_update_is_audited(self) -> None:
        self.client.post(
            reverse("accounts:profile"),
            data={
                "first_name": "Natércia",
                "last_name": "Cossa",
                "phone": "",
                "preferred_language": "pt",
            },
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.UPDATE, model_name="accounts.User"
            ).exists()
        )
