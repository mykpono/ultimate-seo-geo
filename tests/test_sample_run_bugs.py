"""Defects a live report run exposed (balloonbay.us, 2026-09-18) that fixtures had not.

* Cloudflare Email Obfuscation turns every mailto: into /cdn-cgi/l/email-protection,
  which answers 404 to a crawler by design: a false High and a false Critical.
* The broken-links Critical named no link and no fix.
* validate_schema's [info] notes ("keep this markup") were reported as warnings with
  "Fix JSON-LD" and took 8 points off the schema score each.
* readability counted a whole page as one paragraph.
* A retired robots.txt token named its replacement in prose but carried no fix.
* The appendix printed stock "Rerun the section check" text under every issue.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import broken_links  # noqa: E402
import generate_report as gr  # noqa: E402
import readability  # noqa: E402
import url_safety  # noqa: E402


# --- Cloudflare obfuscated mailto links ---------------------------------------------------

@pytest.mark.parametrize("href", [
    "/cdn-cgi/l/email-protection#f59a87919087b5979499",
    "https://ex.com/cdn-cgi/l/email-protection",
    "#top", "mailto:a@ex.com", "tel:+1", "javascript:void(0)", "data:text/plain,x", "sms:+1", "", "  ",
])
def test_non_page_hrefs_are_not_crawlable(href):
    assert not url_safety.is_crawlable_href(href)


@pytest.mark.parametrize("href", ["/pricing/", "https://ex.com/a?b=1", "contact.html", "/blog/email-protection-tips/"])
def test_real_links_stay_crawlable(href):
    assert url_safety.is_crawlable_href(href)


CRAWLERS = ["site_graph", "link_profile", "internal_links", "site_mapper", "broken_links", "content_brief", "canonical_checker"]


@pytest.mark.parametrize("script", CRAWLERS)
def test_every_link_crawler_uses_the_shared_filter(script):
    with open(os.path.join(SCRIPTS, f"{script}.py"), encoding="utf-8") as fh:
        source = fh.read()
    assert "is_crawlable_href(href)" in source
    # content_brief keeps one private copy, as its fallback when url_safety cannot be imported.
    assert source.count('startswith(("#", "javascript:"') == (1 if script == "content_brief" else 0)


def test_broken_links_extraction_drops_the_obfuscated_mailto():
    html = ('<a href="/cdn-cgi/l/email-protection#abc">[email&#160;protected]</a>'
            '<a href="/pricing/">Pricing</a>')
    links = broken_links.extract_links(html, "https://ex.com/")
    assert [l["url"] for l in links] == ["https://ex.com/pricing/"]


# --- the broken-links finding names its evidence ----------------------------------------------

def test_broken_links_finding_carries_evidence_and_a_fix():
    broken = [{"url": f"https://ex.com/gone-{n}", "status": 404, "anchor_text": "Old page"} for n in range(7)]
    issue = broken_links._broken_issue(broken, "7 broken link(s) found")
    assert issue["severity"] == "critical" and issue["fix"]
    # Its own lane: the fix is a link edit, and no wording in it may read as a high-risk change.
    collected = gr._collect_issues({"sections": {"broken_links": {"issues": [issue]}}})
    assert collected[0]["lane"] == "Auto" and not gr._HIGH_RISK_RE.search(issue["fix"])
    assert "https://ex.com/gone-0" in issue["evidence"] and "HTTP 404" in issue["evidence"] and "Old page" in issue["evidence"]
    assert "and 2 more" in issue["evidence"]
    assert broken_links._issue_text(issue).startswith("🔴 7 broken")
    assert broken_links._issue_text("⚠️ plain") == "⚠️ plain"


def test_a_link_with_no_status_still_gets_evidence():
    issue = broken_links._broken_issue([{"url": "https://ex.com/x", "status": None, "error": "ConnectionError"}], "1 broken link(s) found")
    assert "ConnectionError" in issue["evidence"]


# --- a host that refuses the crawler is not a broken link ---------------------------------------

@pytest.mark.parametrize("status", sorted(broken_links.REFUSAL_STATUSES))
def test_an_external_refusal_is_unverified_not_broken(status):
    assert broken_links.is_refused({"url": "https://www.yelp.com/biz/x", "is_internal": False, "status": status})


@pytest.mark.parametrize("link", [
    {"url": "https://ex.com/private", "is_internal": True, "status": 403},   # our own 403 is a real problem
    {"url": "https://other.com/gone", "is_internal": False, "status": 404},
    {"url": "https://other.com/down", "is_internal": False, "status": 500},
    {"url": "https://other.com/ok", "is_internal": False, "status": 200},
])
def test_everything_else_is_judged_as_before(link):
    assert not broken_links.is_refused(link)


def test_refused_links_become_an_open_question_and_cost_no_score(monkeypatch):
    html = '<a href="https://www.yelp.com/biz/x">Yelp</a><a href="/gone/">Gone</a><a href="/ok/">OK</a>'
    statuses = {"https://www.yelp.com/biz/x": 403, "https://ex.com/gone/": 404, "https://ex.com/ok/": 200}

    def fake_check(link, timeout=10, **_kwargs):
        return {**link, "status": statuses[link["url"]], "error": None, "redirect": None,
                "response_time_ms": 1, "soft_404": False}

    class Page:
        status_code, text, url = 200, html, "https://ex.com/"

    monkeypatch.setattr(broken_links, "check_link", fake_check)
    monkeypatch.setattr(broken_links.requests, "get", lambda *a, **k: Page())
    result = broken_links.check_broken_links("https://ex.com/")
    assert [l["url"] for l in result["broken"]] == ["https://ex.com/gone/"]
    assert [l["url"] for l in result["refused"]] == ["https://www.yelp.com/biz/x"]
    assert result["summary"]["broken"] == 1 and result["summary"]["refused"] == 1
    gap = next(i for i in result["issues"] if isinstance(i, dict) and i.get("kind") == "data_gap")
    assert "yelp.com" in gap["evidence"] and "403" in gap["evidence"]
    collected = gr._collect_issues({"sections": {"broken_links": result}})
    kinds = {i["finding"]: i["kind"] for i in collected}
    assert kinds[gap["finding"]] == "data_gap" and kinds["1 broken link(s) found"] == "defect"


# --- validate_schema: an [info] note is not a defect ------------------------------------------------

def _validate(tmp_path, markup):
    page = tmp_path / "page.html"
    page.write_text(f'<html><body><h2>Q?</h2><p>A.</p><script type="application/ld+json">{markup}</script></body></html>',
                    encoding="utf-8")
    out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_schema.py"), str(page), "--json"],
                         capture_output=True, text=True)
    return json.loads(out.stdout)


FAQ = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
    {"@type": "Question", "name": "Q?", "acceptedAnswer": {"@type": "Answer", "text": "A."}}]})


def test_a_keep_this_markup_note_is_info_with_no_fix_and_costs_nothing(tmp_path):
    result = _validate(tmp_path, FAQ)
    notes = [i for i in result["issues"] if "FAQ" in i["finding"]]
    assert notes, result
    for note in notes:
        assert note["severity"] == "info" and note["fix"] == "" and not note["finding"].startswith("[info]")
    if all(i["severity"] == "info" for i in result["issues"]):
        assert result["score"] == 100


def test_a_real_schema_error_still_scores_and_names_the_reference(tmp_path):
    result = _validate(tmp_path, json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": "[REPLACE ME]"}))
    assert any(i["severity"] == "critical" and "schema-types.md" in i["fix"] for i in result["issues"])
    assert result["score"] < 100


# --- readability: paragraphs are block elements ---------------------------------------------------------

@pytest.mark.skipif(not readability.HAS_BS4, reason="needs BeautifulSoup")
def test_paragraphs_are_counted_from_block_elements():
    html = "<main>" + "".join(f"<p>The first sentence of block {n} is here. The second sentence of block {n} follows it.</p>" for n in range(10)) + "</main>"
    text = readability.extract_text(html)
    assert text.count("\n\n") == 9
    result = readability.analyze_readability(text)
    assert result["paragraph_count"] == 10 and result["avg_paragraph_length"] == 2.0


@pytest.mark.skipif(not readability.HAS_BS4, reason="needs BeautifulSoup")
def test_inline_markup_does_not_split_a_sentence():
    text = readability.extract_text("<p>This is <strong>one</strong> <a href='/x'>sentence</a>.</p><p>Second.</p>")
    assert text == "This is one sentence.\n\nSecond."


# --- the appendix prints only what a script said --------------------------------------------------------------

def test_appendix_issue_carries_no_stock_metadata():
    html = gr.render_recommendations({"issues": [{"severity": "medium", "finding": "Title too long", "fix": "Shorten it."}]})
    assert "Title too long" in html and "Shorten it." in html
    assert "Rerun the" not in html and "Leading indicator" not in html


def test_appendix_issue_keeps_metadata_a_script_supplied():
    html = gr.render_recommendations({"issues": [{"severity": "medium", "finding": "x", "fix": "y",
                                                  "leading_indicator": "CTR in 4 weeks", "falsifiability": "No CTR change"}]})
    assert "CTR in 4 weeks" in html and "No CTR change" in html
