from django.test import SimpleTestCase

from weddings.forms import WeddingSettingsForm, WeddingStoryForm
from weddings.models import Wedding


class SMSInvitationMessageFieldTests(SimpleTestCase):
    def test_crlf_line_breaks_count_as_one_character(self):
        field = WeddingSettingsForm.base_fields["sms_invitation_message"]
        browser_value = ("x" * 83) + "\r\n" + ("y" * 5) + "\r\n{link}\r\nz\r\nq"

        cleaned = field.clean(browser_value)

        self.assertEqual(len(browser_value), 104)
        self.assertEqual(len(cleaned), 100)
        self.assertNotIn("\r", cleaned)


class WeddingStoryFormTests(SimpleTestCase):
    def test_visible_story_requires_text_or_quote(self):
        form = WeddingStoryForm(
            data={
                "show_story": "on",
                "story_title": "A nossa história",
                "story": "",
                "story_verse": "",
                "story_verse_reference": "",
            },
            instance=Wedding(),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Escreva a história", str(form.non_field_errors()))

    def test_story_can_be_disabled_without_erasing_content(self):
        form = WeddingStoryForm(
            data={
                "story_title": "A nossa história",
                "story": "Um encontro que mudou tudo.",
                "story_verse": "",
                "story_verse_reference": "",
            },
            instance=Wedding(),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["show_story"])
        self.assertEqual(form.cleaned_data["story"], "Um encontro que mudou tudo.")
