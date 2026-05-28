from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_page as fetch_page_module  # noqa: E402
import generate_report  # noqa: E402
import content_quality  # noqa: E402
import drift_monitor  # noqa: E402


class FakeResponse:
    def __init__(self, url: str, status_code: int = 200, text: str = "ok", headers: dict | None = None):
        self.url = url
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.is_redirect = status_code in {301, 302, 303, 307, 308}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.calls = 0

    def get(self, *args, **kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response


class FetchPageTests(unittest.TestCase):
    def test_redirect_target_is_safety_checked_before_following(self):
        session = FakeSession(
            [
                FakeResponse(
                    "https://example.com",
                    status_code=302,
                    headers={"Location": "http://127.0.0.1/admin"},
                )
            ]
        )
        with (
            patch("fetch_page.requests.Session", return_value=session),
            patch("url_safety.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]),
        ):
            result = fetch_page_module.fetch_page("https://example.com")

        self.assertIn("URL safety check failed", result["error"])
        self.assertEqual(session.calls, 1)


class ReportMetadataTests(unittest.TestCase):
    def test_recommendation_metadata_defaults_are_falsifiable(self):
        meta = generate_report._recommendation_metadata({"finding": "Missing H1"}, "onpage")

        self.assertIn("dependency", meta)
        self.assertIn("failure_check", meta)
        self.assertIn("leading_indicator", meta)
        self.assertIn("onpage", meta["failure_check"])

    def test_environment_fix_render_includes_metadata_labels(self):
        html = generate_report.render_environment_fixes(
            [
                {
                    "severity": "warning",
                    "title": "No llms.txt found",
                    "reason": "Optionality gap.",
                    "fix": "Add /llms.txt.",
                    "dependency": "Can serve root files.",
                    "failure_check": "File returns 200.",
                    "leading_indicator": "Well-formed file.",
                }
            ]
        )

        self.assertIn("Dependency:", html)
        self.assertIn("Failure check:", html)
        self.assertIn("Leading indicator:", html)


class ContentQualityTests(unittest.TestCase):
    def test_flags_filler_and_citation_gap(self):
        html = """
        <html><body><article>
        <h1>Report</h1><p>In today's digital landscape, research shows 72% of teams need better SEO.</p>
        </article></body></html>
        """
        data = content_quality.analyze_html(html, "https://example.com")

        self.assertLess(data["score"], 100)
        self.assertIn("in today's digital landscape", data["filler_phrases"])
        self.assertGreaterEqual(data["citation_gap"], 1)


class DriftMonitorTests(unittest.TestCase):
    def test_snapshot_extracts_seo_fields(self):
        html = """
        <html><head>
        <title>One</title><meta name="description" content="Desc">
        <link rel="canonical" href="https://example.com/one">
        <script type="application/ld+json">{"@type":"Article"}</script>
        </head><body><h1>Heading</h1><a href="/two">Two</a></body></html>
        """
        snapshot = drift_monitor.extract_snapshot(html, "https://example.com/one", 200)

        self.assertEqual(snapshot["title"], "One")
        self.assertEqual(snapshot["meta_description"], "Desc")
        self.assertEqual(snapshot["schema_count"], 1)
        self.assertEqual(snapshot["internal_link_count"], 1)


if __name__ == "__main__":
    unittest.main()

