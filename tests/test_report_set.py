"""The client report set is rendered from one source and checked by one lint.

Pins the contract in references/report-template/report-template.md: findings and
recommendations carry their fields and point at IDs that exist, the blocked-by
graph is acyclic, display-only evidence never carries a score, opportunities
and strengths render outside the findings list, an absence claim about site
structure needs a complete inventory, the start-today view only lists work an
agent can begin, and the report is one self-contained HTML page that links IDs
in place and renders each thing once.
"""

import copy
import json
import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import render_report  # noqa: E402
import report_data_lint  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _source():
    return {
        "schema_version": 1,
        "meta": {"client": "Example", "site": "https://example.com", "prepared_for": "Example team", "prepared_by": "Tester",
                 "date": "2026-09-17", "data_window": "Aug 2026", "site_type": "saas", "version": "0.1"},
        "docs": {
            "brief": {"verdict": "Brand demand is the risk; see F1 and T1."},
            "audit": {"verdict": "Verdict with `code` and **bold**.", "summary": [{"type": "p", "text": "Mentions F1, T1 and D1."}],
                      "sections": [{"id": "what", "title": "What happened", "blocks": [{"type": "table", "heads": ["A"], "rows": [["<b>x</b>"]]}]}]},
            "strategy": {"verdict": "Strategy."},
            "plan": {"verdict": "Plan."},
        },
        "coverage": {
            "graph": {"sitemap": {"found": True, "complete": True}, "crawl": {"complete": False, "reasons": ["max pages"]},
                      "summary": {"sitemap_urls": 3013, "pages_fetched": 120, "max_depth_seen": 4}, "generated_at": "2026-09-17T10:00:00Z"},
            "sources": [{"key": "gsc", "name": "Search Console", "kind": "api", "status": "weighted", "basis": "daily series"}],
            "not_examined": [{"name": "Backlinks", "reason": "no export yet", "enabled_by": ["M1"]}],
            "out_of_scope": [{"name": "Paid search", "reason": "not search"}],
            "assumptions": ["Homepage represents brand demand"],
        },
        "findings": [
            {"id": "F1", "kind": "defect", "severity": "critical", "order": 1, "title": "Brand demand is falling", "observation": "Clicks fell",
             "evidence": "1,004 → 719", "evidence_status": "weighted", "machine_source": "gsc:brand", "impact": "Pipeline",
             "confidence": "Confirmed", "falsifiability": "Clicks recover", "fixes": ["T1"], "watch": "Brand clicks weekly"},
            {"id": "F2", "kind": "keep", "severity": "info", "order": 2, "title": "Canonicals are correct", "observation": "Self-referencing",
             "evidence": "100 URLs", "evidence_status": "sampled", "confidence": "Confirmed", "falsifiability": "A stray noindex"},
            {"id": "F3", "kind": "opportunity", "severity": "medium", "order": 3, "title": "No comparison pages", "observation": "Zero comparison page type",
             "evidence": "0 of 3,013 URLs", "evidence_status": "display_only", "machine_source": "page_types:missing_page_type", "impact": "AI citations",
             "confidence": "Likely", "falsifiability": "Comparison pages exist under another URL scheme", "fixes": ["C1"], "watch": "Citations"},
        ],
        "recommendations": [
            {"id": "T1", "action": "Fix www redirect", "fixes": ["F1"], "basis": "Documented", "validity": "Confirmed", "tier": "Gated",
             "owner_role": "Engineering", "lane": "Human", "effort": "S", "effect": "Deep links pass value", "blocked_by": [], "unblocks": ["C1"],
             "done_when": "20 paths 301", "horizon": "now", "track": "A", "status": "planned"},
            {"id": "C1", "action": "Create comparison pages", "fixes": ["F3"], "basis": "Test first", "validity": "Revised", "tier": "Review",
             "owner_role": "Content", "lane": "Assisted", "effort": "M", "blocked_by": ["T1"], "unblocks": [], "done_when": "3 pages live",
             "horizon": "later", "track": "C", "status": "planned",
             "supersedes": {"check": "page_types", "finding_id": "missing_page_type", "reason": "Third-party /vs/ pages are retired first"}},
            {"id": "M1", "action": "Export links report", "fixes": ["F1"], "basis": "Documented", "tier": "Free", "owner_role": "Analytics",
             "lane": "Auto", "effort": "S", "done_when": "CSV stored", "horizon": "now", "status": "planned"},
            {"id": "C2", "action": "Decide pricing", "fixes": ["F1"], "basis": "Data-backed", "validity": "Dropped", "tier": "Review",
             "owner_role": "Leadership", "lane": "Decision", "decision": "D1", "effort": "S", "done_when": "Decided", "horizon": "weeks_1_4",
             "status": "dropped"},
        ],
        "decisions": [{"id": "D1", "question": "Publish pricing?", "owner_role": "Leadership"}],
        "prompts": {"tiers": [{"tier": "Tier 1", "note": "Category", "rows": [{"id": "T1.1", "prompt": "Best platform?", "owner": "/products", "note": "needs qualifier"}]}]},
        "pages": [{"wave": "Wave 1", "type": "Consolidate", "url": "/products/x", "prompts": ["T1.1"],
                   "fields": {"Today": "551 words", "Change": "301 the duplicate (T1)", "Test": "one URL ranks"}, "recs": ["T1"]}],
        "validity": {"summary": [{"type": "p", "text": "Held up."}]},
        "tests": [{"claim": "X", "disproved_by": "Y", "design": "Z"}],
        "glossary": [{"term": "GEO", "definition": "Generative engine optimization"}],
        "structure": {"architecture": {"sections": [
            {"path": "/blog", "parent": None, "url_count": 900, "dominant_label": "blog_article", "in_nav": True, "hub": {"exists": True}, "avg_depth": 2.1, "equity_share": 0.6},
            {"path": "/blog/x", "parent": "/blog", "url_count": 10, "dominant_label": "blog_article", "in_nav": False, "hub": {"exists": False}, "avg_depth": 3}],
            "inventory": {"total": 3013, "complete": True}, "equity": {"status": "measured"}, "mermaid": "graph TD\n root --> s0[/blog]"}},
    }


