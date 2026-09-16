"""report_lint.py checks a written audit report against the § 2 contract.

The report is the one artifact the agent writes by hand, so it is where the
template drifts: a score from a formula the skill retired, a High finding
filed under Critical, a Core Web Vitals number when PageSpeed never ran. Each
test below breaks one rule in an otherwise valid report built from a real
generate_report.py summary, and checks the linter names that rule.
"""

import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report as gr  # noqa: E402
import report_lint as rl  # noqa: E402


# --- the linter's copy of the contract matches the script's ---------------------------


def test_contract_constants_match_generate_report():
    assert rl.SEVERITY_SCALE == gr.SEVERITY_SCALE
    assert rl.CONFIDENCE_LABELS == gr.CONFIDENCE_LABELS
    assert rl.GROUP_LABELS == gr.CHECK_GROUPS
    assert rl.MIN_MEASURED == gr.MIN_MEASURED_FOR_GATE


# --- the documented examples pass ------------------------------------------------------


def documented_examples():
    with open(os.path.join(ROOT, "references", "audit-output-example.md"), encoding="utf-8") as fh:
        return re.findall(r"```\n(.*?)```", fh.read(), re.S)


def test_all_three_documented_examples_are_found():
    assert [rl.lint(b, excerpt=True)["type"] for b in documented_examples()] == ["audit", "competitive", "geo"]


@pytest.mark.parametrize("index", [0, 1, 2], ids=["audit", "competitive", "geo"])
def test_documented_examples_lint_clean(index):
    """Agents copy these verbatim. The GEO example used to omit four mandatory finding fields."""
    result = rl.lint(documented_examples()[index], excerpt=True)

    assert result["errors"] == []


# --- a valid report ---------------------------------------------------------------------


