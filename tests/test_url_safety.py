from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from render_page import should_render  # noqa: E402
from url_safety import normalize_url, validate_url  # noqa: E402


class UrlSafetyTests(unittest.TestCase):
    def test_normalizes_scheme_and_trailing_dot(self):
        self.assertEqual(normalize_url("Example.com./a"), "https://example.com/a")

    def test_blocks_loopback_hostname(self):
        with patch("url_safety.socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
            result = validate_url("http://example.com")
        self.assertFalse(result.ok)
        self.assertIn("private/internal", result.reason)

    def test_blocks_decimal_ipv4_literal(self):
        result = validate_url("http://2130706433/", resolve_dns=False)
        self.assertFalse(result.ok)
        self.assertIn("127.0.0.1", result.reason)

    def test_blocks_hex_ipv4_literal(self):
        result = validate_url("http://0x7f000001/", resolve_dns=False)
        self.assertFalse(result.ok)
        self.assertIn("127.0.0.1", result.reason)

    def test_rejects_credentials(self):
        result = validate_url("https://user:pass@example.com", resolve_dns=False)
        self.assertFalse(result.ok)
        self.assertIn("credentials", result.reason)

    def test_allows_public_resolved_ip(self):
        with patch("url_safety.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            result = validate_url("https://example.com")
        self.assertTrue(result.ok)
        self.assertEqual(result.resolved_ips, ["93.184.216.34"])


class RenderDetectionTests(unittest.TestCase):
    def test_detects_next_shell(self):
        html = '<html><body><div id="__next"></div><script src="/_next/static/app.js"></script></body></html>'
        self.assertTrue(should_render(html))

    def test_does_not_render_normal_html(self):
        html = "<html><body><main><h1>Title</h1><p>" + ("Useful copy. " * 250) + "</p></main></body></html>"
        self.assertFalse(should_render(html))


if __name__ == "__main__":
    unittest.main()

