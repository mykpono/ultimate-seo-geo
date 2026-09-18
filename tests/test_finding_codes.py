"""Findings keep their identity from run to run, so --previous can say what was fixed.

IDs are renumbered every run and wording carries counts, so neither identifies a
finding. finding_code() gives each one a class (code) and an instance (key).
compare_with_previous() matches on the key, carries first_seen forward, and never
calls a finding fixed when its check simply did not run.
"""

import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report as gr  # noqa: E402


def _data(**sections):
    base = {
        "security": {"score": 90}, "social": {"score": 40},
        "robots": {"status": 200, "sitemaps": ["s"], "ai_crawler_status": {}},
        "broken_links": {"summary": {"total": 50, "broken": 0}}, "readability": {"flesch_reading_ease": 45},
        "content_quality": {"score": 55}, "schema_validation": {"score": 30}, "sitemap": {"score": 100},
        "onpage": {"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
    }
    base.update(sections)
    return {"url": "https://ex.com/", "domain": "ex.com", "timestamp": "2026-09-18T10:00:00",
            "environment": {"primary": "Webflow", "runtime": "Unknown", "confidence": "low", "signals": [], "alternatives": []},
            "environment_fixes": [], "sections": base}


def _summary(data, timestamp=None):
    summary = gr.build_summary(data, gr.calculate_overall_score(data))
    if timestamp:
        summary["timestamp"] = timestamp
    return summary


def _links(count, **extra):
    return {"summary": {"total": 50, "broken": count},
            "issues": [{"severity": "critical", "finding": f"{count} broken link(s) found", "fix": "Fix them."}], **extra}


# --- codes and keys ---------------------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("2 broken link(s) found", "1 broken link(s) found"),
    ("Average paragraph length (114.0 sentences) — aim for 2-4", "Average paragraph length (6.5 sentences) — aim for 2-4"),
    ("Content readability is moderate (Flesch: 44.4)", "Content readability is moderate (Flesch: 51)"),
    ("LCP is 4,200 ms on mobile", "LCP is 2,900ms on mobile"),
])
def test_a_count_that_moves_is_the_same_finding(a, b):
    assert gr.finding_code("x", {}, a) == gr.finding_code("x", {}, b)


def test_the_subject_keeps_two_instances_apart_but_in_one_class():
    code_a, key_a = gr.finding_code("entity", {}, "Could not verify sameAs URL: https://yelp.com/biz/a")
    code_b, key_b = gr.finding_code("entity", {}, "Could not verify sameAs URL: https://yelp.com/biz/b")
    assert code_a == code_b and key_a != key_b
    assert gr.finding_code("entity", {}, "No Wikipedia article found for 'Balloon Bay'.")[1].endswith("#balloon bay")


def test_different_findings_from_one_check_get_different_codes():
    wiki = gr.finding_code("entity", {}, "Missing sameAs link to Wikipedia (Primary KG signal).")
    data = gr.finding_code("entity", {}, "Missing sameAs link to Wikidata (Primary KG signal).")
    assert wiki != data


def test_a_short_lead_in_does_not_swallow_the_finding():
    a = gr.finding_code("schema_validation", {}, "[info] Block 3: Google withdrew FAQ rich results but schema is still valid")
    b = gr.finding_code("schema_validation", {}, "[info] Block 1: Organization is missing a logo")
    assert a[0] != b[0]


def test_a_scripts_own_code_or_type_wins_and_is_namespaced():
    issue = {"type": "missing_page_type", "label": "comparison", "finding": "No comparison pages found on a saas site."}
    assert gr.finding_code("page_types", issue, issue["finding"]) == (
        "page_types.missing_page_type", "page_types.missing_page_type#comparison")
    assert gr.finding_code("x", {"code": "x.thing"}, "whatever")[0] == "x.thing"
    # A "type" that is prose, not a slug, is ignored.
    assert gr.finding_code("x", {"type": "Not A Slug!"}, "Title is missing")[0] == "x.title-is-missing"


def test_codes_are_slugs_and_every_finding_has_one():
    data = _data(broken_links=_links(2), internal_links={"issues": ["⚠️ 27 links have no anchor text"]})
    for finding in _summary(data)["findings"]:
        assert re.match(r"^[a-z_]+\.[a-z0-9_.-]+$", finding["code"])
        assert finding["key"].startswith(finding["code"])
        assert finding["status"] is None and finding["first_seen"] is None  # no previous run


# --- the comparison -------------------------------------------------------------------------

def test_a_moved_count_is_persisting_not_resolved_plus_new():
    then = _summary(_data(broken_links=_links(2)), "2026-08-01T09:00:00")
    now = _summary(_data(broken_links=_links(1)))
    delta = gr.compare_with_previous(now, then)
    assert delta["resolved"] == [] and delta["new"] == []
    [item] = delta["persisting"]
    assert item["finding"] == "1 broken link(s) found" and item["finding_was"] == "2 broken link(s) found"
    assert item["first_seen"] == "2026-08-01T09:00:00"


