"""The report separates what to do from what is not known, and says who can do it.

Three rules. A finding that only says a check could not see is an open question,
never a defect and never in the plan. Every other finding carries a lane from
the recommendation register's vocabulary (Auto, Assisted, Human, Decision), and
a high-risk change is never Auto. The plan lists the lanes agent-first, and the
HTML, the JSON summary and the fix prompt all read the same classification.
"""

import json
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


MIXED = dict(
    image_seo={"score": 60, "issues": [
        {"severity": "medium", "finding": "First <img> has no srcset attribute.", "fix": "Add srcset."}]},
    onpage={"title": "t", "meta_description": "", "h1": ["h"], "canonical": "https://ex.com/", "issues": [
        {"severity": "high", "finding": "Meta description missing.", "fix": "Write a 150-character description."}]},
    robots={"status": 200, "sitemaps": ["s"], "ai_crawler_status": {}, "issues": [
        {"severity": "medium", "finding": "robots.txt blocks OAI-SearchBot.", "fix": "Allow OAI-SearchBot in robots.txt."}]},
    entity={"issues": [
        {"severity": "medium", "finding": "Missing sameAs link to Wikidata.", "fix": "Add the wikidata.org URL to sameAs."},
        {"severity": "info", "finding": "Could not verify sameAs URL: https://yelp.com/biz/x", "fix": "Confirm the URL by hand."}]},
    architecture={"issues": [
        {"severity": "info", "finding": "Link equity by section was not measured.", "evidence": "crawl stopped at max_pages=80",
         "fix": "Re-run `site_graph.py` with a higher --max-pages."}]},
    page_types={"issues": [
        {"severity": "medium", "finding": "No comparison pages found.", "fix": "Create /vs/ pages.", "tags": ["opportunity"]}]},
    readability={"flesch_reading_ease": 45, "issues": [
        {"severity": "info", "finding": "Readability is moderate (Flesch 45)."}]},
    pagespeed={"error": "HTTP 429: rate limited"},
)


def _issues(data):
    return gr._collect_issues(data)


def _by_finding(data):
    return {i["finding"]: i for i in _issues(data)}


def _section(html, sid):
    match = re.search(r'<section id="%s".*?</section>\n' % re.escape(sid), html, re.S)
    return match.group(0) if match else ""


def _html(data):
    return gr.generate_html(data, gr.calculate_overall_score(data))


# --- the lane table ---------------------------------------------------------------

def test_every_check_has_a_lane_on_the_register_scale():
    assert set(gr.CHECK_LANE) == set(gr.CHECK_LABELS)
    assert set(gr.CHECK_LANE.values()) <= set(gr.LANES)
    assert set(gr.LANE_TITLES) == set(gr.LANE_REASONS) == set(gr.LANES)


def test_lanes_are_the_client_register_vocabulary():
    with open(os.path.join(ROOT, "references", "report-template", "report-template.md"), encoding="utf-8") as fh:
        template = fh.read()
    for lane in gr.LANES:
        assert f"`{lane}`" in template


@pytest.mark.parametrize("check", ["canonical", "robots", "redirects", "hreflang", "ai_search_access"])
def test_high_risk_checks_are_never_auto(check):
    assert gr.CHECK_LANE[check] != "Auto"


# --- classification -----------------------------------------------------------------

def test_findings_land_in_the_expected_lane():
    found = _by_finding(_data(**MIXED))
    assert found["First <img> has no srcset attribute."]["lane"] == "Auto"
    assert found["Meta description missing."]["lane"] == "Auto"
    assert found["robots.txt blocks OAI-SearchBot."]["lane"] == "Assisted"
    assert found["Missing sameAs link to Wikidata."]["lane"] == "Human"
    assert found["No comparison pages found."] ["kind"] == "opportunity"
    assert found["No comparison pages found."]["lane"] == "Decision"
    for issue in found.values():
        if issue["lane"]:
            assert issue["lane_reason"]


@pytest.mark.parametrize("text", [
    "Add a canonical tag to the page.", "Fix the redirect chain.", "Add noindex to thin pages.",
    "Edit robots.txt to allow the bot.", "Add hreflang return tags."])