def _errors(src):
    return {e["rule"] for e in report_data_lint.lint(src)["errors"]}


# --- lint ---------------------------------------------------------------------

def test_fixture_source_is_clean():
    result = report_data_lint.lint(_source())
    assert result["errors"] == []
    assert result["findings"] == 3 and result["recommendations"] == 4


def test_fix_must_point_at_an_existing_recommendation():
    src = _source()
    src["findings"][0]["fixes"] = ["T99"]
    assert "orphan-id" in _errors(src)


def test_recommendation_must_fix_a_finding_and_use_the_scales():
    src = _source()
    src["recommendations"][0]["fixes"] = []
    src["recommendations"][1]["lane"] = "Robot"
    src["recommendations"][2]["tier"] = "Maybe"
    errs = _errors(src)
    assert {"missing-field", "scale"} <= errs


def test_blocked_by_cycle_is_an_error():
    src = _source()
    src["recommendations"][0]["blocked_by"] = ["C1"]   # T1 <- C1 <- T1
    assert "dependency-cycle" in _errors(src)


def test_display_only_finding_never_carries_a_score():
    src = _source()
    src["findings"][2]["score"] = 40
    assert "display-only-scored" in _errors(src)


def test_keep_finding_has_no_fix_and_defects_need_impact():
    src = _source()
    src["findings"][1]["fixes"] = ["T1"]
    del src["findings"][0]["impact"]
    errs = _errors(src)
    assert {"keep-has-fix", "missing-field"} <= errs


def test_absence_claim_needs_a_complete_inventory():
    src = _source()
    src["coverage"]["graph"]["sitemap"]["complete"] = False
    assert "absence-claim" in _errors(src)
    src["coverage"]["graph"]["crawl"]["complete"] = True
    assert "absence-claim" not in _errors(src)


def test_decision_lane_names_a_listed_decision():
    src = _source()
    src["recommendations"][3]["decision"] = "D9"
    assert "orphan-id" in _errors(src)
    del src["recommendations"][3]["decision"]
    assert "decision-missing" in _errors(src)


def test_dropped_validity_needs_dropped_status():
    src = _source()
    src["recommendations"][3]["status"] = "planned"
    assert "dropped-status" in _errors(src)


def test_health_score_needs_generate_report_source():
    src = _source()
    src["health_score"] = {"overall": 72, "source": "estimated"}
    assert "score-source" in _errors(src)
    src["health_score"] = {"overall": 72, "source": "generate_report.py — 9 weighted checks measured"}
    assert "score-source" not in _errors(src)


