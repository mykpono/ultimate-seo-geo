"""The generate_report.py HTML follows the report design (references/report-template).

One spine for every report the skill produces: masthead with a coverage bar,
verdict and figures, what changed since the previous run, the Health Score by
category, scope and coverage, site shape, findings by kind, GEO readiness,
recommendations, platform, and the check details as an appendix. The page uses
report.css from the template package so the generator, the agent's HTML and the
client set share one design system.
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


def _data(**sections):
    base = {
        "security": {"score": 90}, "social": {"score": 40},
        "robots": {"status": 200, "sitemaps": ["s"], "ai_crawler_status": {}},
        "broken_links": {"summary": {"total": 50, "broken": 2}}, "readability": {"flesch_reading_ease": 45},
        "content_quality": {"score": 55}, "schema_validation": {"score": 30}, "sitemap": {"score": 100},
        "onpage": {"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
    }
    base.update(sections)
    return {"url": "https://ex.com/", "domain": "ex.com", "timestamp": "2026-09-17T10:00:00",
            "environment": {"primary": "Webflow", "runtime": "Unknown", "confidence": "low", "signals": [], "alternatives": []},
            "environment_fixes": [], "sections": base}


ARCHITECTURE = {
    "site": "https://ex.com/", "site_type": "saas",
    "inventory": {"total": 120, "fetched": 40, "sitemap_urls": 120, "complete": True, "reasons": []},
    "navigation": {"status": "measured", "sections": ["pricing"]},
    "sections": [
        {"path": "/blog/", "parent": None, "url_count": 100, "dominant_label": "blog_article", "in_nav": False,
         "hub": {"exists": True}, "avg_depth": 1.0, "equity_share": None},
        {"path": "/blog/guides/", "parent": "/blog/", "url_count": 12, "dominant_label": "pillar_guide", "in_nav": False,
         "hub": {"exists": False}, "avg_depth": 2.0, "equity_share": None},
    ],
    "equity": {"status": "not measured", "reason": "crawl incomplete", "by_section": {}, "top_pages": []},
    "hygiene": {}, "mermaid": "graph TD\n  root[\"ex.com\"]", "issues": [],
}
PAGE_TYPES = {
    "site": "https://ex.com/", "site_type": "saas", "urls_classified": 120, "urls_fetched": 40,
    "source": {"status": "complete", "sitemap_complete": True, "crawl_complete": False, "reasons": []},
    "matrix": {"blog_article": {"count": 100, "share": 0.83, "intent": "TOFU", "families": ["blog"]},
               "pricing": {"count": 1, "share": 0.01, "intent": "BOFU", "families": [None]},
               "comparison": {"count": 0, "share": 0.0, "intent": "BOFU", "families": []}},
    "by_intent": {"TOFU": {"count": 100, "share": 0.83}, "BOFU": {"count": 1, "share": 0.01}, "trust": {"count": 0, "share": 0.0}},
    "expected": ["pricing", "comparison"],
    "issues": [{"type": "missing_page_type", "severity": "Medium", "finding": "No comparison pages found on a saas site.",
                "evidence": "0 of 120 URLs match comparison patterns.", "impact": "Most-cited type absent.",
                "fix": "Create /vs/[competitor]/ pages.", "confidence": "Likely", "tags": ["opportunity"], "label": "comparison"}],
}


def _html(data, **kwargs):
    return gr.generate_html(data, gr.calculate_overall_score(data), **kwargs)


def _section(html, sid):
    match = re.search(r'<section id="%s".*?</section>' % re.escape(sid), html, re.S)
    return match.group(0) if match else ""


# --- one design system --------------------------------------------------------

def test_report_inlines_the_template_design_system():
    html = _html(_data())
    with open(os.path.join(ROOT, "references", "report-template", "report.css"), encoding="utf-8") as fh:
        css = fh.read()
    assert "--accent:#0D6E74" in css and "--accent:#0D6E74" in html
    assert "@media print" in html
    assert "fonts.googleapis.com" in html and "IBM+Plex+Sans" in html
    # No CDN scripts: the only script is the inline one.
    assert re.search(r"<script[^>]+src=", html) is None


def test_missing_template_css_falls_back_and_warns(monkeypatch, capsys):
    monkeypatch.setattr(gr.os.path, "join", lambda *parts: "/nonexistent/" + "/".join(parts) if "report-template" in parts else os.path.join(*parts))
    html = _html(_data())
    assert "--accent:#0D6E74" in html  # the fallback carries the same tokens
    assert "using the embedded fallback stylesheet" in capsys.readouterr().err


# --- the spine ------------------------------------------------------------------

def test_sections_follow_the_spine_in_order():
    html = _html(_data(page_types=PAGE_TYPES, navigation={"status": "measured", "primary_nav": {"count": 3}, "footer_nav": {"count": 1},
                                                          "breadcrumbs": {"with_visible": 2, "with_jsonld": 2}, "issues": []},
                       architecture=ARCHITECTURE))
    order = ["verdict", "score", "coverage", "shape", "findings", "geo", "recommendations", "platform", "appendix"]
    positions = [html.index(f'<section id="{sid}"') for sid in order]
    assert positions == sorted(positions)
    nav = re.search(r'<nav class="toc".*?</nav>', html, re.S).group(0)
    for sid in order:
        assert f'href="#{sid}"' in nav


def test_site_shape_is_omitted_when_no_structure_check_ran():
    html = _html(_data())
    assert '<section id="shape"' not in html
    assert 'href="#shape"' not in html


# --- masthead and coverage bar ------------------------------------------------------

def test_masthead_carries_the_coverage_bar_and_the_absence_claims_verdict():
    html = _html(_data(page_types=PAGE_TYPES, architecture=ARCHITECTURE, pagespeed={"error": "Rate limited"},
                       hreflang={"hreflang_tags_found": 0}))
    bar = re.search(r'<div class="covbar".*?</div>', html, re.S).group(0)
    weighted = int(re.search(r"<b>(\d+)</b> checks weighted", bar).group(1))
    display = int(re.search(r"<b>(\d+)</b> shown, not weighted", bar).group(1))
    deferred = int(re.search(r"<b>(\d+)</b> not measured", bar).group(1))
    assert weighted >= 5 and display >= 2 and deferred >= 1
    assert "Inventory complete · absence claims allowed" in bar
    assert "Site type" in html and "saas" in html


def test_incomplete_inventory_withholds_absence_claims():
    arch = dict(ARCHITECTURE, inventory=dict(ARCHITECTURE["inventory"], complete=False))
    html = _html(_data(architecture=arch, page_types=dict(PAGE_TYPES, source={"status": "incomplete"})))
    assert "absence claims withheld" in html
    assert "Inventory incomplete" in html


def test_white_label_slots_are_rendered_escaped_and_accent_overrides_the_token():
    html = _html(_data(), options={"prepared_for": "Acme <b>Ltd</b>", "prepared_by": "Jo & Co", "accent": "#B83F00"})
    assert "Acme &lt;b&gt;Ltd&lt;/b&gt;" in html and "Jo &amp; Co" in html
    assert ":root{--accent:#B83F00}" in html
    assert html.index("--accent:#0D6E74") < html.index(":root{--accent:#B83F00}")


def test_invalid_accent_is_rejected():
    with pytest.raises(ValueError):
        _html(_data(), options={"accent": "red"})


# --- verdict, figures, start here -----------------------------------------------------

def test_verdict_leads_with_figures_then_start_here():
    html = _html(_data(entity={"issues": [{"severity": "high", "finding": "No Wikidata entry", "fix": "Create one"}]}))
    verdict = _section(html, "verdict")
    assert verdict.index('class="figs"') < verdict.index('class="verdict"') < verdict.index('class="start"')
    assert "Start here" in verdict and 'href="#F01"' in verdict and "No Wikidata entry" in verdict
    assert "Critical findings" in verdict


def test_clean_audit_start_here_says_so():
    verdict = _section(_html(_data()), "verdict")
    assert "No critical or warning findings" in verdict


# --- health score -------------------------------------------------------------------------

def test_score_block_shows_every_group_with_a_bar_or_a_hatched_track():
    html = _html(_data(pagespeed={"error": "Rate limited"}))
    score = _section(html, "score")
    for label in gr.CHECK_GROUPS.values():
        assert label in score
    assert "Source: generate_report.py" in score
    assert 'class="track nm"' in score  # Core Web Vitals not measured
    assert "not measured: Performance (Core Web Vitals)" in score
    bars = re.findall(r'<div class="track"><i style="width:(\d+)%"></i></div>', score)
    assert bars and all(0 <= int(b) <= 100 for b in bars)


def test_inconclusive_score_is_not_presented_as_a_number():
    data = _data()
    data["sections"] = {"security": {"score": 90}, "social": {"score": 40}}
    html = _html(data)
    assert "Inconclusive" in _section(html, "score")
    assert "Health Score inconclusive" in _section(html, "verdict")


# --- delta since the previous run ------------------------------------------------------------

def _summary(data):
    return gr.build_summary(data, gr.calculate_overall_score(data))


def test_compare_with_previous_matches_findings_by_wording_not_id():
    now = _summary(_data(entity={"issues": [{"severity": "high", "finding": "No Wikidata entry", "fix": "x"}]},
                         social={"score": 90}))
    then = _summary(_data(internal_links={"issues": ["⚠️ 27 links have no anchor text"]}))
    then["timestamp"] = "2026-08-17T10:00:00"
    delta = gr.compare_with_previous(now, then)
    assert delta["score_delta"] == now["overall"] - then["overall"]
    assert [f["finding"] for f in delta["resolved"]] == ["27 links have no anchor text"]
    assert [f["finding"] for f in delta["new"]] == ["No Wikidata entry"]
    assert {"check": "social", "label": "Social meta", "from": "Gap", "to": "Strong"} in delta["status_changes"]


def test_delta_strip_renders_only_with_a_previous_summary():
    data = _data(entity={"issues": [{"severity": "high", "finding": "No Wikidata entry", "fix": "x"}]})
    assert 'class="delta"' not in _html(data)
    previous = _summary(_data())
    previous["timestamp"] = "2026-08-17T10:00:00"
    html = _html(data, previous_summary=previous)
    strip = re.search(r'<div class="delta".*?</div>\s*</section>', html, re.S).group(0)
    assert "2026-08-17" in strip and "New findings" in strip and "F01" in strip


# --- coverage and checks ---------------------------------------------------------------------

def test_coverage_table_says_what_counts_toward_the_score():
    html = _html(_data(page_types=PAGE_TYPES, architecture=ARCHITECTURE, pagespeed={"error": "Rate limited"},
                       hreflang={"hreflang_tags_found": 0}))
    coverage = _section(html, "coverage")
    def row(key):
        return re.search(r'<tr data-key="%s".*?</tr>' % key, coverage, re.S).group(0)
    assert "weighted" in row("security")
    assert "shown, not weighted" in row("page_types") and "—" in row("page_types")
    assert "not measured" in row("pagespeed")
    assert "Not applicable" in row("hreflang")
    assert "120" in coverage and "sitemap URLs" in coverage


# --- site shape --------------------------------------------------------------------------------

def test_site_shape_renders_funnel_tree_and_reconciliation():
    html = _html(_data(page_types=PAGE_TYPES, architecture=ARCHITECTURE,
                       navigation={"status": "measured", "primary_nav": {"count": 3}, "footer_nav": {"count": 1},
                                   "breadcrumbs": {"with_visible": 2, "with_jsonld": 1}, "issues": []},
                       sitemap={"score": 100, "reconcile": {"crawled_not_in_sitemap": {"count": 7}}}))
    shape = _section(html, "shape")
    assert 'class="funnel"' in shape and "TOFU" in shape and 'class="gap"' in shape  # trust is 0
    assert "/blog/" in shape and "/blog/guides/" in shape and "no hub" in shape and "not in nav" in shape
    assert "Mismatch" in shape and "Indexable pages not in the sitemap" in shape and "Withheld" in shape
    assert "Expected page types missing" in shape and "comparison" in shape


def test_not_measured_navigation_is_never_reported_as_absent():
    shape = _section(_html(_data(architecture=ARCHITECTURE, navigation={"status": "not_measured", "issues": []})), "shape")
    assert "Not measured" in shape


# --- findings by kind ----------------------------------------------------------------------------

def test_opportunities_render_apart_from_the_severity_list():
    html = _html(_data(page_types=PAGE_TYPES,
                       entity={"issues": [{"severity": "high", "finding": "No Wikidata entry", "fix": "Create one",
                                           "evidence": "0 results", "impact": "Invisible", "confidence": "Confirmed",
                                           "falsifiability": "Assistants already cite the brand",
                                           "leading_indicator": "Entity resolves in 2 weeks", "dependency": "none"}]}))
    findings = _section(html, "findings")
    index = re.search(r'<tbody id="finding-rows">.*?</tbody>', findings, re.S).group(0)
    assert 'data-key="F01"' in index and "No comparison pages found" not in index
    opp = findings[findings.index('id="opportunities"'):]
    assert "No comparison pages found" in opp and 'class="find opp"' in opp and "Opportunity" in opp
    card = re.search(r'<article class="find c"[^>]*id="F01".*?</article>', findings, re.S).group(0)
    for field in ("Evidence", "Impact", "Confidence", "Wrong if:", "Fix", "Watch", "Depends on", "script:entity"):
        assert field in card


def test_filter_buttons_cover_rows_and_cards():
    html = _html(_data(internal_links={"issues": ["🔴 3 pages return 404", "⚠️ 27 links have no anchor text", "plain note"]}))
    findings = _section(html, "findings")
    assert 'data-filter="critical"' in findings and 'aria-pressed="true"' in findings
    assert '<article class="find c" data-key="F01" data-filter="critical"' in findings
    assert '<tr data-key="F03" data-filter="info"' in findings


# --- GEO readiness -----------------------------------------------------------------------------------

def test_geo_readiness_lists_each_check_with_its_status():
    html = _html(_data(entity={"score": 0, "issues": [{"severity": "high", "finding": "No Wikidata entry", "fix": "x"}]}))
    geo = _section(html, "geo")
    for key, _question in gr._GEO_QUICK:
        assert f'href="#check-{key}"' in geo
    assert 'class="no"' in geo and "Entity SEO" in geo


# --- appendix -----------------------------------------------------------------------------------------

def test_check_details_live_in_the_appendix_all_visible():
    html = _html(_data())
    appendix = _section(html, "appendix")
    for key in gr.CHECK_LABELS:
        assert f'id="check-{key}"' in appendix
    assert re.search(r"<article[^>]*\shidden", html) is None


# --- CLI ---------------------------------------------------------------------------------------------

def test_cli_rejects_a_bad_accent_and_a_bad_previous(tmp_path):
    script = os.path.join(ROOT, "scripts", "generate_report.py")
    bad = subprocess.run([sys.executable, script, "https://ex.com/", "--accent", "teal"], capture_output=True, text=True)
    assert bad.returncode == 2 and "--accent" in bad.stderr
    previous = tmp_path / "prev.json"
    previous.write_text("{}")
    bad = subprocess.run([sys.executable, script, "https://ex.com/", "--previous", str(previous)], capture_output=True, text=True)
    assert bad.returncode == 2 and "--previous" in bad.stderr


def test_summary_json_carries_the_comparison(monkeypatch, tmp_path):
    previous = _summary(_data())
    previous["timestamp"] = "2026-08-17T10:00:00"
    prev_path = tmp_path / "prev.json"
    prev_path.write_text(json.dumps(previous))
    out = tmp_path / "summary.json"
    monkeypatch.setattr(gr, "collect_data", lambda url, **kw: _data(entity={"issues": [{"severity": "high", "finding": "New", "fix": "x"}]}))
    monkeypatch.setattr(sys, "argv", ["generate_report.py", "https://ex.com/", "--format", "none", "--json", str(out),
                                      "--previous", str(prev_path)])
    gr.main()
    summary = json.loads(out.read_text())
    assert summary["previous"]["overall"] == previous["overall"]
    assert [f["finding"] for f in summary["previous"]["new"]] == ["New"]
