"""generate_report.py CI mode: a stable JSON summary and exit-code gates.

A CI gate is only useful if it fails because of the site, not the audit
machine. Two things make that true:

  * a check that never ran or errored is left out of the score. It used to
    count as 0 (a rate-limited PageSpeed run cost 13 weight points), or as 100
    (a missing broken-links run scored as "no broken links");
  * a score built from too few measured checks is inconclusive (exit 3), not
    a pass or a fail.

No network: collect_data is replaced with a fixture.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_report as gr  # noqa: E402


def sections(**overrides):
    base = {
        "security": {"score": 90, "issues": ["🔴 Strict-Transport-Security header missing"]},
        "social": {"score": 80},
        "robots": {"status": 200, "sitemaps": ["https://ex.com/sitemap.xml"], "ai_crawler_status": {}},
        "onpage": {"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
        "readability": {"flesch_reading_ease": 65},
        "content_quality": {"score": 70, "issues": ["⚠️ No author byline"]},
        "schema_validation": {"score": 100},
        "sitemap": {"score": 100},
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def data(**overrides):
    return {"url": "https://ex.com/", "timestamp": "2026-09-14T10:00:00", "sections": sections(**overrides)}


def overall(d):
    return gr.calculate_overall_score(d)["overall"]


# --- unmeasured checks ----------------------------------------------------------


def test_the_score_uses_only_measured_checks():
    """8 measured checks: (90*8 + 80*5 + 80*8 + 100*10 + 100*8 + 70*6 + 100*5 + 100*3) / 53 = 90.2."""
    scores = gr.calculate_overall_score(data())

    assert scores["overall"] == 90
    assert scores["measured_categories"] == 8
    assert {"pagespeed", "broken_links", "internal_links", "redirects"} <= set(scores["unmeasured"])


@pytest.mark.parametrize("pagespeed", [{"error": "HTTP 429 rate limited"}, {"strategy": "mobile"}])
def test_an_errored_or_empty_pagespeed_run_does_not_move_the_score(pagespeed):
    assert overall(data(pagespeed=pagespeed)) == overall(data())


def test_a_missing_broken_links_run_is_not_scored_as_perfect():
    missing = gr.calculate_overall_score(data())

    assert missing["raw_categories"]["broken_links"] is None
    assert missing["categories"]["broken_links"] == 0  # the view still gets a number
    assert overall(data(broken_links={"summary": {"total": 10, "broken": 0}})) > missing["overall"]


def test_a_measured_zero_still_counts():
    assert overall(data(security={"score": 0})) < overall(data())


# --- summary contract ------------------------------------------------------------


def test_summary_contract():
    d = data(pagespeed={"error": "HTTP 429"})
    summary = gr.build_summary(d, gr.calculate_overall_score(d))

    assert summary["schema_version"] == 1
    assert (summary["overall"], summary["grade"]) == (90, "A+")
    assert summary["categories"]["pagespeed"] == {
        "label": "Performance (Core Web Vitals)", "score": None, "weight": 13, "status": "Not measured"}
    assert summary["categories"]["security"]["status"] == "Strong"
    assert summary["counts"] == {"critical": 1, "warning": 1, "info": 0}
    assert summary["findings"][0] == {"id": "F01", "severity": "critical", "section": "security",
                                      "finding": "Strict-Transport-Security header missing", "fix": ""}
    json.dumps(summary)  # serialisable as-is


# --- gates -------------------------------------------------------------------------


def summary_of(d):
    return gr.build_summary(d, gr.calculate_overall_score(d))


@pytest.mark.parametrize("kwargs,result,code", [
    ({}, "not set", 0),
    ({"fail_under": 90}, "pass", 0),
    ({"fail_under": 91}, "fail", 1),
    ({"fail_on": "critical"}, "fail", 1),
    ({"fail_on": "warning"}, "fail", 1),
])
def test_gate_results_and_exit_codes(kwargs, result, code):
    gate = gr.evaluate_gate(summary_of(data()), **kwargs)

    assert (gate["result"], gate["exit_code"]) == (result, code)


def test_fail_on_critical_passes_when_only_warnings_exist():
    d = data(security={"score": 90})
    gate = gr.evaluate_gate(summary_of(d), fail_on="critical")

    assert gate["result"] == "pass"


def test_fail_on_warning_fails_on_warnings_alone():
    """The fixture's critical finding would mask a --fail-on warning that ignored warnings."""
    d = data(security={"score": 90})
    gate = gr.evaluate_gate(summary_of(d), fail_on="warning")

    assert (gate["result"], gate["exit_code"]) == ("fail", 1)
    assert "1 finding(s) at or above warning" in gate["reasons"][0]


def test_too_few_measured_checks_make_a_score_gate_inconclusive():
    thin = {"url": "https://ex.com/", "sections": {"security": {"score": 20}, "social": {"score": 20}}}
    gate = gr.evaluate_gate(summary_of(thin), fail_under=70)

    assert (gate["result"], gate["exit_code"]) == ("inconclusive", 3)
    assert "only 2 weighted check(s)" in gate["reasons"][0]


def test_a_critical_finding_fails_even_when_the_score_is_inconclusive():
    thin = {"url": "https://ex.com/", "sections": {"security": {"score": 20, "issues": ["🔴 No HTTPS"]}}}
    gate = gr.evaluate_gate(summary_of(thin), fail_under=70, fail_on="critical")

    assert (gate["result"], gate["exit_code"]) == ("fail", 1)


# --- GitHub annotations ----------------------------------------------------------------


def test_annotations_escape_site_text_so_it_cannot_start_a_workflow_command():
    summary = {"findings": [
        {"id": "F01", "severity": "critical", "section": "onpage, meta",
         "finding": "Title is 100% keywords\n::add-mask::secret", "fix": ""},
        {"id": "F02", "severity": "info", "section": "x", "finding": "ignored", "fix": ""},
    ]}
    [line] = gr.github_annotations(summary)

    assert "\n" not in line
    assert line == "::error title=SEO F01 (onpage%2C meta)::Title is 100%25 keywords%0A::add-mask::secret"


# --- CLI -------------------------------------------------------------------------------


def run_main(argv, fixture, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["generate_report.py", "https://ex.com/", *argv])
    with patch.object(gr, "collect_data", return_value=fixture):
        gr.main()


def test_ci_run_writes_json_no_report_file_and_fails_the_gate(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_main(["--format", "none", "--json", "out/summary.json", "--fail-under", "95",
                  "--github-annotations"], data(), monkeypatch, tmp_path)

    assert exit_info.value.code == 1
    summary = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert summary["gate"]["result"] == "fail" and summary["gate"]["fail_under"] == 95
    assert not list(tmp_path.glob("*.html"))
    assert "::error title=SEO F01 (security)::Strict-Transport-Security header missing" in capsys.readouterr().out


def test_json_to_stdout_is_clean_and_progress_goes_to_stderr(monkeypatch, tmp_path, capsys):
    run_main(["--format", "none", "--json", "-"], data(), monkeypatch, tmp_path)

    captured = capsys.readouterr()
    assert json.loads(captured.out)["overall"] == 90
    assert "Overall Score" in captured.err
    assert sys.stdout is not sys.stderr


@pytest.mark.parametrize("argv", [["--fail-under", "101"], ["--json", "-", "--github-annotations"]])
def test_invalid_ci_flags_are_usage_errors(argv, monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        run_main(argv, data(), monkeypatch, tmp_path)

    assert exit_info.value.code == 2