def test_a_high_risk_fix_is_assisted_whichever_check_raised_it(text):
    data = _data(onpage={"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "c",
                         "issues": [{"severity": "medium", "finding": "Something is off.", "fix": text}]})
    [issue] = _issues(data)
    assert gr.CHECK_LANE["onpage"] == "Auto" and issue["lane"] == "Assisted"


def test_a_script_may_state_its_own_lane_and_kind():
    data = _data(onpage={"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "c", "issues": [
        {"severity": "medium", "finding": "Title is weak.", "fix": "Rewrite it.", "lane": "human", "lane_reason": "Brand call."},
        {"severity": "high", "finding": "The page could not be read.", "kind": "data_gap"},
        {"severity": "medium", "finding": "x", "fix": "y", "lane": "Robot"}]})
    found = _by_finding(data)
    assert (found["Title is weak."]["lane"], found["Title is weak."]["lane_reason"]) == ("Human", "Brand call.")
    assert found["The page could not be read."]["kind"] == "data_gap"
    assert found["x"]["lane"] == "Auto"  # an unknown lane falls back to the check's


def test_wording_alone_never_hides_a_real_defect():
    # "could not" in a critical finding is still a defect: only info-level notes move.
    data = _data(robots={"status": 500, "sitemaps": [], "ai_crawler_status": {}, "issues": [
        {"severity": "critical", "finding": "robots.txt could not be fetched (HTTP 500).", "fix": "Restore it."}]})
    [issue] = _issues(data)
    assert issue["kind"] == "defect" and issue["lane"] == "Assisted"


def test_a_data_gap_carries_no_lane():
    found = _by_finding(_data(**MIXED))
    for text in ("Link equity by section was not measured.", "Could not verify sameAs URL: https://yelp.com/biz/x"):
        assert found[text]["kind"] == "data_gap" and found[text]["lane"] is None


# --- the plan ------------------------------------------------------------------------

def test_plan_orders_lanes_agent_first_and_items_by_severity():
    data = _data(**MIXED)
    plan = gr.build_action_plan(_issues(data), gr.calculate_overall_score(data))
    assert list(plan) == ["Auto", "Assisted", "Human", "Decision"]
    assert [i["finding"] for i in plan["Auto"]] == ["Meta description missing.", "First <img> has no srcset attribute."]
    assert [len(plan[lane]) for lane in gr.LANES] == [2, 1, 1, 1]


def test_plan_leaves_out_questions_and_notes_with_no_fix():
    data = _data(**MIXED)
    planned = {i["finding"] for items in gr.build_action_plan(_issues(data), gr.calculate_overall_score(data)).values()
               for i in items}
    assert "Link equity by section was not measured." not in planned
    assert "Readability is moderate (Flesch 45)." not in planned


def test_score_gain_is_the_points_a_check_adds_back_at_100():
    data = _data()
    scores = gr.calculate_overall_score(data)
    gains = gr.check_score_gains(scores)
    assert gains["sitemap"] == 0 and gains["schema_validation"] > 0
    assert "pagespeed" not in gains  # unmeasured: nothing to recover
    # Recovering every gain lands exactly on 100.
    assert round(scores["overall"] + sum(gains.values())) in (99, 100, 101)


# --- open questions ---------------------------------------------------------------------

def test_open_questions_list_unmeasured_checks_then_data_gaps():
    data = _data(**MIXED)
    scores = gr.calculate_overall_score(data)
    questions = gr.build_open_questions(data, scores, _issues(data))
    by_id = {q["id"]: q for q in questions}
    speed = by_id["Q-pagespeed"]
    assert "rate limited" in speed["why"] and "PAGESPEED_API_KEY" in speed["close"]
    assert str(gr.CHECK_WEIGHTS["pagespeed"]) in speed["unlocks"]
    gaps = [q for q in questions if q["id"].startswith("F")]
    assert {q["question"] for q in gaps} == {
        "Link equity by section was not measured.", "Could not verify sameAs URL: https://yelp.com/biz/x"}
    assert all(q["close"] for q in gaps)
    assert questions.index(speed) < questions.index(gaps[0])


# --- the summary JSON -----------------------------------------------------------------------