def test_unmeasured_cwv_numbers_are_rejected():
    src = _source()
    src["findings"][0]["evidence_status"] = "not_measured"
    src["findings"][0]["evidence"] = "INP 241 ms on mobile"
    assert "unmeasured-number" in _errors(src)


def test_lint_cli_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_source()), encoding="utf-8")
    bad_src = _source()
    bad_src["findings"][0]["fixes"] = ["T99"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(bad_src), encoding="utf-8")
    script = os.path.join(ROOT, "scripts", "report_data_lint.py")
    assert subprocess.run([sys.executable, script, str(good)], capture_output=True).returncode == 0
    run = subprocess.run([sys.executable, script, str(bad), "--json"], capture_output=True, text=True)
    assert run.returncode == 1
    assert any(e["rule"] == "orphan-id" for e in json.loads(run.stdout)["errors"])
    assert subprocess.run([sys.executable, script, str(tmp_path / "missing.json")], capture_output=True).returncode == 2



def _warnings(src):
    return {w["rule"] for w in report_data_lint.lint(src)["warnings"]}


def _duplicate_ids(src):
    markup = re.sub(r"<script\b.*?</script>", "", render_report.render(src), flags=re.S)
    found = re.findall(r'\bid="([^"]+)"', markup)
    return sorted({i for i in found if found.count(i) > 1})


@pytest.mark.parametrize("change", [
    lambda s: s["docs"]["audit"]["sections"].append({"id": "what", "title": "Again", "blocks": []}),        # twice in one part
    lambda s: s["docs"]["audit"]["sections"].append({"id": "findings", "title": "Mine", "blocks": []}),    # the renderer's own section
    lambda s: s["docs"].setdefault("strategy", {}).setdefault("sections", []).append({"id": "prompts", "title": "Mine"}),
    lambda s: s["prompts"]["tiers"][0]["rows"].append({"id": "T1", "prompt": "Clashes with rec T1"}),       # prompt id = rec id
    lambda s: s["prompts"]["tiers"][0]["rows"].append({"id": "T1.1", "prompt": "Same prompt id twice"}),
], ids=["section twice", "generated section id", "generated strategy id", "prompt reuses rec id", "prompt twice"])
def test_lint_catches_every_id_the_page_would_repeat(change):
    """Each case really does put two elements with one id on the page, and the lint says so first."""
    src = _source()
    change(src)
    assert _duplicate_ids(src) != []
    assert "duplicate-id" in _errors(src)


def test_section_without_id_or_title_is_an_error_not_a_crash():
    src = _source()
    src["docs"]["audit"]["sections"].append({"title": "No id"})
    with pytest.raises(KeyError):
        render_report.render(copy.deepcopy(src))
    assert "section-shape" in _errors(src)
    src = _source()
    src["docs"]["audit"]["sections"].append({"id": "has space", "title": "Bad id"})
    assert "section-id" in _errors(src)


def test_summary_and_part_leads_stay_short():
    src = _source()
    assert not _warnings(src) & {"summary-length", "lead-length"}
    src["docs"]["brief"]["blocks"] = [{"type": "p", "text": "word " * 695}]
    assert "summary-length" in _warnings(src)                                  # 695 + the 8-word verdict
    src = _source()
    src["docs"]["plan"]["verdict"] = "word " * 61
    assert "lead-length" in _warnings(src)
    src = _source()
    del src["docs"]["brief"]
    src["docs"]["audit"]["verdict"] = "word " * 200                            # the audit verdict is the Summary now
    assert "lead-length" not in _warnings(src) and "summary-length" not in _warnings(src)


def test_text_the_page_no_longer_renders_is_flagged():
    src = _source()
    src["docs"]["plan"]["title"] = "Implementation Plan"
    src["docs"]["index"] = {"how": ["Findings live only in the Audit."]}
    flagged = {w["where"] for w in report_data_lint.lint(src)["warnings"] if w["rule"] == "not-rendered"}
    assert flagged == {"docs.plan.title", "docs.index.how"}
    assert "Implementation Plan" not in render_report.render(src)


# --- render ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def html():
    return render_report.render(_source())


def part(html, pid):
    """The markup of one part: from its opening div to the next part or the footer."""
    start = html.index(f'<div class="part" id="{pid}">')
    ends = [i for i in (html.find('<div class="part" id=', start + 1), html.find("<footer>", start)) if i != -1]
    return html[start:min(ends)]


