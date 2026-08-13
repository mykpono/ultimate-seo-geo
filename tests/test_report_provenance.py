"""A report must say where its numbers came from, and stock advice must be
domain-neutral.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import backlink_analyzer  # noqa: E402
import readability  # noqa: E402


# --- backlink_analyzer provenance -------------------------------------------

@pytest.fixture
def sample_report():
    backlinks = backlink_analyzer.generate_sample_data("https://example.com")
    return backlink_analyzer.run_analysis(
        backlinks, target_url="https://example.com", data_source="sample"
    )


def test_sample_report_declares_itself_as_sample(sample_report):
    assert sample_report["data_source"] == "sample"
    assert sample_report["is_sample_data"] is True


def test_real_source_is_not_flagged_as_sample():
    backlinks = backlink_analyzer.generate_sample_data("https://example.com")
    report = backlink_analyzer.run_analysis(
        backlinks, target_url="https://example.com", data_source="csv"
    )

    assert report["data_source"] == "csv"
    assert report["is_sample_data"] is False


def test_provenance_survives_json_serialization(sample_report):
    """stderr warnings do not travel; the payload has to carry it."""
    import json

    round_tripped = json.loads(json.dumps(sample_report, default=str))

    assert round_tripped["is_sample_data"] is True


def test_provenance_defaults_to_unknown_not_to_a_real_source():
    backlinks = backlink_analyzer.generate_sample_data("https://example.com")
    report = backlink_analyzer.run_analysis(backlinks, target_url="https://example.com")

    assert report["data_source"] == "unknown"
    assert report["is_sample_data"] is False


# --- readability stock recommendations --------------------------------------

LEAKED_TERMS = [
    "ethical hacking",
    "Wi-Fi security",
    "Active Directory",
    "malware analysis",
    "Red-Team",
    "AD Attack Paths",
]


def _all_recommendation_text():
    source = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "readability.py"
    )
    with open(source, encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("term", LEAKED_TERMS)
def test_stock_recommendations_are_domain_neutral(term):
    """These came from one client's site and shipped into every report."""
    assert term.lower() not in _all_recommendation_text().lower(), (
        f"{term!r} is a leftover from a specific client's copy and would "
        f"appear verbatim in an unrelated client's report"
    )


def test_the_fallback_recommendations_still_exist():
    """Neutralising the copy must not delete the feature."""
    text = _all_recommendation_text()

    assert "sentence_rewrites" in text
    assert "who you help" in text
