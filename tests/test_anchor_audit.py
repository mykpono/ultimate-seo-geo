"""internal_links.anchor_audit: anchor text per destination, from in-content links only.

Calibrated on four real graphs (smashingmagazine.com, posthog.com,
developers.cloudflare.com, balloonbay.us, 40 pages each). Two first-draft
defects became the regression tests below: "Go" naming the Go language was
called vague, and a "one anchor dominates" finding fired only on template calls
to action, so it was dropped as a finding.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report as gr  # noqa: E402
import internal_links as il  # noqa: E402

SITE = "https://ex.com"


def link(path, anchor, region="main", container="main", internal=True):
    href = f"{SITE}{path}"
    return {"href": href, "key": href.rstrip("/") if path != "/" else href, "anchor": anchor, "rel": [],
            "region": region, "container": container, "internal": internal}


def page(path, links, depth=1):
    url = f"{SITE}{path}"
    return {"url": url, "key": url.rstrip("/") if path != "/" else url, "depth": depth, "out_links": links}


def graph(pages):
    return {"pages": {p["key"]: p for p in pages}}


def blog_site(n=6, extra=None):
    """n pages; each carries the site chrome, a div footer link and one card list."""
    pages = []
    for i in range(n):
        links = [
            link("/pricing", "Pricing", region="nav", container="header"),       # chrome
            link("/about", "Read more", region="footer", container="footer"),    # chrome, vague: not counted
            link("/privacy", "Privacy", region="other", container="other"),      # div footer on every page
            link(f"/post-{i + 1}", "Read more »"),                                # card: vague
            link(f"/post-{i + 1}", "Read more »"),                                # same link twice on one page
            link(f"/post-{i + 1}", "How we cut our bill in half"),                # the card title: descriptive
        ]
        links += (extra or {}).get(i, [])
        pages.append(page(f"/blog/{i}", links))
    return graph(pages)


def test_chrome_and_repeating_links_are_left_out():
    audit = il.anchor_audit(blog_site())
    assert audit["status"] == "measured"
    assert audit["excluded"]["chrome"] == 12       # two chrome links on six pages
    assert audit["excluded"]["boilerplate"] == 6   # the div footer link on every page
    assert all(v["target"].split("/")[-1].startswith("post-") for v in audit["vague_links"])


def test_each_page_counts_once_per_destination_and_anchor():
    audit = il.anchor_audit(blog_site())
    assert audit["vague_links_count"] == 6         # not 12: the repeated card link counts once
    assert audit["content_links"] == 12            # six "read more" + six titles


def test_punctuation_and_arrows_do_not_hide_a_vague_anchor():
    assert il.normalise_anchor("Read more »") == "read more"
    assert il.normalise_anchor("Continue reading ↬") == "continue reading"   # smashingmagazine.com
    assert il.is_vague("continue reading", f"{SITE}/2026/09/some-article/")


def test_go_naming_the_go_language_is_not_vague():
    """developers.cloudflare.com and posthog.com link "Go" to /api/go/ and /installation/go."""
    assert not il.is_vague("go", "https://developers.cloudflare.com/api/go/")
    assert not il.is_vague("go", "https://posthog.com/docs/error-tracking/installation/go")
    assert il.is_vague("go", f"{SITE}/pricing")
    assert il.is_vague("read more", f"{SITE}/read-more-about-us") is False  # the words are the target's own


def test_a_page_reached_only_through_vague_content_links():
    """posthog.com /careers/ai-research-engineer: header links excluded, the one content link is "Read more"."""
    extra = {0: [link("/careers/engineer", "Read more"), link("/careers/engineer", "Learn more", region="header", container="header")]}
    audit = il.anchor_audit(blog_site(extra=extra))
    assert [d["url"] for d in audit["only_vague"]] == [f"{SITE}/careers/engineer"]
    issue = il.anchor_issues(audit)[0]
    assert "1 page(s) are reached only through such anchors in content" in issue["finding"]
    assert issue["urls"] == [f"{SITE}/careers/engineer"]


def test_a_repeated_anchor_is_reported_as_data_never_as_a_finding():
    """Template calls to action dominated this list on every real site tried."""
    extra = {i: [link("/build-quote", "Build your quote")] for i in range(6)}
    extra[0].append(link("/faq", "See all FAQs"))
    audit = il.anchor_audit(blog_site(extra=extra))
    assert "dominant" not in audit
    assert all(i["code"] != "internal_links.dominant_anchor" for i in il.anchor_issues(audit))
    dest = next(d for d in audit["destinations"] if d["url"].endswith("/faq"))
    assert dest["top_anchor"] == "see all faqs" and dest["top_anchor_share"] == 1.0


def test_too_few_pages_is_not_measured_and_raises_nothing():
    audit = il.anchor_audit(blog_site(n=3))
    assert audit["status"] == "not measured" and "3 fetched page" in audit["reason"]
    assert il.anchor_issues(audit) == []


def test_empty_anchors_are_counted_not_judged():
    extra = {0: [link("/gallery", "")]}
    audit = il.anchor_audit(blog_site(extra=extra))
    assert audit["excluded"]["empty_anchor"] == 1
    assert all(v["target"] != f"{SITE}/gallery" for v in audit["vague_links"])


def test_the_finding_follows_the_contract_and_is_low():
    issues = il.anchor_issues(il.anchor_audit(blog_site()))
    assert len(issues) == 1
    issue = issues[0]
    assert issue["severity"] == "low" and issue["code"] == "internal_links.vague_anchors" and issue["lane"] == "Auto"
    for field in ("finding", "evidence", "impact", "fix", "confidence", "falsifiability", "leading_indicator"):
        assert issue[field], field


def test_the_internal_links_score_does_not_move():
    base = {"issues": ["⚠️ 3 page(s) have fewer than 3 internal links"]}
    with_audit = {"issues": base["issues"] + il.anchor_issues(il.anchor_audit(blog_site()))}
    assert gr._internal_links_score(with_audit) == gr._internal_links_score(base)


def test_generate_report_passes_the_shared_graph(monkeypatch):
    calls = {}

    def fake_run(script, args, timeout=120):
        calls[script] = args
        return {}

    monkeypatch.setattr(gr, "run_script", fake_run)
    monkeypatch.setattr(gr, "fetch_page", lambda url, render="never": ("", ""))
    monkeypatch.setattr(gr, "build_site_graph", lambda url: "/tmp/graph.json")
    monkeypatch.setattr(gr.os.path, "exists", lambda p: False)
    gr.collect_data("https://ex.com/")
    assert calls["internal_links.py"][-2:] == ["--graph", "/tmp/graph.json"]
    monkeypatch.setattr(gr, "build_site_graph", lambda url: None)
    gr.collect_data("https://ex.com/")
    assert "--graph" not in calls["internal_links.py"]


def test_report_panel_shows_the_audit():
    audit = il.anchor_audit(blog_site())
    html = gr._anchor_audit_panel(audit)
    assert "Anchor audit (in-content links)" in html and "read more" in html.lower()
    assert "2 fetched page(s)" in gr._anchor_audit_panel({"status": "not measured", "reason": "2 fetched page(s)"})
    assert gr._anchor_audit_panel(None) == ""


def test_cli_rejects_a_file_that_is_not_a_graph(tmp_path):
    bad = tmp_path / "g.json"
    bad.write_text(json.dumps({"pages": {}}))
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "internal_links.py"), "https://ex.com", "--graph", str(bad)],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2 and "--graph" in proc.stderr
