"""score_eval_transcript.py: the report_lint assertion type.

Eval assertions were all literal or regex matches, so eval 1 passed any reply
that contained "Finding:" and a "72/100" somewhere, including the bundled
fixture, which had no report title, no sections and no severities. The
report_lint assertion runs the written report through report_lint.py, so the
eval suite enforces the § 2 report contract instead of its keywords.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_report as gr  # noqa: E402
import score_eval_transcript as se  # noqa: E402

SCRIPT = ROOT / "scripts" / "score_eval_transcript.py"
FIXTURE = ROOT / "evals" / "fixtures" / "eval1_pass.txt"
ASSERTION = {"id": "report-contract", "type": "report_lint"}


def eval_one():
    data = se.load_evals(ROOT / "evals" / "evals.json")
    return next(e for e in data["evals"] if e["id"] == 1)


def test_eval_one_carries_the_report_contract_assertion():
    assert {"id": "report-contract", "type": "report_lint"}.items() <= next(
        a for a in eval_one()["assertions"] if a["type"] == "report_lint").items()


def test_the_bundled_eval_one_fixture_passes_every_assertion():
    result = se.score_eval(eval_one(), FIXTURE.read_text(encoding="utf-8"))

    assert result["all_passed"], [a["detail"] for a in result["assertions"] if not a["passed"]]


def test_the_old_keyword_only_fixture_now_fails_the_contract():
    """The previous eval1_pass.txt: every keyword assertion passed, no report structure at all."""
    old = ("SEO Health Score: 72/100\n\nFinding: Time to first byte is elevated\nEvidence: slow origin\n"
           "Impact: crawl efficiency\nFix: Enable CDN caching\nConfidence: Likely\n\n"
           "E-E-A-T / YMYL: authorship. Schema: add JSON-LD.\n\nAction Plan\n| Priority | Effort |\n")
    result = se.score_eval(eval_one(), old)
    by_id = {a["id"]: a for a in result["assertions"]}

    assert all(a["passed"] for i, a in by_id.items() if i != "report-contract")
    assert not by_id["report-contract"]["passed"]
    assert "no report title found" in by_id["report-contract"]["detail"]


def test_preamble_before_the_title_is_ignored_and_lines_point_into_the_transcript():
    report = FIXTURE.read_text(encoding="utf-8")
    broken = report.replace("Dependency: Independent; unblocks F03 (Person schema)\n", "")
    passed, detail = se.check_assertion(ASSERTION, "Sure, here it is.\n\nMore preamble.\n" + broken)

    assert not passed
    first_finding = ("Sure, here it is.\n\nMore preamble.\n" + broken).splitlines().index(
        "Finding: Health and dosing pages have no named author or medical reviewer") + 1
    assert f"finding-field@{first_finding}" in detail


def test_strict_also_fails_on_warnings():
    text = FIXTURE.read_text(encoding="utf-8")  # a /100 with no summary to check it against: a warning

    assert se.check_assertion(ASSERTION, text)[0]
    passed, detail = se.check_assertion({**ASSERTION, "strict": True}, text)
    assert not passed and "unverified-score" in detail


def test_excerpt_skips_the_required_sections():
    text = FIXTURE.read_text(encoding="utf-8").split("## ⚡ Quick Wins")[0]

    assert not se.check_assertion(ASSERTION, text)[0]
    assert se.check_assertion({**ASSERTION, "excerpt": True}, text)[0]


def test_a_summary_is_checked_when_given():
    data = {"url": "https://psybear.co/", "timestamp": "2026-09-16T10:00:00",
            "sections": {"security": {"score": 90}, "social": {"score": 40}, "sitemap": {"score": 100},
                         "readability": {"flesch_reading_ease": 45}, "content_quality": {"score": 55},
                         "schema_validation": {"score": 30}}}
    summary = gr.build_summary(data, gr.calculate_overall_score(data))
    passed, detail = se.check_assertion(ASSERTION, FIXTURE.read_text(encoding="utf-8"), summary)

    assert not passed
    assert "score-mismatch" in detail


def test_other_assertion_types_are_unchanged():
    assert se.check_assertion({"id": "x", "type": "contains_any", "values": ["Finding:"]}, "Finding: y") == (
        True, "x: any of 1 literals -> True")


# --- CLI ---------------------------------------------------------------------------------


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_all_fixtures_pass():
    out = run("--all-fixtures")

    assert out.returncode == 0, out.stdout


def test_cli_summary_flag(tmp_path):
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"overall": 40, "measured_categories": 18, "unmeasured": ["pagespeed"],
                                   "group_scores": {}}), encoding="utf-8")

    out = run("--eval-id", "1", "--text-file", str(FIXTURE), "--summary", str(summary))
    assert out.returncode == 1 and "score-mismatch" in out.stdout
    assert run("--eval-id", "1", "--text-file", str(FIXTURE)).returncode == 0


@pytest.mark.parametrize("content", ["not json", "[1, 2]"])
def test_cli_rejects_a_bad_summary(tmp_path, content):
    summary = tmp_path / "summary.json"
    summary.write_text(content, encoding="utf-8")

    assert run("--eval-id", "1", "--text-file", str(FIXTURE), "--summary", str(summary)).returncode == 2
