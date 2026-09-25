"""link_opportunities.py: pages that name a target's topic but do not link to it.

Calibrated on 40-page graphs of posthog.com, balloonbay.us,
developers.cloudflare.com and smashingmagazine.com. First-draft false positives,
each now a named test: the target listed as its own opportunity (a www copy in
the graph), "Workers" matching "Workers AI" / "Workers KV", and page furniture
(breadcrumbs, "Copy as Markdown | ..." bars, a quote builder's carousel, a
Title Case heading) read as sentences.
"""

import csv
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "scripts", "link_opportunities.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import link_opportunities as lo  # noqa: E402

SITE = "https://ex.com"
TARGET = f"{SITE}/pricing"


def link(path, region="main", container="main", anchor="x"):
    href = f"{SITE}{path}"
    return {"href": href, "key": href.rstrip("/"), "anchor": anchor, "region": region, "container": container, "internal": True}


def page(path, links=(), title="", h1="", depth=1, canonical=None):
    url = f"{SITE}{path}"
    return {"url": url, "key": url.rstrip("/"), "title": title, "h1": h1, "depth": depth,
            "canonical": canonical, "out_links": list(links)}


def graph(*pages):
    return {"pages": {p["key"]: p for p in pages}}


def html(body):
    return f"<html><body><header><a href='/pricing'>Pricing</a></header><main>{body}</main><footer>Pricing and plans</footer></body></html>"


def fetcher(bodies):
    def fetch(url):
        if url in bodies:
            return {"html": html(bodies[url]), "error": None}
        return {"html": "", "error": "HTTP 404"}
    return fetch


PROSE = "<p>Our team compares every plan on the pricing page before a customer signs up for anything.</p>"


def run(g, bodies, terms=("pricing",), **kw):
    return lo.find_opportunities(g, TARGET, list(terms), fetch=fetcher(bodies), **kw)


# --- which pages are read ---------------------------------------------------------------

def test_a_page_linking_from_content_is_done_and_a_nav_only_link_is_still_a_candidate():
    g = graph(page("/pricing"),
              page("/a", [link("/pricing")]),                                      # content link: done
              page("/b", [link("/pricing", region="nav", container="header")]),   # nav only: still a candidate
              page("/c"))
    result = run(g, {f"{SITE}/b": PROSE, f"{SITE}/c": PROSE})
    assert result["already_linking_from_content"] == 1
    by = {o["source"]: o for o in result["opportunities"]}
    assert set(by) == {f"{SITE}/b", f"{SITE}/c"}
    assert by[f"{SITE}/b"]["nav_only_link"] is True and by[f"{SITE}/c"]["nav_only_link"] is False


def test_the_target_under_another_host_spelling_or_canonical_is_not_its_own_opportunity():
    """smashingmagazine.com's graph held both www and apex copies of the target."""
    www = page("/pricing")
    www.update(url="https://www.ex.com/pricing/", key="https://www.ex.com/pricing")
    g = graph(www, page("/pricing-old", canonical=TARGET), page("/c"))
    result = run(g, {"https://www.ex.com/pricing/": PROSE, f"{SITE}/pricing-old": PROSE, f"{SITE}/c": PROSE})
    assert [o["source"] for o in result["opportunities"]] == [f"{SITE}/c"]


def test_max_fetch_reads_heading_matches_first_and_reports_the_rest():
    g = graph(page("/z-deep", depth=3), page("/y"), page("/guide", title="A guide to pricing"))
    result = run(g, {f"{SITE}/guide": PROSE, f"{SITE}/y": PROSE, f"{SITE}/z-deep": PROSE}, max_fetch=1)
    assert result["pages_read"] == 1 and result["pages_not_read"] == 2
    assert [o["source"] for o in result["opportunities"]] == [f"{SITE}/guide"]
    assert any("2 candidate page(s) were not read" in line for line in result["limits"])


def test_a_page_that_fails_to_load_is_reported_not_fatal():
    result = run(graph(page("/gone"), page("/ok")), {f"{SITE}/ok": PROSE})
    assert result["fetch_errors"] == [{"url": f"{SITE}/gone", "error": "HTTP 404"}]
    assert result["count"] == 1


# --- what counts as a mention --------------------------------------------------------------

def test_a_term_that_is_already_link_text_does_not_count():
    body = "<p>Before you buy, read our <a href='/blog/x'>pricing guide</a> and the comparison table below.</p>"
    assert run(graph(page("/c")), {f"{SITE}/c": body})["count"] == 0


def test_header_and_footer_mentions_do_not_count():
    assert run(graph(page("/c")), {f"{SITE}/c": "<p>Nothing about money is said in this content at all.</p>"})["count"] == 0


