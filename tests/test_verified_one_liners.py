"""Regression tests for three independent one-line defects.

Each test fails against the code as it stood before the accompanying fix.
"""

import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import drift_monitor  # noqa: E402
import entity_checker  # noqa: E402
import hreflang_checker  # noqa: E402


# --- drift_monitor: robots-meta severity was a tautology --------------------

def _robots_change(old, new):
    changes = drift_monitor._apply_rules({"robots": old}, {"robots": new})
    return next(c for c in changes if c["rule"] == 3)


def test_noindex_addition_is_critical():
    assert _robots_change("index,follow", "noindex,follow")["severity"] == "critical"


def test_benign_robots_change_is_not_critical():
    """`max-image-preview:large` is Google's own recommendation, not an outage."""
    change = _robots_change(
        "index,follow", "index,follow,max-image-preview:large"
    )

    assert change["severity"] == "warning"
    assert change["severity"] in drift_monitor.SEVERITY_ORDER


# --- hreflang: LA is Laos, not "Latin America" ------------------------------

def test_la_is_a_valid_iso_region():
    assert "LA" in hreflang_checker.VALID_REGION_CODES
    assert "LA" not in hreflang_checker.COMMON_REGION_MISTAKES


def test_lo_la_validates_clean():
    result = hreflang_checker.validate_lang_code("lo-LA")

    assert result["valid"] is True, result
    assert result["region"] == "LA"


def test_genuine_region_mistakes_still_flagged():
    assert hreflang_checker.validate_lang_code("en-UK")["valid"] is False
    assert hreflang_checker.validate_lang_code("en-EU")["valid"] is False


# --- entity_checker: phone detection matched whitespace ---------------------

_has_phone = entity_checker.has_visible_phone


def test_whitespace_is_not_a_phone_number():
    """The old class included \\s, so 7 spaces satisfied it on every page."""
    assert _has_phone("Contact       us today") is False


def test_prose_without_digits_is_not_a_phone_number():
    assert _has_phone("We are open Monday through Friday.") is False


def test_real_phone_numbers_are_still_detected():
    for number in ("(512) 555-0134", "+1 512 555 0134", "512-555-0134"):
        assert _has_phone(f"Call {number} today") is True, number


def test_nap_check_reports_a_missing_phone():
    """End to end through check_nap_consistency, which the bug made dead."""
    soup = BeautifulSoup("<p>Contact       us today</p>", "html.parser")
    entities = [{"type": "LocalBusiness"}]

    issues = entity_checker.check_nap_consistency(soup, entities)

    assert any("phone" in str(i).lower() for i in issues), (
        "a LocalBusiness page with no phone number must raise a NAP issue; "
        f"got {issues}"
    )
    assert re.search(r"[\+]?[\d\-\(\)\s]{7,15}", soup.get_text(separator=" ")), (
        "the old expression matched this whitespace-only text, which is why "
        "the check was dead"
    )