def section(html, sid):
    return html.split(f'<section id="{sid}"')[1].split("</section>")[0]


def test_one_self_contained_file(html):
    assert set(render_report.render_all(_source())) == {"report.html"}
    assert html.startswith("<!doctype html>")
    assert "--paper:" in html and "@media print" in html                     # CSS inlined, print styles present
    assert "<script src=" not in html                                         # no CDN scripts
    assert "prefers-color-scheme:dark" in html


def test_parts_run_summary_audit_strategy_plan_appendix(html):
    nav = re.search(r'<nav class="toc".*?</nav>', html, re.S).group(0)
    assert re.findall(r'href="#(\w+)"', nav) == ["summary", "audit", "strategy", "plan", "appendix"]
    positions = [html.index(f'<div class="part" id="{p}">') for p in ("summary", "audit", "strategy", "plan", "appendix")]
    assert positions == sorted(positions)
    assert '<span class="sec-n">2.1</span><h2>Scope and coverage</h2>' in html   # sections number within their part
    toc = re.search(r'<ol class="part-toc">.*?</ol>', part(html, "plan"), re.S).group(0)
    assert 'href="#plan-register"' in toc


def test_each_thing_renders_once(html):
    """The duplication the six-file set had: one verdict, one coverage block, one decisions
    table, one list of this week's actions, one register."""
    assert html.count("Brand demand is the risk") == 1                        # brief verdict, in the Summary only
    assert html.count("Scope and coverage</h2>") == 1
    assert html.count("Inventory complete: absence claims") == 1
    assert html.count("Decisions needed</h2>") == 1 and html.count('id="D1"') == 1
    assert "What happens next" not in html and "Start today — what an agent" not in html and "By owner" not in html
    assert html.count("The full register</h2>") == 1


def test_summary_falls_back_to_the_audit_verdict_without_repeating_it():
    src = _source()
    del src["docs"]["brief"]
    out = render_report.render(src)
    assert out.count("Verdict with <code>code</code>") == 1
    assert "Verdict with" in part(out, "summary") and "Verdict with" not in part(out, "audit")


def test_prompt_ids_and_paths_are_not_linked_as_recommendations():
    ctx = render_report.Ctx(_source())
    out = ctx.inline("prompt T1.3 owns /vs/ but T1 fixes it; `T1` in code stays")
    assert '<a href="#T1">T1</a> fixes' in out
    assert "T1.3" in out and '<a href="#T1">T1</a>.3' not in out
    assert "<code>T1</code>" in out


def test_ids_link_within_the_page(html):
    audit, plan = part(html, "audit"), part(html, "plan")
    assert 'href="#T1"' in audit                                              # finding -> rec
    assert 'href="#F1"' in plan                                               # rec -> finding
    assert 'href="#D1"' in audit                                              # decision link
    assert 'id="T1"' in section(html, "plan-register") and html.count('id="T1"') == 1
    assert ".html#" not in html                                               # nothing points at another file
    assert "<code>code</code>" in audit and "<strong>bold</strong>" in audit


def test_findings_strengths_and_opportunities_render_in_their_own_blocks(html):
    findings = section(html, "audit-findings")
    assert 'id="F1"' in findings and 'id="F2"' not in findings and 'id="F3"' not in findings
    assert 'id="F2"' in section(html, "audit-strengths")
    opps = section(html, "audit-opportunities")
    assert 'id="F3"' in opps and "shown, not weighted" in opps


def test_coverage_states_completeness_and_checks(html):
    cov = section(html, "audit-coverage")
    assert "Inventory complete: absence claims" in cov
    assert "3,013" in cov and "crawl incomplete" in cov
    assert "Not examined" in cov and "Backlinks" in cov
    assert "Assumptions you can reject" in cov
    src = _source()
    src["coverage"]["graph"]["sitemap"]["complete"] = False
    src["findings"] = [f for f in src["findings"] if f["kind"] != "opportunity"]
    assert "Inventory incomplete: absence claims about site structure are withheld" in render_report.render(src)


def test_site_shape_tree_is_static_and_mermaid_goes_to_appendix(html):
    audit = part(html, "audit")
    assert 'class="tree"' in audit and "/blog/x" in audit
    assert "graph TD" not in audit
    assert "graph TD" in part(html, "appendix")


