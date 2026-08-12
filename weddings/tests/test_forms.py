from django.test import SimpleTestCase

from weddings.forms import WeddingSettingsForm


class SMSInvitationMessageFieldTests(SimpleTestCase):
    def test_crlf_line_breaks_count_as_one_character(self):
        field = WeddingSettingsForm.base_fields["sms_invitation_message"]
        browser_value = ("x" * 83) + "\r\n" + ("y" * 5) + "\r\n{link}\r\nz\r\nq"

        cleaned = field.clean(browser_value)

        self.assertEqual(len(browser_value), 104)
        self.assertEqual(len(cleaned), 100)
        self.assertNotIn("\r", cleaned)
