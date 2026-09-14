"""An orphan is a page nothing links to — and only a complete crawl can say so.

A live audit of a 3,008-URL site reported "14 orphan pages" at high severity and
"1,637 potential orphans" beside it. Both were artefacts of the crawl, not the site:

  * ``link_profile.py`` fetched the first 20 sitemap URLs and called any of them an
    orphan if none of the other 19 linked to it. Inbound links from the 2,988 pages
    it never fetched were invisible. It also exempted ``min(crawled)`` as the
    homepage (the alphabetically first URL, not the entry page), keyed sitemap URLs
    and link targets differently so ``/guide/`` never matched ``/guide``, and
    counted a page's link to itself as an inbound link.
  * ``internal_links.py`` discovers pages only by following links, so every page it
    knows about has an inbound link by construction. It labelled pages linked from
    ≤1 of its 16 crawled pages "potential orphans" — case studies linked from the
    homepage among them.

The rule now: an orphan claim needs a crawl that is provably complete — sitemap
not truncated, every fetch succeeded, and every page any crawled page links to was
itself crawled. Anything less is reported as inconclusive, never as a finding.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_report  # noqa: E402
import internal_links  # noqa: E402
import link_profile  # noqa: E402


SITE = "https://ex.com/"


def _html(*hrefs):
    return "<html><body>" + "".join(f'<a href="{h}">link</a>' for h in hrefs) + "</body></html>"


def _audit(monkeypatch, pages, sitemap, site=SITE, max_pages=50):
    """Run link_profile's crawl + analysis against an in-memory site."""
    monkeypatch.setattr(
        link_profile, "get_sitemap_urls", lambda site_url, limit=200: list(sitemap)[:limit]
    )
    monkeypatch.setattr(
        link_profile, "fetch_page", lambda url, timeout=10: (url, pages.get(url, ""))
    )
    monkeypatch.setattr(link_profile.time, "sleep", lambda seconds: None)
    graph, crawled, domain = link_profile.crawl_site(site, max_pages=max_pages)
    return link_profile.analyze_link_profile(graph, crawled, domain)


def _orphan_issues(report):
    return [i for i in report["issues"] if "orphan" in i["type"]]


# --- link_profile: partial crawls prove nothing ------------------------------

def test_truncated_sitemap_is_inconclusive_not_an_orphan_finding(monkeypatch):
    """The live false positive: a sitemap sample where the hub linking to a page was never fetched."""
    pages = {
        SITE: _html("/"),
        "https://ex.com/customer/acme": _html("/"),
    }
    # /customers links to /customer/acme, but max_pages stops the crawl before reaching it.
    sitemap = [SITE, "https://ex.com/customer/acme", "https://ex.com/customers"]
    report = _audit(monkeypatch, pages, sitemap, max_pages=2)

    assert report["orphan_pages"]["status"] == "inconclusive"
    assert report["orphan_pages"]["count"] == 0
    assert report["orphan_pages"]["urls"] == []
    assert all(i["severity"] == "Info" for i in _orphan_issues(report))


def test_uncrawled_link_targets_make_the_check_inconclusive(monkeypatch):
    pages = {
        SITE: _html("/a", "/elsewhere"),
        "https://ex.com/a": _html("/"),
    }
    report = _audit(monkeypatch, pages, [SITE, "https://ex.com/a"])

    assert report["orphan_pages"]["status"] == "inconclusive"
    assert report["orphan_pages"]["count"] == 0


def test_failed_fetch_makes_the_check_inconclusive(monkeypatch):
    """A page that timed out may be the one linking to the 'orphan'."""
    pages = {
        SITE: _html("/a"),
        "https://ex.com/a": _html("/"),
    }
    report = _audit(monkeypatch, pages, [SITE, "https://ex.com/a", "https://ex.com/down"])

    assert report["orphan_pages"]["status"] == "inconclusive"
    assert "https://ex.com/down" not in report["orphan_pages"]["urls"]


def test_inconclusive_check_never_raises_a_high_severity_issue(monkeypatch):
    pages = {SITE: _html("/a", "/b"), "https://ex.com/a": _html("/")}
    report = _audit(monkeypatch, pages, [SITE, "https://ex.com/a"])

    assert not [i for i in _orphan_issues(report) if i["severity"] == "High"]


