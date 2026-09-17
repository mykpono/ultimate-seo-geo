"""The site-structure checks in generate_report.py: shown, never weighted.

v1.14.0 contract: new heuristic checks appear in the report but do not enter
CHECK_WEIGHTS until validated on real audits. These tests pin that the four
P1–P5 scripts are wired in exactly that way: one shared crawl before the
parallel batch, three display-only rows, findings in the summary with a null
weight, and an `overall` that does not move when they run.
"""

import inspect
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_report as gr  # noqa: E402

STRUCTURE = ("page_types", "navigation", "architecture")


def test_structure_checks_are_labelled_grouped_and_unweighted():
    for key in STRUCTURE:
        assert key in gr.CHECK_LABELS and key in gr.CHECK_GROUP, key
        assert key not in gr.CHECK_WEIGHTS, f"{key} must stay display-only"
    assert set(gr.DISPLAY_ONLY_CHECKS) == set(STRUCTURE)


def test_collect_data_builds_the_graph_once_and_passes_it_to_the_checkers():
    src = inspect.getsource(gr.collect_data)
    assert "build_site_graph(url)" in src
    assert '("page_types", "page_type_classifier.py", structure_args)' in src
    assert '("navigation", "navigation_checker.py", structure_args)' in src
    assert '("architecture", "site_architecture.py", structure_args)' in src
    assert '"--reconcile", graph_path' in src
    assert "os.unlink(graph_path)" in src


def test_build_site_graph_failure_returns_none_and_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(gr, "run_script", lambda name, args, timeout=120: {"error": "boom"})
    assert gr.build_site_graph("https://ex.com/") is None


def test_build_site_graph_returns_the_written_path(monkeypatch):
    def fake_run(name, args, timeout=120):
        out = args[args.index("--out") + 1]
        with open(out, "w") as fh:
            json.dump({"pages": {}, "crawl": {}}, fh)
        assert name == "site_graph.py" and args[0] == "https://ex.com/"
        assert timeout == gr._SCRIPT_TIMEOUT_CRAWL
        return {"ok": True}
    monkeypatch.setattr(gr, "run_script", fake_run)
    path = gr.build_site_graph("https://ex.com/")
    assert path and os.path.exists(path)
    os.unlink(path)