def test_register_carries_tier_lane_supersedes_and_dropped_rows(html):
    plan = part(html, "plan")
    assert "lane-Auto" in plan and "lane-Human" in plan and "lane-Decision" in plan
    assert "Overrides page_types finding missing_page_type" in plan
    assert 'class="dropped"' in section(html, "plan-register")               # C2 struck through in the full register
    assert "C2" not in section(html, "plan-timeline")                         # dropped items leave the timeline


def test_start_today_lists_only_unblocked_agent_work():
    src = _source()
    ids = [r["id"] for r in render_report.start_today(src)]
    assert ids == ["M1"]                       # Auto, unblocked. C1 is blocked by T1 (Human); T1 is Human; C2 dropped.
    src["recommendations"][0]["status"] = "shipped"
    assert [r["id"] for r in render_report.start_today(src)] == ["C1", "M1"]


def test_start_today_is_marked_in_the_timeline(html):
    timeline = section(html, "plan-timeline")
    marked = re.findall(r'<tr><td class="q"><a href="#(\w+)"[^<]*</a></td><td><span class="chip g">Start today</span>', timeline)
    assert marked == ["M1"]
    assert "Start today" not in section(html, "plan-register")


def test_summary_has_decisions_this_week_and_what_is_not_known(html):
    summary = part(html, "summary")
    assert "Publish pricing?" in summary and 'id="D1"' in summary
    assert 'href="#T1"' in summary and "M1" in summary
    assert 'id="T1"' not in summary                                           # the register owns the anchor
    assert "What is not known yet" in summary and 'href="#audit-coverage"' in summary


def test_page_cards_and_appendix_fold(html):
    assert '<details class="fold wave">' in section(html, "strategy-pages")
    appendix = part(html, "appendix")
    assert appendix.count('<section id="appendix-') == appendix.count('<details class="fold"><summary class="sec-head">')
    assert "Confirmed as written" in appendix and "Dropped" in appendix
    assert "Machine checks" not in appendix                                   # no summary folded in
    assert "Generative engine optimization" in appendix


def test_link_handler_unfolds_and_printing_opens_every_fold():
    js = render_report.NAV_JS
    handler = js[js.index("In-page links scroll by script"):]
    assert "p.open=true" in handler.split("scrollIntoView")[0]
    assert "beforeprint" in js and "afterprint" in js
    css = open(os.path.join(ROOT, "references", "report-template", "print.css"), encoding="utf-8").read()
    assert ".part{break-before:page" in css


def test_parts_without_content_are_left_out():
    src = _source()
    for key in ("prompts", "pages", "validity", "tests", "glossary"):
        src.pop(key, None)
    src["docs"]["strategy"] = {}
    src["recommendations"] = [dict(r, validity=None) for r in src["recommendations"] if r["status"] != "dropped"]
    src["structure"]["architecture"].pop("mermaid", None)
    out = render_report.render(src)
    assert 'id="strategy"' not in out and 'id="appendix"' not in out
    assert 'href="#strategy"' not in out and 'href="#appendix"' not in out


def test_summary_and_graph_merge_into_coverage_and_appendix():
    src = _source()
    summary = {"schema_version": 2, "url": "https://example.com", "timestamp": "2026-09-17", "overall": 71, "measured_categories": 9,
               "categories": {"robots": {"label": "Robots", "group": "technical", "score": 90, "weight": 5, "status": "Strong"},
                              "page_types": {"label": "Page-type coverage", "group": "content", "score": None, "weight": None, "status": "Reviewed"},
                              "pagespeed": {"label": "Core Web Vitals", "group": "performance", "score": None, "weight": 8, "status": "Not measured"}},
               "findings": [{"id": "x", "severity": "medium", "section": "page_types", "finding": "No alternatives pages", "evidence": "0 URLs", "fix": "Create", "confidence": "Likely"}]}
    render_report.merge_summary(src, summary)
    graph = {"site": "https://example.com", "generated_at": "2026-09-17T10:00:00Z", "sitemap": {"found": True, "complete": True, "urls": {"a": {}}},
             "crawl": {"complete": True, "reasons": []}, "summary": {"sitemap_urls": 1, "pages_fetched": 1, "max_depth_seen": 1}}
    render_report.merge_graph(src, graph)
    assert "urls" not in src["coverage"]["graph"]["sitemap"]
    assert src["health_score"]["overall"] == 71 and src["health_score"]["source"].startswith("generate_report.py")
    assert report_data_lint.lint(src)["errors"] == []
    out = render_report.render(src)
    audit, appendix = part(out, "audit"), part(out, "appendix")
    assert "Health Score 71/100" in audit
    row = re.search(r"<tr>.*?Page-type coverage.*?</tr>", audit, re.S).group(0)
    assert "shown, not weighted" in row and "<td class=\"n\">—</td>" in row      # display-only: no score, no weight
    assert "Machine checks" in appendix and "No alternatives pages" in appendix