# --- link_profile: complete crawls still find real orphans -------------------

def test_complete_crawl_reports_a_real_orphan(monkeypatch):
    pages = {
        SITE: _html("/a"),
        "https://ex.com/a": _html("/"),
        "https://ex.com/lonely": _html("/a"),
    }
    report = _audit(monkeypatch, pages, [SITE, "https://ex.com/a", "https://ex.com/lonely"])

    assert report["orphan_pages"]["status"] == "complete"
    assert report["orphan_pages"]["urls"] == ["https://ex.com/lonely"]
    assert [i["severity"] for i in _orphan_issues(report)] == ["High"]


def test_link_to_itself_is_not_an_inbound_link(monkeypatch):
    pages = {
        SITE: _html("/a"),
        "https://ex.com/a": _html("/"),
        "https://ex.com/island": _html("/island"),
    }
    report = _audit(monkeypatch, pages, [SITE, "https://ex.com/a", "https://ex.com/island"])

    assert report["orphan_pages"]["urls"] == ["https://ex.com/island"]


def test_entry_page_is_exempt_even_when_it_is_not_alphabetically_first(monkeypatch):
    """min(crawled) exempted /about and flagged the real entry page /start."""
    site = "https://ex.com/start"
    pages = {
        site: _html("/about"),
        "https://ex.com/about": _html("/about"),
    }
    report = _audit(monkeypatch, pages, [site, "https://ex.com/about"], site=site)

    assert report["orphan_pages"]["status"] == "complete"
    assert report["orphan_pages"]["urls"] == []


@pytest.mark.parametrize(
    "sitemap_loc, href",
    [
        ("https://ex.com/guide/", "/guide"),
        ("https://ex.com/guide", "/guide/"),
        ("https://EX.com/guide", "/guide"),
    ],
)
def test_url_spelling_variants_are_the_same_page(monkeypatch, sitemap_loc, href):
    pages = {SITE: _html(href), sitemap_loc: _html("/")}
    report = _audit(monkeypatch, pages, [SITE, sitemap_loc])

    assert report["orphan_pages"]["status"] == "complete"
    assert report["orphan_pages"]["urls"] == []


def test_links_to_files_do_not_block_completeness(monkeypatch):
    pages = {
        SITE: _html("/a", "/files/deck.pdf", "/img/logo.png"),
        "https://ex.com/a": _html("/"),
    }
    report = _audit(monkeypatch, pages, [SITE, "https://ex.com/a"])

    assert report["orphan_pages"]["status"] == "complete"


# --- internal_links: link discovery cannot see orphans -----------------------

class _Resp:
    def __init__(self, url, text):
        self.url = url
        self.text = text
        self.status_code = 200
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.history = []


def test_internal_links_makes_no_orphan_claim(monkeypatch):
    site = {
        SITE: _html("/a", "/b"),
        "https://ex.com/a": _html("/"),
        "https://ex.com/b": _html("/"),
    }
    monkeypatch.setattr(
        internal_links.requests, "get", lambda url, **kw: _Resp(url, site.get(url, _html()))
    )
    result = internal_links.crawl_site(SITE, max_depth=2, max_pages=10)

    assert "orphan_candidates" not in result
    assert not [i for i in result["issues"] if "orphan" in i.lower()]
    assert not [r for r in result["recommendations"] if "orphan" in r.lower()]


# --- generate_report: say "not checked", not "0 orphans" ---------------------

def test_report_shows_inconclusive_orphan_check_as_unchecked():
    data = {
        "url": SITE,
        "domain": "ex.com",
        "timestamp": "2026-09-14T09:14:00",
        "sections": {
            "link_profile": {
                "pages_crawled": 20,
                "avg_internal_links_per_page": 150.0,
                "orphan_pages": {"status": "inconclusive", "count": 0, "urls": []},
                "dead_end_pages": {"count": 0, "urls": []},
                "issues": [],
            },
            "internal_links": {"pages_crawled": 16, "total_internal_links": 2465, "issues": []},
        },
    }
    html = generate_report.generate_html(data, generate_report.calculate_overall_score(data))

    assert "Potential Orphan Pages" not in html
    assert "<dt>Orphan pages</dt><dd>—</dd>" in html
