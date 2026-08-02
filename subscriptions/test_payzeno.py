from __future__ import annotations

import json
from unittest.mock import patch

from django.test import SimpleTestCase

from .payzeno import PayzenoClient, PayzenoConfigurationError


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _limit):
        return json.dumps(self.payload).encode()


class PayzenoClientTests(SimpleTestCase):
    @patch("subscriptions.payzeno.urlopen")
    def test_checkout_uses_api_key_and_idempotency(self, mocked_open):
        mocked_open.return_value = _Response({"checkout_id": "chk_1"})
        client = PayzenoClient("pk_live_secret")
        client.create_checkout({"amount": 150000}, idempotency_key="mc-123")
        request = mocked_open.call_args.args[0]
        self.assertEqual(request.get_header("Api-key"), "pk_live_secret")
        self.assertEqual(request.get_header("Idempotency-key"), "mc-123")
        self.assertEqual(request.full_url, "https://api.payzeno.io/v1/checkout/sessions")

    @patch("subscriptions.payzeno.urlopen")
    def test_status_uses_server_to_server_endpoint(self, mocked_open):
        mocked_open.return_value = _Response({"status": "paid"})
        result = PayzenoClient("pk_live_secret").checkout_status("chk_1")
        self.assertEqual(result["status"], "paid")
        self.assertTrue(mocked_open.call_args.args[0].full_url.endswith("/chk_1/status"))

    def test_rejects_non_https_base_url(self):
        with self.assertRaises(PayzenoConfigurationError):
            PayzenoClient("pk_live_secret", base_url="http://insecure.example")