SECTIONS = dict(
    security={"score": 90}, social={"score": 40}, robots={"status": 200, "sitemaps": ["s"], "ai_crawler_status": {}},
    broken_links={"summary": {"total": 50, "broken": 2}}, readability={"flesch_reading_ease": 45},
    content_quality={"score": 55}, schema_validation={"score": 30}, sitemap={"score": 100},
    onpage={"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
    pagespeed={"error": "HTTP 429"},
)


@pytest.fixture
def summary():
    data = {"url": "https://ex.com/", "timestamp": "2026-09-16T10:00:00", "sections": dict(SECTIONS)}
    return json.loads(json.dumps(gr.build_summary(data, gr.calculate_overall_score(data))))


CRITICAL = """Finding: Schema validation fails on /pricing
Evidence: validate_schema.py reports 3 errors on the Product node
Impact: Product rich results are withheld
Fix: Add the missing offers.price and offers.priceCurrency
Confidence: Confirmed | Severity: 🔴 Critical
First-Principle Observation: The Product node has no offers property
Dependency: Independent; unblocks F04
Falsifiability: If the Rich Results Test passes with the current markup, the errors are false positives
Leading Indicator: GSC Merchant listings report shows valid items within 2 weeks"""

HIGH = """Finding: 2 broken internal links on the homepage
Evidence: broken_links.py found 2 of 50 links returning 404
Impact: Crawl budget and link equity leak to dead URLs
Fix: Point /old-pricing and /team at their live pages
Confidence: Confirmed | Severity: 🟠 High
First-Principle Observation: GET /old-pricing returns 404
Dependency: Independent
Falsifiability: If both URLs return 200 on a rerun, the failure was transient
Leading Indicator: broken_links.py reports 0 broken links on the next run"""

MEDIUM = """Finding: Title tag uses "Home | Brand" pattern
Evidence: <title>Home | Brand</title>
Impact: Weak query match for the primary keyword
Fix: Rewrite to "Invoicing Software for Agencies | Brand"
Confidence: Likely | Severity: 🟡 Medium
Falsifiability: If CTR does not change within 4 weeks at the same position, the title was not the issue
Leading Indicator: GSC CTR for homepage queries"""


def render(summary, *, score=None, body=None):
    rows = []
    for group in summary["group_scores"].values():
        value = "—" if group["score"] is None else f"{group['score']}/100"
        rows.append(f"| {group['label']} | {value} | {group['share']}% | {group['status']} |")
    header = (
        f"## SEO Health Score: {summary['overall'] if score is None else score}/100\n"
        f"Source: generate_report.py — {summary['measured_categories']} weighted checks measured; "
        f"not measured: {', '.join(summary['unmeasured'])}\n\n"
        "| Category | Score | Share | Status |\n|---|---|---|---|\n" + "\n".join(rows)
    )
    body = body if body is not None else (
        "## Executive Summary\nStrong technical base; schema is the gap.\n\n"
        f"## 🔴 Critical Issues (fix immediately)\n\n{CRITICAL}\n\n"
        f"## 🟠 High Priority (fix this week)\n\n{HIGH}\n\n"
        f"## 🟡 Medium Priority (fix this month)\n\n{MEDIUM}\n\n"
        "## 🔵 Low Priority\nNone.\n\n## ⚡ Quick Wins (findings tagged quick_win, any severity)\nNone.\n\n"
        "## 💡 Opportunity Signals (findings tagged opportunity)\nNone.\n\n"
        "## Assumptions Audit\n- The homepage represents the site.\n\n## Full Findings\nAs above.\n"
    )
    return ("# SEO Audit Report — ex.com\n"
            "Date: 2026-09-16 | Business Type: SaaS | Audited Pages: 8 | Confidence: Medium\n\n"
            f"{header}\n\n{body}")


def rules(result, level="errors"):
    return sorted({item["rule"] for item in result[level]})


def test_a_valid_report_is_clean(summary):
    result = rl.lint(render(summary), summary=summary)

    assert (result["errors"], result["warnings"]) == ([], [])
    assert (result["type"], result["score"], result["findings"]) == ("audit", summary["overall"], 3)


def test_a_pipe_inside_a_value_is_not_a_field_separator(summary):
    result = rl.lint(render(summary), summary=summary)
    linter = rl.Linter(render(summary), summary=summary)
    linter.run()

    medium = next(f for f in linter.findings if f["fields"]["Finding"].startswith("Title tag"))
    assert medium["fields"]["Evidence"] == "<title>Home | Brand</title>"
    assert medium["fields"]["Severity"] == "🟡 Medium"
    assert result["errors"] == []


# --- one broken rule at a time -----------------------------------------------------------


def test_score_that_differs_from_the_summary(summary):
    assert rules(rl.lint(render(summary, score=summary["overall"] + 5), summary=summary)) == ["score-mismatch"]


def test_category_status_that_contradicts_its_score(summary):
    text = re.sub(r"(\| Schema / structured data \| 30/100 \| [\d.]+% \| )Gap", r"\1Strong", render(summary))

    assert rules(rl.lint(text, summary=summary)) == ["category-mismatch", "category-status"]


def test_category_score_that_differs_from_the_summary(summary):
    text = re.sub(r"(\| Schema / structured data \| )30/100", r"\g<1>45/100", render(summary))

    assert "category-mismatch" in rules(rl.lint(text, summary=summary))


def test_missing_required_section(summary):
    text = render(summary).replace("## Assumptions Audit\n- The homepage represents the site.\n\n", "")

    assert rules(rl.lint(text, summary=summary)) == ["section-missing"]


def test_critical_finding_without_its_extra_fields(summary):
    text = render(summary).replace("Dependency: Independent; unblocks F04\n", "")

    result = rl.lint(text, summary=summary)
    assert rules(result) == ["finding-field"]
    assert "Dependency" in result["errors"][0]["message"]


def test_medium_finding_does_not_need_the_critical_high_fields(summary):
    assert "First-Principle" not in MEDIUM
    assert rl.lint(render(summary), summary=summary)["errors"] == []


def test_high_finding_filed_under_critical(summary):
    text = render(summary).replace(f"## 🟠 High Priority (fix this week)\n\n{HIGH}", "## 🟠 High Priority (fix this week)\n")
    text = text.replace(CRITICAL, CRITICAL + "\n\n" + HIGH)

    assert rules(rl.lint(text, summary=summary)) == ["severity-section"]


def test_confidence_off_the_scale(summary):
    text = render(summary).replace("Confidence: Likely |", "Confidence: High |")

    assert rules(rl.lint(text, summary=summary)) == ["confidence"]


def test_severity_off_the_scale(summary):
    text = render(summary).replace("Severity: 🟡 Medium", "Severity: Warning")

    assert rules(rl.lint(text, summary=summary)) == ["severity"]


def test_retired_deduction_formula(summary):
    text = render(summary).replace(
        "Source: generate_report.py",
        "positive_signals=14, deficit_signals=9, base=61; Critical −15×0\nSource: generate_report.py")

    assert rules(rl.lint(text, summary=summary)) == ["retired-formula"]


def test_score_without_a_generate_report_source(summary):
    text = re.sub(r"Source: generate_report\.py[^\n]*\n", "", render(summary))

    assert rules(rl.lint(text, summary=summary)) == ["score-source"]


def test_score_when_too_few_checks_were_measured(summary):
    summary["measured_categories"] = 3

    assert rules(rl.lint(render(summary), summary=summary)) == ["score-thin"]


def test_not_scored_needs_a_reason(summary):
    head = "## SEO Health Score: not scored\n\n| Category | Status |\n|---|---|\n| Technical SEO | Needs work |"
    text = re.sub(r"## SEO Health Score:.*?(?=\n\n## Executive)", head, render(summary), flags=re.S)
    thin = dict(summary, measured_categories=2)

    assert rules(rl.lint(text, summary=thin)) == ["score-reason"]
    fixed = text.replace("not scored\n", "not scored\nReason: only 2 weighted checks measured\n")
    assert rl.lint(fixed, summary=thin)["errors"] == []


def test_not_scored_when_the_summary_has_a_score_is_a_warning(summary):
    head = ("## SEO Health Score: not scored — generate_report.py output not attached\n\n"
            "| Category | Status |\n|---|---|\n| Technical SEO | Needs work |")
    text = re.sub(r"## SEO Health Score:.*?(?=\n\n## Executive)", head, render(summary), flags=re.S)
    result = rl.lint(text, summary=summary)

    assert (rules(result), rules(result, "warnings")) == ([], ["score-available"])


def test_core_web_vitals_number_when_pagespeed_was_not_measured(summary):
    text = render(summary).replace("Impact: Weak query match", "Impact: LCP 4.8s and a weak query match")

    assert "pagespeed" in summary["unmeasured"]
    assert rules(rl.lint(text, summary=summary)) == ["unmeasured-metric"]


def test_backlink_count_when_link_profile_did_not_run(summary):
    text = render(summary).replace("Impact: Weak query match", "Impact: Only 12 referring domains; weak query match")

    assert rules(rl.lint(text, summary=summary)) == ["unmeasured-metric"]


def test_without_a_summary_numbers_are_warnings_not_errors(summary):
    text = render(summary).replace("Impact: Weak query match", "Impact: LCP 4.8s and a weak query match")
    result = rl.lint(text)

    assert rules(result) == []
    assert rules(result, "warnings") == ["unverified-metric", "unverified-score"]


def test_competitive_report_with_a_health_score():
    text = ("# Competitive SEO Observation — rival.com\n"
            "Date: 2026-09-16 | Pages Reviewed: 12 | Context: External Observation Only\n\n"
            "## SEO Health Score: 62/100\n")

    assert rules(rl.lint(text)) == ["competitive-score"]


def test_unrecognised_report():
    assert rules(rl.lint("Here is your audit!\n\nScore: 80")) == ["title"]


def test_duplicate_findings_across_severity_sections_warn(summary):
    text = render(summary).replace("## 🔵 Low Priority\nNone.", "## 🔵 Low Priority\n\n" + MEDIUM.replace(
        "Severity: 🟡 Medium", "Severity: Low"))

    assert rules(rl.lint(text, summary=summary), "warnings") == ["duplicate"]


# --- real report shapes (from the skill's own eval runs) ------------------------------------


def test_bold_labels_blank_lines_and_finding_subheadings():
    """iteration-2 eval-1 (psybear.co) wrote findings like this and parsed as having none."""
    text = """# SEO Audit Report — psybear.co
Date: 2026-03-30 | Audited Pages: 50 | Confidence: Medium

## 🟠 High Priority (fix this week)

### Finding 1: 123 Leaf Pages Are Near-Orphaned

**Finding:** 123 pages receive only a single internal link

**Evidence:** `internal_links.py --depth 1` found 123 URLs with exactly 1 incoming link

**Impact:** Link equity pools in hub pages

- **Fix**: Add related-strain links to each leaf page

**Confidence:** Likely (inferred from source analysis, not measured) | **Severity:** 🟡 Medium
**Falsifiability:** If rankings do not move after linking, equity is not the constraint
**Leading Indicator:** internal_links.py shows ≥3 inbound links per leaf page
"""
    linter = rl.Linter(text, excerpt=True)
    result = linter.run()

    [finding] = linter.findings
    assert finding["fields"]["Fix"] == "Add related-strain links to each leaf page"
    assert finding["section"] == "🟠 High Priority (fix this week)".replace("🟠 ", "")
    assert rules(result) == ["severity-section"]  # the one real problem: a Medium under High Priority


def test_a_fix_written_as_a_list_under_its_label():
    """iteration-2 eval-1: "**Fix:**" on its own line, then numbered steps, was reported as a missing Fix."""
    text = """# SEO Audit Report — psybear.co
Date: 2026-03-30 | Audited Pages: 50 | Confidence: Medium

## 🟡 Medium Priority

**Finding:** 123 pages receive only a single internal link

**Fix:**
1. Add contextual cross-links from related content pages
2. Add a "Related Strains" block to each leaf page

**Confidence:** Confirmed
"""
    linter = rl.Linter(text, excerpt=True)
    linter.run()

    [finding] = linter.findings
    assert finding["fields"]["Fix"].startswith("1. Add contextual cross-links")
    assert "Related Strains" in finding["fields"]["Fix"]


@pytest.mark.parametrize("value", ["Likely (inferred from source analysis, not measured)",
                                   "Confirmed (direct evidence from validate_schema.py)", "Hypothesis — needs URL check"])
def test_confidence_with_its_reason_is_accepted(value, summary):
    text = render(summary).replace("Confidence: Likely |", f"Confidence: {value} |")

    assert rl.lint(text, summary=summary)["errors"] == []


@pytest.mark.parametrize("value", ["N/A — not measured", "Likelyish", "High (strong)"])
def test_confidence_that_is_not_a_label_is_still_rejected(value, summary):
    text = render(summary).replace("Confidence: Likely |", f"Confidence: {value} |")

    assert rules(rl.lint(text, summary=summary)) == ["confidence"]


# --- CLI ----------------------------------------------------------------------------------


def cli(tmp_path, text, *args):
    report = tmp_path / "report.md"
    report.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "report_lint.py"), str(report), *args],
                          capture_output=True, text=True)


def test_cli_exit_codes(tmp_path, summary):
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    assert cli(tmp_path, render(summary), "--summary", str(summary_path)).returncode == 0
    assert cli(tmp_path, render(summary, score=1), "--summary", str(summary_path)).returncode == 1
    assert cli(tmp_path, render(summary)).returncode == 0  # warnings only
    assert cli(tmp_path, render(summary), "--strict").returncode == 1
    missing = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "report_lint.py"),
                              str(tmp_path / "nope.md")], capture_output=True, text=True)
    assert missing.returncode == 2


def test_cli_json_output(tmp_path, summary):
    out = cli(tmp_path, render(summary, score=1), "--json")
    result = json.loads(out.stdout)

    assert result["score"] == 1 and result["type"] == "audit"
    assert {"rule", "line", "message"} <= set(result["warnings"][0])
