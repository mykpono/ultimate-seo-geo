"""Search Console clicks joined to report findings (generate_report.py --gsc-pages / --gsc-property).

Severity says how wrong a finding is; clicks say what it costs. The join must
only print a number when a URL ties it to the finding, must leave the score
and the finding set untouched, and must leave a run without Search Console
data exactly as it was.
"""

import json
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report as gr  # noqa: E402

PAGES = [
    {"page": "https://www.ex.com/", "clicks": 900, "impressions": 20000},
    {"page": "https://www.ex.com/pricing/", "clicks": 400, "impressions": 8000},
    {"page": "https://www.ex.com/blog/old", "clicks": 50, "impressions": 3000},
]


def _data(traffic=True, **sections):
    base = {
        "security": {"score": 60, "issues": [{"severity": "medium", "finding": "HSTS header missing.", "fix": "Add HSTS."}]},
        "onpage": {"title": "t", "meta_description": "", "h1": ["h"], "canonical": "https://ex.com/", "issues": [
            {"severity": "medium", "finding": "Meta description missing.", "fix": "Write one."}]},
        "broken_links": {"summary": {"total": 5, "broken": 2}, "issues": [
            {"severity": "medium", "finding": "Broken internal link on https://ex.com/pricing to /gone.", "fix": "Fix the link.",
             "url": "https://ex.com/pricing"},
            {"severity": "medium", "finding": "Broken external link to https://other.org/x.", "fix": "Remove it."}]},
        "duplicate_content": {"issues": [
            {"severity": "medium", "finding": "Near-duplicate pages.", "fix": "Merge them.",
             "urls": ["https://ex.com/blog/old", "https://ex.com/blog/never-clicked"]}]},
        "link_profile": {"issues": [{"severity": "medium", "finding": "Low link diversity.", "fix": "Earn links."}]},
    }
    base.update(sections)
    data = {"url": "https://ex.com/", "domain": "ex.com", "timestamp": "2026-09-22T10:00:00",
            "environment": {"primary": "Webflow", "runtime": "Unknown", "confidence": "low", "signals": [], "alternatives": []},
            "environment_fixes": [], "sections": base}
    if traffic:
        data["gsc_traffic"] = gr.traffic_from_pages(PAGES, "gsc_insights.py", ["2026-08-24", "2026-09-20"])
    return data


def _by_finding(data):
    return {i["finding"]: i for i in gr._collect_issues(data)}


def test_traffic_key_ignores_www_scheme_and_trailing_slash():
    assert gr.traffic_key("https://www.EX.com/pricing/") == gr.traffic_key("http://ex.com/pricing") == "ex.com/pricing"
    assert gr.traffic_key("https://ex.com") == "ex.com/"


def test_named_urls_are_charged_their_clicks():
    issue = _by_finding(_data())["Broken internal link on https://ex.com/pricing to /gone."]
    assert issue["traffic"]["scope"] == "pages"
    assert (issue["traffic"]["clicks"], issue["traffic"]["impressions"]) == (400, 8000)
    assert issue["traffic"]["urls_named"] == 1 and issue["traffic"]["basis"] == "URLs named in the finding"


def test_only_urls_that_earn_clicks_are_counted_and_the_rest_are_reported():
    issue = _by_finding(_data())["Near-duplicate pages."]
    assert (issue["traffic"]["clicks"], issue["traffic"]["urls_named"], issue["traffic"]["urls_matched"]) == (50, 2, 1)
    assert "1 of 2 URLs" in gr.traffic_text(issue["traffic"])


def test_other_sites_urls_are_never_charged():
    """A broken EXTERNAL link names another host; its clicks are not this site's to lose."""
    issue = _by_finding(_data())["Broken external link to https://other.org/x."]
    assert issue["traffic"] is None


def test_page_scoped_check_without_a_url_is_the_audited_page():
    issue = _by_finding(_data())["Meta description missing."]
    assert issue["traffic"]["clicks"] == 900 and issue["traffic"]["basis"] == "the audited page"


def test_site_wide_check_gets_no_per_page_figure():
    issue = _by_finding(_data())["HSTS header missing."]
    assert issue["traffic"] == {"scope": "site", "source": "gsc_insights.py", "window": ["2026-08-24", "2026-09-20"]}
    assert "no per-page figure" in gr.traffic_text(issue["traffic"])


def test_data_gaps_carry_no_traffic():
    data = _data(entity={"issues": [{"severity": "info", "finding": "Could not verify sameAs URL: https://ex.com/about",
                                     "fix": "Check it by hand."}]})
    assert _by_finding(data)["Could not verify sameAs URL: https://ex.com/about"]["traffic"] is None


def test_search_performance_panel_explains_how_to_turn_it_on():
    data = _data(traffic=False)
    html = gr.generate_html(data, gr.calculate_overall_score(data))
    assert "--gsc-property sc-domain:example.com" in html


def test_unscoped_check_without_a_url_gets_nothing():
    assert _by_finding(_data())["Low link diversity."]["traffic"] is None


def test_named_urls_with_no_clicks_say_so_instead_of_printing_zero_as_a_cost():
    data = _data(duplicate_content={"issues": [{"severity": "medium", "finding": "Thin page.", "fix": "Expand.",
                                                "url": "https://ex.com/blog/never-clicked"}]})
    traffic = _by_finding(data)["Thin page."]["traffic"]
    assert traffic["clicks"] == 0 and traffic["urls_matched"] == 0
    assert gr.traffic_text(traffic).startswith("No Search Console clicks")