@pytest.mark.parametrize("furniture", [
    "<p>Docs / Workers / Pricing Last updated Jul 31, 2026 | Copy as Markdown | Edit</p>",         # cloudflare
    "<p>Colors ⇄ Primary ⇄ Secondary pricing per piece ‹ 1 / 5 ›</p>",                           # balloonbay quote builder
    "<p>Pricing <a href='/x'>x</a> Email Pricing For The Next Ones Of Our Team.</p>",             # smashing heading
    "<p>See pricing.</p>",                                                                        # too short to hold a link
    "<p><a href='/a'>a</a> <a href='/b'>b</a> <a href='/c'>c</a> pricing is listed for all of our plans today.</p>",
])
def test_page_furniture_is_not_a_sentence_to_link_from(furniture):
    assert run(graph(page("/c")), {f"{SITE}/c": furniture})["count"] == 0


def test_a_term_inside_a_longer_product_name_is_not_the_term():
    """developers.cloudflare.com: "Workers AI" and "Workers KV" are other products than /workers."""
    body = "<p>You can call Workers AI models and store data in Workers KV from any application you build.</p>"
    assert run(graph(page("/c")), {f"{SITE}/c": body}, terms=("Workers",))["count"] == 0
    body = "<p>Deploy the function to Workers and it runs close to every user of your application.</p>"
    assert run(graph(page("/c")), {f"{SITE}/c": body}, terms=("Workers",))["count"] == 1


# --- anchors and ordering ------------------------------------------------------------------

def test_a_search_console_query_in_the_sentence_is_the_anchor():
    body = "<p>Most teams check our plans and pricing for startups before they talk to sales about it.</p>"
    result = run(graph(page("/c")), {f"{SITE}/c": body}, queries=["plans and pricing for startups", "ex pricing"])
    o = result["opportunities"][0]
    assert (o["anchor"], o["anchor_from"]) == ("plans and pricing for startups", "search console query")


def test_without_a_matching_query_the_term_is_the_anchor_as_written():
    o = run(graph(page("/c")), {f"{SITE}/c": PROSE.replace("pricing page", "Pricing page")})["opportunities"][0]
    assert (o["anchor"], o["anchor_from"]) == ("Pricing", "term")


def test_clicks_order_the_opportunities():
    g = graph(page("/a"), page("/b"))
    result = run(g, {f"{SITE}/a": PROSE, f"{SITE}/b": PROSE}, clicks={lo._key(f"{SITE}/b"): 900, lo._key(f"{SITE}/a"): 10})
    assert [o["source"] for o in result["opportunities"]] == [f"{SITE}/b", f"{SITE}/a"]
    assert result["ordered_by"].startswith("source page clicks")


def test_the_finding_is_an_auto_opportunity_that_names_its_pages():
    issues = run(graph(page("/c")), {f"{SITE}/c": PROSE})["issues"]
    assert len(issues) == 1
    issue = issues[0]
    assert (issue["kind"], issue["lane"], issue["severity"]) == ("opportunity", "Auto", "low")
    assert issue["urls"] == [f"{SITE}/c"]
    for field in ("finding", "evidence", "impact", "fix", "confidence", "falsifiability", "leading_indicator"):
        assert issue[field], field


def test_no_terms_is_an_error():
    with pytest.raises(ValueError, match="no terms"):
        lo.find_opportunities(graph(page("/c")), TARGET, [], fetch=fetcher({}))


# --- inputs ------------------------------------------------------------------------------------

def test_queries_come_from_the_targets_rows_in_a_save_rows_file(tmp_path):
    rows = {"query_page": {"rows": [
        {"query": "ex pricing", "page": "https://www.ex.com/pricing/", "impressions": 50},
        {"query": "ex plans", "page": "https://ex.com/pricing#faq", "impressions": 900},
        {"query": "ex blog", "page": "https://ex.com/blog", "impressions": 5000},
        {"query": "EX PRICING", "page": "https://ex.com/pricing", "impressions": 10},
    ]}}
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(rows))
    assert lo.load_queries(str(path), TARGET) == ["ex plans", "ex pricing"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"pages": []}))
    with pytest.raises(ValueError, match="save-rows"):
        lo.load_queries(str(bad), TARGET)


def test_clicks_load_from_the_pages_export(tmp_path):
    path = tmp_path / "Pages.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([["Top pages", "Clicks", "Impressions"], ["https://www.ex.com/a/", "120", "3000"]])
    assert lo.load_clicks(str(path)) == {"ex.com/a": 120}


def test_cli_rejects_a_relative_target_and_missing_terms(tmp_path):
    g = tmp_path / "g.json"
    g.write_text("{}")
    rel = subprocess.run([sys.executable, SCRIPT, "--graph", str(g), "--target", "/pricing", "--terms", "x"],
                         capture_output=True, text=True, timeout=60)
    assert rel.returncode == 2 and "absolute URL" in rel.stderr
    bad = subprocess.run([sys.executable, SCRIPT, "--graph", str(g), "--target", TARGET, "--terms", "x"],
                         capture_output=True, text=True, timeout=60)
    assert bad.returncode == 2 and "--graph" in bad.stderr