def test_a_fixed_finding_is_resolved_only_when_its_check_ran_again():
    then = _summary(_data(broken_links=_links(2)), "2026-08-01T09:00:00")
    fixed = gr.compare_with_previous(_summary(_data()), then)
    assert [f["finding"] for f in fixed["resolved"]] == ["2 broken link(s) found"] and fixed["not_rechecked"] == []
    assert fixed["resolved"][0]["lane"] == "Auto"

    errored = gr.compare_with_previous(_summary(_data(broken_links={"error": "timeout"})), then)
    assert errored["resolved"] == []
    assert [f["finding"] for f in errored["not_rechecked"]] == ["2 broken link(s) found"]


def test_a_summary_written_before_codes_existed_still_matches():
    then = _summary(_data(broken_links=_links(2)), "2026-08-01T09:00:00")
    for finding in then["findings"]:
        for field in ("code", "key", "status", "first_seen", "lane", "kind", "lane_reason"):
            finding.pop(field, None)
    then.pop("sections_run", None)
    delta = gr.compare_with_previous(_summary(_data(broken_links=_links(5))), then)
    assert len(delta["persisting"]) == 1 and not delta["new"] and not delta["resolved"]


def test_an_old_summary_matches_a_finding_whose_script_names_its_type():
    # Typed findings key on the type; a pre-1.19 baseline only has wording. Both sides
    # fall back to wording, or the same finding reads as resolved and new at once.
    nav = {"status": "measured", "issues": [{"type": "nav_link_error", "severity": "high",
           "finding": "1 global navigation link(s) return an error on every page.", "fix": "Fix it."}]}
    then = _summary(_data(navigation=nav), "2026-08-01T09:00:00")
    for finding in then["findings"]:
        finding.pop("key"), finding.pop("code")
    delta = gr.compare_with_previous(_summary(_data(navigation=nav)), then)
    assert len(delta["persisting"]) == 1 and not delta["new"] and not delta["resolved"]


def test_severity_change_is_reported_on_a_persisting_finding():
    then = _summary(_data(broken_links=_links(9)), "2026-08-01T09:00:00")
    data = _data(broken_links=_links(1))
    data["sections"]["broken_links"]["issues"][0]["severity"] = "medium"
    [item] = gr.compare_with_previous(_summary(data), then)["persisting"]
    assert item["severity_was"] == "critical"


def test_first_seen_carries_forward_through_a_chain_of_runs():
    run1 = _summary(_data(broken_links=_links(3)), "2026-07-01T09:00:00")
    run2 = _summary(_data(broken_links=_links(2)), "2026-08-01T09:00:00")
    gr.apply_previous(run2, run1)
    run3 = _summary(_data(broken_links=_links(1), social={"score": 40, "issues": [
        {"severity": "medium", "finding": "og:image missing", "fix": "Add it."}]}))
    gr.apply_previous(run3, run2)
    by_text = {f["finding"]: f for f in run3["findings"]}
    assert (by_text["1 broken link(s) found"]["status"], by_text["1 broken link(s) found"]["first_seen"]) == (
        "persisting", "2026-07-01T09:00:00")
    assert (by_text["og:image missing"]["status"], by_text["og:image missing"]["first_seen"]) == ("new", run3["timestamp"])
    assert run3["previous"]["timestamp"] == "2026-08-01T09:00:00"


# --- the HTML -------------------------------------------------------------------------------------

def _html(data, previous):
    return gr.generate_html(data, gr.calculate_overall_score(data), previous_summary=previous)


def _plan(html):
    return re.search(r'<section id="plan".*?</section>\n<section id="questions"', html, re.S).group(0)


def test_plan_opens_with_what_was_fixed_and_ages_what_is_left():
    then = _summary(_data(broken_links=_links(2), social={"score": 40, "issues": [
        {"severity": "medium", "finding": "og:image missing", "fix": "Add it."}]}), "2026-08-01T09:00:00")
    data = _data(broken_links=_links(1), image_seo={"score": 60, "issues": [
        {"severity": "medium", "finding": "Hero image has no srcset.", "fix": "Add srcset."}]})
    plan = _plan(_html(data, then))
    assert "Fixed since the 2026-08-01 run" in plan and "og:image missing" in plan
    assert plan.index('id="fixed"') < plan.index('id="lane-auto"')
    assert "Open since 2026-08-01" in plan and ">New<" in plan
    fixed = plan[plan.index('id="fixed"'):plan.index('id="lane-auto"')]
    assert "broken link" not in fixed  # it only moved


def test_a_check_that_did_not_run_is_called_out_not_credited():
    then = _summary(_data(broken_links=_links(2)), "2026-08-01T09:00:00")
    html = _html(_data(broken_links={"error": "timeout"}), then)
    plan = _plan(html)
    assert "Fixed since" not in plan
    assert "Not re-checked" in plan and "Broken links did not run" in plan and "not counted as fixed" in plan
    assert "1 not re-checked" in html


def test_no_previous_run_means_no_fixed_block_and_no_age_chips():
    html = gr.generate_html(_data(broken_links=_links(2)), gr.calculate_overall_score(_data(broken_links=_links(2))))
    assert 'id="fixed"' not in html and "Open since" not in html and ">New<" not in html