def test_render_cli_refuses_a_bad_source_unless_forced(tmp_path):
    bad = _source()
    bad["findings"][0]["fixes"] = ["T99"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    script = os.path.join(ROOT, "scripts", "render_report.py")
    run = subprocess.run([sys.executable, script, str(path), "--out", str(tmp_path / "out")], capture_output=True, text=True)
    assert run.returncode == 1 and "orphan-id" in run.stdout
    assert not (tmp_path / "out").exists()
    run = subprocess.run([sys.executable, script, str(path), "--out", str(tmp_path / "out"), "--force", "--json"], capture_output=True, text=True)
    assert run.returncode == 0
    assert [os.path.basename(p) for p in json.loads(run.stdout)["written"]] == ["report.html"]


def test_sample_source_is_clean_and_catalogue_shows_every_component():
    sample = render_report.sample_source()
    assert report_data_lint.lint(sample)["errors"] == []
    out = render_report.catalogue_html(render_report.load_css())
    for marker in ('class="verdict"', 'class="figs"', 'class="cov"', 'class="tree"', 'class="find c"', 'class="find keep"', 'class="find opp"',
                   "lane-Decision", 'class="dropped"', 'class="ptier"', 'class="pg con"', 'class="gloss"', "Overrides navigation finding", "Toggle light / dark"):
        assert marker in out, marker
    assert "<script src=" not in out


def test_catalogue_on_disk_matches_the_renderer():
    path = os.path.join(ROOT, "references", "report-template", "components.html")
    assert os.path.exists(path), "run: python scripts/render_report.py --catalogue references/report-template/components.html"
    on_disk = open(path, encoding="utf-8").read()
    fresh = render_report.catalogue_html(render_report.load_css())
    strip = lambda s: re.sub(r"Generated \d{4}-\d{2}-\d{2}", "Generated DATE", s)
    assert strip(on_disk) == strip(fresh), "components.html is stale: regenerate it with --catalogue"


def test_template_package_is_bundled():
    plugin = os.path.join(ROOT, "plugins", "ultimate-seo-geo", "skills", "ultimate-seo-geo", "references", "report-template")
    root = os.path.join(ROOT, "references", "report-template")
    for name in ("report-template.md", "report.css", "print.css"):
        assert os.path.exists(os.path.join(root, name)), name
        assert os.path.exists(os.path.join(plugin, name)), f"{name} missing from the plugin bundle: run setup-plugin.sh"


def test_html_escapes_source_text():
    src = _source()
    src["findings"][0]["title"] = "<img src=x onerror=alert(1)>"
    out = render_report.render(src)
    assert "<img src=x" not in out and "&lt;img src=x" in out
    src2 = copy.deepcopy(_source())
    src2["docs"]["audit"]["sections"][0]["blocks"][0]["rows"] = [["<script>x</script>"]]
    assert "<script>x</script>" not in render_report.render(src2)


# --- anchors ------------------------------------------------------------------------

def _ids(markup):
    markup = re.sub(r"<script\b.*?</script>", "", markup, flags=re.S)
    return re.findall(r'\bid="([^"]+)"', markup), markup


@pytest.mark.parametrize("make", [lambda: render_report.render(_source()), lambda: render_report.render(render_report.sample_source()),
                                  lambda: render_report.catalogue_html(render_report.load_css())],
                         ids=["test source", "sample source", "catalogue"])
def test_every_id_is_unique_and_every_link_lands(make):
    """A repeated id sends a link to the first copy; a missing one goes nowhere."""
    found, markup = _ids(make())
    assert sorted({i for i in found if found.count(i) > 1}) == []
    assert sorted({h for h in re.findall(r'href="#([^"]*)"', markup) if h not in set(found)}) == []


def test_in_page_links_scroll_by_script_and_the_footer_says_what_to_do(html):
    script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    assert "scrollIntoView" in script and "preventDefault" in script
    assert "open the file in a web browser" in re.search(r"<footer>.*?</footer>", html, re.S).group(0)
