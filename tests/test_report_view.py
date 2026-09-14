"""The HTML report is a view of what the checks found. It must not execute what
the audited site serves, must not dress up a check that never ran as a failure,
and must show every finding and check to a reader without JavaScript (print,
WeasyPrint PDF export).

The previous dashboard inserted page titles, meta descriptions, anchor text,
broken-link URLs and social tag values into the HTML unescaped, scored a
rate-limited PageSpeed run as a red 0, and hid every section behind a
JavaScript toggle that a PDF renderer never runs.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_report  # noqa: E402


def _data(**sections):
    return {
        "url": "https://ex.com/",
        "domain": "ex.com",
        "timestamp": "2026-09-14T09:14:00",
        "environment": {"primary": "Unknown", "runtime": "Unknown", "confidence": "low",
                        "signals": [], "alternatives": []},
        "environment_fixes": [],
        "sections": sections,
    }


def _html(data):
    return generate_report.generate_html(data, generate_report.calculate_overall_score(data))


def _row(html, key):
    match = re.search(r'<tr data-key="%s"[^>]*>.*?</tr>' % re.escape(key), html, re.S)
    return match.group(0) if match else ""


# --- escaping ----------------------------------------------------------------

def test_site_content_is_rendered_as_text():
    data = _data(
        onpage={"title": '<script>alert("t")</script>', "meta_description": "<img src=x onerror=alert(1)>",
                "h1": ["<b>h</b>"], "canonical": "https://ex.com/"},
        broken_links={"summary": {"total": 1, "broken": 1},
                      "broken": [{"url": "https://ex.com/<svg onload=alert(1)>", "status": 404,
                                  "is_internal": True, "anchor_text": "<i>x</i>"}]},
        social={"og_tags": {"og:title": "<script>og</script>"}, "twitter_tags": {}},
    )
    html = _html(data)

    assert '<script>alert("t")</script>' not in html
    assert "<img src=x onerror" not in html
    assert "<svg onload" not in html
    assert "<script>og</script>" not in html
    assert "&lt;script&gt;alert(&quot;t&quot;)&lt;/script&gt;" in html


def test_finding_text_is_escaped():
    data = _data(entity={"issues": [{"severity": "high", "finding": "Bad <iframe src=x>", "fix": "<b>fix</b>"}]})
    html = _html(data)

    assert "<iframe src=x>" not in html
    assert "<b>fix</b>" not in html


# --- honest statuses -----------------------------------------------------------

def test_failed_pagespeed_is_not_measured_not_a_gap():
    row = _row(_html(_data(pagespeed={"error": "Rate limited by Google API."})), "pagespeed")

    assert "Not measured" in row
    assert "Gap" not in row


def test_check_that_never_ran_is_not_scored_as_a_gap():
    row = _row(_html(_data()), "onpage")

    assert "Not run" in row
    assert "Gap" not in row


def test_single_language_site_hreflang_is_not_applicable():
    row = _row(_html(_data(hreflang={"hreflang_tags_found": 0, "implementation_method": "none"})), "hreflang")

    assert "Not applicable" in row


def test_score_bands_map_to_status_chips():
    assert generate_report._check_status("security", {"score": 90}, 90)[1] == "Strong"
    assert generate_report._check_status("security", {"score": 60}, 60)[1] == "Needs work"
    assert generate_report._check_status("security", {"score": 20}, 20)[1] == "Gap"


# --- readable without JavaScript -----------------------------------------------

def test_every_finding_and_check_is_in_the_page_without_javascript():
    data = _data(
        entity={"issues": [{"severity": "high", "finding": "No Wikidata entry", "fix": "Create one"}]},
        internal_links={"issues": ["⚠️ 27 link(s) have no anchor text"]},
    )
    html = _html(data)

    assert 'id="F01"' in html and 'id="F02"' in html
    for key in generate_report.CHECK_LABELS:
        assert f'id="check-{key}"' in html
    # JavaScript hides unselected cards at runtime; the markup itself never does.
    assert re.search(r"<article[^>]*\shidden", html) is None


def test_empty_audit_renders():
    html = _html(_data())

    assert "No findings" in html


# --- severity and design-system vocabulary -------------------------------------

def test_string_issue_severity_is_still_read_from_its_marker():
    data = _data(internal_links={"issues": ["🔴 3 internal pages return 404",
                                            "⚠️ 27 links have no anchor text",
                                            "plain note"]})
    html = _html(data)

    assert '<tr data-key="F01" data-filter="critical"' in html
    assert '<tr data-key="F02" data-filter="warning"' in html
    assert '<tr data-key="F03" data-filter="info"' in html


def test_report_carries_no_emoji():
    data = _data(
        internal_links={"issues": ["⚠️ 27 link(s) have no anchor text", "🔴 3 pages return 404"]},
        security={"https": True, "headers_present": {"HSTS": "max-age=1"}, "headers_missing": {}},
        llms_txt={"exists": False, "quality": {"suggestions": ["💡 Add a description"]}},
    )
    html = _html(data)

    assert not re.search("[\U0001F300-\U0001FAFF✅❌⚠ℹ]", html)
