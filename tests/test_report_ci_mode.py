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
    """9 measured checks, robots split into crawl rules (w4) and AI search access (w8):
    (90*8 + 80*5 + 100*4 + 100*8 + 100*10 + 100*8 + 70*6 + 100*5 + 100*3) / 57 = 93.7."""
    scores = gr.calculate_overall_score(data())

    assert scores["overall"] == 94
    assert scores["measured_categories"] == 9
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

    assert summary["schema_version"] == 2
    assert (summary["overall"], summary["grade"]) == (94, "A+")
    assert summary["severity_scale"] == ["critical", "high", "medium", "low", "info"]
    assert summary["categories"]["pagespeed"] == {
        "label": "Performance (Core Web Vitals)", "group": "performance", "score": None, "weight": 13,
        "status": "Not measured"}
    assert summary["categories"]["security"]["status"] == "Strong"
    assert summary["counts"] == {"critical": 1, "high": 0, "medium": 1, "low": 0, "info": 0}
    assert summary["findings"][0] == {
        "id": "F01", "severity": "critical", "level": "critical", "section": "security", "group": "technical",
        "finding": "Strict-Transport-Security header missing", "evidence": None, "impact": None, "fix": "",
        "confidence": None, "falsifiability": None, "leading_indicator": None, "dependency": None,
        "source": "script:security", "tags": []}
    assert summary["findings"][1]["severity"] == "medium" and summary["findings"][1]["level"] == "warning"
    json.dumps(summary)  # serialisable as-is


# --- v2 severity scale and finding fields --------------------------------------------

# The v1 summary collapsed script severities into three levels. v2 keeps the
# script's own severity, but "level" must stay exactly what v1 called severity,
# or --fail-on and the annotations would silently change for existing pipelines.
V1_LEVELS = {"critical": "critical", "high": "critical", "warning": "warning", "medium": "warning",
             "info": "info", "low": "info", "": "info", "bogus": "info"}


def summary_with_issues(*issues):
    return summary_of(data(security={"score": 90, "issues": list(issues)}, content_quality={"score": 70}))


@pytest.mark.parametrize("raw,level", sorted(V1_LEVELS.items()))
def test_level_is_what_v1_called_severity(raw, level):
    [finding] = summary_with_issues({"severity": raw, "finding": "x"})["findings"]

    assert finding["level"] == level


@pytest.mark.parametrize("raw,severity", [("critical", "critical"), ("HIGH", "high"), ("warning", "medium"),
                                          ("medium", "medium"), ("low", "low"), ("info", "info"),
                                          ("bogus", "info")])
def test_severity_keeps_the_scripts_own_scale(raw, severity):
    [finding] = summary_with_issues({"severity": raw, "finding": "x"})["findings"]

    assert finding["severity"] == severity


def test_findings_are_ordered_on_the_full_scale():
    summary = summary_with_issues({"severity": "low", "finding": "l"}, {"severity": "high", "finding": "h"},
                                  {"severity": "critical", "finding": "c"}, {"severity": "medium", "finding": "m"})

    assert [(f["id"], f["severity"]) for f in summary["findings"]] == [
        ("F01", "critical"), ("F02", "high"), ("F03", "medium"), ("F04", "low")]


def test_script_supplied_fields_pass_through():
    [finding] = summary_with_issues({
        "severity": "high", "finding": "hreflang return tag missing", "fix": "add it",
        "evidence": "/fr/ lacks a link back to /en/", "impact": "Google may ignore the pair",
        "confidence": "confirmed", "failure_check": "hreflang_checker reports no missing returns",
        "leading_indicator": "GSC International Targeting errors drop", "depends_on": "F02",
        "tags": ["quick_win"],
    })["findings"]

    assert finding["evidence"] == "/fr/ lacks a link back to /en/"
    assert finding["impact"] == "Google may ignore the pair"
    assert finding["confidence"] == "Confirmed"
    assert finding["falsifiability"] == "hreflang_checker reports no missing returns"
    assert finding["leading_indicator"] == "GSC International Targeting errors drop"
    assert finding["dependency"] == "F02"
    assert finding["tags"] == ["quick_win"]


def test_missing_fields_are_null_not_the_html_placeholder_text():
    """The HTML fills gaps with generic guidance; the summary must not pass that off as the script's."""
    d = data(security={"score": 90, "issues": [{"severity": "high", "finding": "x"}]}, content_quality={"score": 70})
    [issue] = gr._collect_issues(d)
    [finding] = summary_of(d)["findings"]

    assert issue["leading_indicator"]  # the view still gets its default
    assert (finding["falsifiability"], finding["leading_indicator"], finding["dependency"]) == (None, None, None)


@pytest.mark.parametrize("raw", ["High", "Medium", 0.9, ""])
def test_confidence_outside_the_documented_labels_is_null(raw):
    [finding] = summary_with_issues({"severity": "info", "finding": "x", "confidence": raw})["findings"]

    assert finding["confidence"] is None


def test_every_check_belongs_to_one_report_group():
    assert set(gr.CHECK_GROUP) == set(gr.CHECK_LABELS)
    assert set(gr.CHECK_GROUP.values()) == set(gr.CHECK_GROUPS)


def test_a_high_finding_still_fails_fail_on_critical():
    gate = gr.evaluate_gate(summary_with_issues({"severity": "high", "finding": "x"}), fail_on="critical")

    assert gate["result"] == "fail"


def test_a_low_finding_does_not_fail_fail_on_warning():
    gate = gr.evaluate_gate(summary_with_issues({"severity": "low", "finding": "x"}), fail_on="warning")

    assert gate["result"] == "pass"


def test_gates_still_read_v1_shaped_findings():
    v1 = {"findings": [{"id": "F01", "severity": "warning", "section": "x", "finding": "y", "fix": ""}]}

    assert gr.evaluate_gate(v1, fail_on="warning")["result"] == "fail"
    assert gr.evaluate_gate(v1, fail_on="critical")["result"] == "pass"


# --- gates -------------------------------------------------------------------------


def summary_of(d):
    return gr.build_summary(d, gr.calculate_overall_score(d))


@pytest.mark.parametrize("kwargs,result,code", [
    ({}, "not set", 0),
    ({"fail_under": 94}, "pass", 0),
    ({"fail_under": 95}, "fail", 1),
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
    assert json.loads(captured.out)["overall"] == 94
    assert "Overall Score" in captured.err
    assert sys.stdout is not sys.stderr


@pytest.mark.parametrize("argv", [["--fail-under", "101"], ["--json", "-", "--github-annotations"]])
def test_invalid_ci_flags_are_usage_errors(argv, monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        run_main(argv, data(), monkeypatch, tmp_path)

    assert exit_info.value.code == 2
