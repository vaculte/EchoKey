"""Tests for the EchoKey API client's TLS configuration."""

import unittest
from unittest import mock

from echokey import api


class TestHttpxVerify(unittest.TestCase):
    @mock.patch.object(api.settings, "ECHOKEY_CA_CERT", "/tmp/rootCA.pem")
    def test_uses_configured_ca_certificate(self):
        self.assertEqual(api._httpx_verify(), "/tmp/rootCA.pem")

    @mock.patch.object(api.settings, "ECHOKEY_CA_CERT", None)
    def test_keeps_default_verification_without_custom_ca(self):
        self.assertIs(api._httpx_verify(), True)


if __name__ == "__main__":
    unittest.main()