def _data(**sections):
    base = {
        "security": {"score": 90}, "social": {"score": 40},
        "robots": {"status": 200, "sitemaps": ["s"], "ai_crawler_status": {}},
        "broken_links": {"summary": {"total": 50, "broken": 2}}, "readability": {"flesch_reading_ease": 45},
        "content_quality": {"score": 55}, "schema_validation": {"score": 30}, "sitemap": {"score": 100},
        "onpage": {"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
    }
    base.update(sections)
    return {"url": "https://ex.com/", "domain": "ex.com", "timestamp": "2026-09-17T10:00:00", "sections": base}


PAGE_TYPES = {
    "site": "https://ex.com/", "site_type": "saas", "urls_classified": 120, "urls_fetched": 40,
    "source": {"status": "complete", "sitemap_complete": True, "crawl_complete": False, "reasons": []},
    "matrix": {"blog_article": {"count": 100, "share": 0.83, "intent": "TOFU", "families": ["blog"]},
               "pricing": {"count": 1, "share": 0.01, "intent": "BOFU", "families": [None]},
               "comparison": {"count": 0, "share": 0.0, "intent": "BOFU", "families": []}},
    "expected": ["pricing", "comparison"],
    "issues": [{"type": "missing_page_type", "severity": "Medium", "finding": "No comparison pages found on a saas site.",
                "evidence": "0 of 120 URLs match comparison patterns.", "impact": "Most-cited type absent.",
                "fix": "Create /vs/[competitor]/ pages.", "confidence": "Likely", "tags": ["opportunity"], "label": "comparison"}],
}
NAVIGATION = {"site": "https://ex.com/", "site_type": "saas", "status": "measured", "sampled_pages": 40, "method": "m",
              "primary_nav": {"count": 2, "internal": 2, "links": [{"anchor": "Pricing", "href": "https://ex.com/pricing"}]},
              "footer_nav": {"count": 0, "internal": 0, "links": []}, "repeating_unlabelled": {"count": 0, "links": []},
              "taxonomy": {"sections": ["pricing"], "nav_links": []},
              "breadcrumbs": {"with_visible": 0, "with_jsonld": 0, "mismatches": [], "missing_on_deep_pages_count": 0, "deep_pages": 0},
              "issues": [{"type": "nav_link_broken", "severity": "High", "finding": "1 global navigation link(s) return an error.",
                          "evidence": "e", "impact": "i", "fix": "f", "confidence": "Confirmed"}]}
ARCHITECTURE = {"site": "https://ex.com/", "site_type": "saas", "inventory": {"total": 120, "fetched": 40, "sitemap_urls": 120, "complete": True, "reasons": []},
                "navigation": {"status": "measured", "sections": ["pricing"]},
                "sections": [{"path": "/blog/", "parent": None, "url_count": 100, "dominant_label": "blog_article", "in_nav": False, "hub": {"exists": True}, "avg_depth": 1.0, "equity_share": None}],
                "equity": {"status": "not measured", "reason": "crawl incomplete", "by_section": {}, "top_pages": []},
                "hygiene": {}, "mermaid": "graph TD\n  root[\"ex.com\"]", "issues": []}


def test_structure_findings_reach_the_summary_unweighted_and_the_score_does_not_move():
    without = _data()
    with_structure = _data(page_types=PAGE_TYPES, navigation=NAVIGATION, architecture=ARCHITECTURE)
    s0 = gr.build_summary(without, gr.calculate_overall_score(without))
    s1 = gr.build_summary(with_structure, gr.calculate_overall_score(with_structure))
    assert s1["overall"] == s0["overall"]
    assert s1["measured_categories"] == s0["measured_categories"]
    by_section = {f["section"]: f for f in s1["findings"]}
    assert by_section["page_types"]["tags"] == ["opportunity"]
    assert by_section["page_types"]["severity"] == "medium" and by_section["page_types"]["level"] == "warning"
    assert by_section["page_types"]["confidence"] == "Likely" and by_section["page_types"]["evidence"].startswith("0 of 120")
    assert by_section["navigation"]["severity"] == "high"
    for key in STRUCTURE:
        assert key not in s1["categories"] or s1["categories"][key]["weight"] is None


def test_display_only_status_follows_the_findings():
    assert gr._check_status("page_types", PAGE_TYPES, None) == ("flag", "Needs work")
    assert gr._check_status("navigation", NAVIGATION, None) == ("gap", "Gap")
    assert gr._check_status("architecture", ARCHITECTURE, None) == ("ok", "Reviewed")
    assert gr._check_status("navigation", dict(NAVIGATION, status="not_measured"), None) == ("deferred", "Not measured")
    assert gr._check_status("page_types", {"error": "timeout"}, None) == ("deferred", "Not measured")
    assert gr._check_status("page_types", {}, None) == ("na", "Not run")


def test_html_renders_the_three_panels_with_their_data():
    data = _data(page_types=PAGE_TYPES, navigation=NAVIGATION, architecture=ARCHITECTURE)
    html = gr.generate_html(data, gr.calculate_overall_score(data))
    assert "Page-type coverage" in html and "Navigation and breadcrumbs" in html and "Site architecture" in html
    assert "blog article" in html and "Expected types missing" in html and "comparison" in html
    assert "https://ex.com/pricing" in html
    assert "/blog/" in html and "graph TD" in html
    assert "No comparison pages found" in html
    import re
    for key in STRUCTURE:
        assert f'data-key="{key}"' in html
        card = re.search(rf'<article class="card detail" data-key="{key}".*?</article>', html, re.S).group(0)
        assert "/ 100" not in card, f"{key} must not show a score"
        row = re.search(rf'<tr data-key="{key}".*?</tr>', html, re.S).group(0)
        assert "meter" not in row and row.count("—") >= 2, f"{key} row must show no score and no weight"


def test_ci_json_carries_structure_findings(monkeypatch, tmp_path, capsys):
    data = _data(page_types=PAGE_TYPES)
    out = tmp_path / "summary.json"
    with patch.object(gr, "collect_data", return_value=data):
        monkeypatch.setattr(sys, "argv", ["generate_report.py", "https://ex.com/", "--format", "none", "--json", str(out)])
        try:
            gr.main()
        except SystemExit as exc:
            assert exc.code in (0, None)
    summary = json.loads(out.read_text())
    assert any(f["section"] == "page_types" and "opportunity" in f["tags"] for f in summary["findings"])