def test_summary_carries_the_plan_and_the_questions():
    data = _data(**MIXED)
    summary = gr.build_summary(data, gr.calculate_overall_score(data))
    assert summary["schema_version"] == 2  # additive: no consumer breaks
    ids = {f["finding"]: f["id"] for f in summary["findings"]}
    assert summary["action_plan"]["Auto"] == [ids["Meta description missing."], ids["First <img> has no srcset attribute."]]
    assert set(summary["action_plan"]) == set(gr.LANES)
    assert {f["kind"] for f in summary["findings"]} == {"defect", "opportunity", "data_gap"}
    assert all(f["lane"] in gr.LANES or f["kind"] == "data_gap" for f in summary["findings"])
    assert any(q["id"] == "Q-pagespeed" for q in summary["open_questions"])
    planned = {fid for lane in summary["action_plan"].values() for fid in lane}
    assert not planned & {q["id"] for q in summary["open_questions"]}
    json.dumps(summary)


def test_gate_and_counts_still_see_every_finding():
    # The new kinds are a view: --fail-on and the severity counts are unchanged.
    data = _data(**MIXED)
    summary = gr.build_summary(data, gr.calculate_overall_score(data))
    assert sum(summary["counts"].values()) == len(summary["findings"]) == 8


# --- the HTML ----------------------------------------------------------------------------------

def test_plan_section_lists_lanes_in_order_with_the_fix_prompt():
    html = _html(_data(**MIXED))
    plan = _section(html, "plan")
    positions = [plan.index(f'id="lane-{lane.lower()}"') for lane in gr.LANES]
    assert positions == sorted(positions)
    auto = plan[positions[0]:positions[1]]
    assert "Meta description missing" in auto and "AI can fix now" in auto
    assert 'id="fix-prompt-text"' in auto and "Mode 3" in auto and "--previous" in auto
    assert "robots.txt blocks OAI-SearchBot" not in auto
    assert "Link equity by section was not measured" not in plan


def test_fix_prompt_names_only_the_auto_lane():
    data = _data(**MIXED)
    plan = gr.build_action_plan(_issues(data), gr.calculate_overall_score(data))
    prompt = gr.build_fix_prompt(data, plan["Auto"])
    assert "https://ex.com/" in prompt and "2026-09-18" in prompt
    assert "Meta description missing." in prompt and "Write a 150-character description." in prompt
    assert "OAI-SearchBot" not in prompt and "Wikidata" not in prompt


def test_open_questions_section_holds_the_gaps_and_findings_does_not():
    html = _html(_data(**MIXED))
    questions = _section(html, "questions")
    assert "Q-pagespeed" in questions and "Link equity by section was not measured." in questions
    assert "Could not verify sameAs URL" in questions
    findings = _section(html, "findings")
    assert "Link equity by section was not measured." not in findings
    assert "2 moved to open questions" in findings
    assert "Needs a human" in findings  # the card says who acts


def test_verdict_counts_who_acts_and_starts_with_agent_work():
    data = _data(**MIXED)
    html = _html(data)
    verdict = _section(html, "verdict")
    lanes = re.search(r'<div class="figs lanes".*?</div></div>', verdict, re.S).group(0)
    # The fixture runs few checks, so most of its open questions are checks that never ran.
    open_count = len(gr.build_open_questions(data, gr.calculate_overall_score(data), _issues(data)))
    assert re.findall(r'<div class="fig[^"]*">(\d+)</div>', lanes) == ["2", "1", "2", str(open_count)]
    start = verdict[verdict.index('class="start'):]
    assert "Meta description missing" in start and "AI can fix now" in start


def test_start_here_still_names_a_more_severe_finding_an_agent_cannot_fix():
    data = _data(
        entity={"issues": [{"severity": "critical", "finding": "No Wikidata entry", "fix": "Create one"}]},
        image_seo={"score": 60, "issues": [{"severity": "medium", "finding": "No srcset on hero image.", "fix": "Add srcset."}]})
    start = _section(_html(data), "verdict")
    start = start[start.index('class="start'):]
    assert "No srcset on hero image" in start and "Most severe" in start and "No Wikidata entry" in start


def test_clean_run_says_nothing_to_do_and_nothing_open():
    html = _html(_data())
    assert "Nothing to act on" in _section(html, "plan")
    assert "Nothing open" in gr._render_open_questions([])


def test_recommendations_are_not_restated_outside_the_appendix():
    html = _html(_data(**MIXED))
    assert '<section id="recommendations"' not in html and 'href="#recommendations"' not in html