def test_action_plan_orders_by_clicks_inside_a_severity():
    issues = gr._collect_issues(_data())
    scores = gr.calculate_overall_score(_data())
    plan = gr.build_action_plan(issues, scores)
    auto = [i["finding"] for i in plan["Auto"]]
    # Same severity and lane: the audited page (900 clicks) before /pricing (400) before /blog/old (50).
    assert auto.index("Meta description missing.") < auto.index("Broken internal link on https://ex.com/pricing to /gone.")


def test_site_wide_findings_lead_their_severity():
    issues = gr._collect_issues(_data())
    plan = gr.build_action_plan(issues, gr.calculate_overall_score(_data()))
    assisted = [i["finding"] for i in plan["Assisted"]]
    assert assisted.index("HSTS header missing.") < assisted.index("Near-duplicate pages.")


def test_without_search_console_data_nothing_changes():
    with_gsc, without = _data(), _data(traffic=False)
    assert all(i["traffic"] is None for i in gr._collect_issues(without))
    before = gr.build_summary(without, gr.calculate_overall_score(without))
    after = gr.build_summary(with_gsc, gr.calculate_overall_score(with_gsc))
    assert before["overall"] == after["overall"] and before["counts"] == after["counts"]
    assert [f["code"] for f in before["findings"]] == [f["code"] for f in after["findings"]]
    assert before["search_console"] is None
    assert after["search_console"] == {"source": "gsc_insights.py", "window": ["2026-08-24", "2026-09-20"],
                                       "total_clicks": 1350, "total_impressions": 31000, "pages": 3}


def test_no_gsc_plan_order_is_the_old_order():
    """_traffic_rank is constant without data, so the old (severity, gain, id) order holds."""
    data = _data(traffic=False)
    issues = gr._collect_issues(data)
    scores = gr.calculate_overall_score(data)
    gains = gr.check_score_gains(scores)
    plan = gr.build_action_plan(issues, scores)
    for items in plan.values():
        assert items == sorted(items, key=lambda i: (gr.SEVERITY_SCALE.index(i["canonical_severity"]),
                                                     -gains.get(i["section"], 0), i["id"]))


def test_summary_and_html_carry_the_figure():
    data = _data()
    scores = gr.calculate_overall_score(data)
    summary = gr.build_summary(data, scores)
    finding = next(f for f in summary["findings"] if f["finding"].startswith("Broken internal"))
    assert finding["traffic_at_stake"]["clicks"] == 400
    html = gr.generate_html(data, scores)
    assert "Traffic at stake" in html and "400 clicks at stake" in html
    assert "Search Console clicks (2026-08-24 to 2026-09-20) break ties" in html


def test_search_performance_is_display_only_and_its_findings_reach_the_report():
    sp = {"windows": {"current": ["2026-08-24", "2026-09-20"]}, "query_page_rows": 10, "truncated": [],
          "ctr_curve": {"3": {"median_ctr": 0.1, "rows": 6}},
          "striking_distance": {"count": 1, "items": [{"query": "q", "page": "https://ex.com/pricing", "position": 11.0,
                                                        "impressions": 900, "upside_clicks_at_position_3": 86}]},
          "issues": [{"code": "striking_distance", "severity": "medium", "kind": "opportunity", "lane": "Auto",
                      "finding": "1 queries rank at average position 8-15.", "fix": "Add the query to the title.",
                      "urls": ["https://ex.com/pricing"]}]}
    data = _data(search_performance=sp)
    scores = gr.calculate_overall_score(data)
    baseline = gr.calculate_overall_score(_data())
    assert scores["overall"] == baseline["overall"]
    assert "search_performance" not in gr.CHECK_WEIGHTS
    issue = _by_finding(data)["1 queries rank at average position 8-15."]
    assert issue["kind"] == "opportunity" and issue["traffic"]["clicks"] == 400
    html = gr.generate_html(data, scores)
    assert 'id="check-search_performance"' in html and "Striking distance (position 8-15)" in html


def test_collect_data_runs_gsc_insights_only_with_a_property(monkeypatch):
    calls = []

    def fake_run(script, args, timeout=120):
        calls.append((script, args))
        if script == "gsc_insights.py":
            return {"windows": {"current": ["a", "b"]}, "pages": PAGES, "issues": []}
        return {}

    monkeypatch.setattr(gr, "run_script", fake_run)
    monkeypatch.setattr(gr, "fetch_page", lambda url, render="never": ("", ""))
    monkeypatch.setattr(gr, "build_site_graph", lambda url: None)
    data = gr.collect_data("https://ex.com/")
    assert not any(s == "gsc_insights.py" for s, _ in calls) and "gsc_traffic" not in data
    calls.clear()
    data = gr.collect_data("https://ex.com/", gsc_property="sc-domain:ex.com")
    assert ("gsc_insights.py", ["sc-domain:ex.com", "--all"]) in calls
    assert data["gsc_traffic"]["total_clicks"] == 1350


def test_cli_rejects_an_unreadable_pages_file(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "Queries.csv"
    bad.write_text("Top queries,Clicks\nx,1\n")
    monkeypatch.setattr(sys, "argv", ["generate_report.py", "https://ex.com/", "--gsc-pages", str(bad)])
    with pytest.raises(SystemExit) as exc:
        gr.main()
    assert exc.value.code == 2 and "--gsc-pages" in capsys.readouterr().err
