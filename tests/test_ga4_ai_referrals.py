"""ga4_report.py --ai-referrals: AI assistant sessions in GA4.

The GA4 client library is optional and not installed in CI, so these tests pin
the parts that decide correctness without it: which sessionSource values count
as an AI engine, that the regex GA4 evaluates agrees with the Python matcher,
and that the filter names the Data API's real enum member (FULL_REGEXP).
"""

import os
import re
import subprocess
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS)

import ga4_report  # noqa: E402

SAMPLES = [
    ("chatgpt.com", "ChatGPT"),
    ("chat.openai.com", "ChatGPT"),
    ("perplexity.ai", "Perplexity"),
    ("www.perplexity.ai", "Perplexity"),
    ("claude.ai", "Claude"),
    ("gemini.google.com", "Gemini"),
    ("copilot.microsoft.com", "Microsoft Copilot"),
    ("ChatGPT.com", "ChatGPT"),
    ("google", None),
    ("(direct)", None),
    ("openai.com", None),
    ("notchatgpt.com", None),
    ("chatgpt.com.example.net", None),
    ("google.com", None),
    ("", None),
]


@pytest.mark.parametrize("source,engine", SAMPLES)
def test_sources_map_to_the_right_engine(source, engine):
    assert ga4_report.ai_engine_for(source) == engine


@pytest.mark.parametrize("source,engine", SAMPLES)
def test_the_regex_ga4_runs_agrees_with_the_python_matcher(source, engine):
    matched = re.fullmatch(ga4_report.AI_REFERRAL_PATTERN, source.lower()) is not None
    assert matched == (engine is not None), f"{source!r}: GA4 regex and ai_engine_for disagree"


def test_filter_uses_the_data_api_enum_spelling():
    spec = ga4_report.ai_referral_filter_spec()

    assert spec["field_name"] == "sessionSource"
    assert spec["match_type"] == "FULL_REGEXP"


def test_rows_are_tagged_and_summed_per_engine():
    rows = [
        {"sessionSource": "chatgpt.com", "landingPage": "/a", "sessions": 40},
        {"sessionSource": "chatgpt.com", "landingPage": "/b", "sessions": 10},
        {"sessionSource": "www.perplexity.ai", "landingPage": "/a", "sessions": 7},
    ]

    by_engine = ga4_report.summarize_ai_rows(rows)

    assert by_engine == {"ChatGPT": 50, "Perplexity": 7}
    assert [r["ai_engine"] for r in rows] == ["ChatGPT", "ChatGPT", "Perplexity"]


def test_ai_referrals_refuses_to_combine_with_organic_only():
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "ga4_report.py"),
         "--property", "1", "--ai-referrals", "--organic-only"],
        capture_output=True, text=True, timeout=30,
    )

    assert proc.returncode == 2
    assert "cannot be combined" in proc.stderr
