"""site_graph.py: one crawl, link regions attributed, completeness recorded.

Every checker in this repo strips <nav>, <header> and <footer> before it looks
at a page, so global navigation has never been part of the audit. site_graph
records the region every link sits in, decomposes URLs into the columns a
structure audit reads, and — following tests/test_orphan_detection.py — says
whether the crawl was complete instead of letting a consumer assume it.

The site is in memory: ``fetch_url`` is monkeypatched with a dict of URL ->
(status, html) so no test touches the network.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from bs4 import BeautifulSoup  # noqa: E402

import site_graph  # noqa: E402

SITE = "https://ex.com/"


def _page(body, head=""):
    return f"<html lang='en'><head><title>T</title>{head}</head><body>{body}</body></html>"


def _links(*hrefs):
    return "".join(f'<a href="{h}">link {h}</a>' for h in hrefs)


def _serve(monkeypatch, pages, sitemaps=None, robots=None):
    """Serve an in-memory site. pages: url -> html (200). sitemaps: url -> xml."""
    sitemaps = sitemaps or {}

    def fake_fetch(url, timeout=10):
        if url.endswith("/robots.txt"):
            if robots is None:
                return {"status": 404, "final_url": url, "html": "", "headers": {}, "error": "HTTP 404"}
            return {"status": 200, "final_url": url, "html": robots, "headers": {}, "error": None}
        if url in sitemaps:
            return {"status": 200, "final_url": url, "html": sitemaps[url], "headers": {"content-type": "application/xml"}, "error": None}
        key = site_graph.page_key(url)
        for u, html in pages.items():
            if site_graph.page_key(u) == key:
                if html is None:
                    return {"status": 500, "final_url": url, "html": "", "headers": {}, "error": "HTTP 500"}
                return {"status": 200, "final_url": u, "html": html, "headers": {"content-type": "text/html"}, "error": None}
        return {"status": 404, "final_url": url, "html": "", "headers": {}, "error": "HTTP 404"}

    monkeypatch.setattr(site_graph, "fetch_url", fake_fetch)
    monkeypatch.setattr(site_graph.time, "sleep", lambda s: None)


# --- url_parts ---------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://ex.com/", {"dir_1": None, "depth": 0, "last_dir": None, "trailing_slash": False}),
    ("https://ex.com/blog/", {"dir_1": "blog", "depth": 1, "last_dir": "blog", "trailing_slash": True}),
    ("https://ex.com/blog/post-title", {"dir_1": "blog", "dir_2": "post-title", "depth": 2, "has_date": False}),
    ("https://ex.com/2026/09/hello", {"has_date": True, "depth": 3}),
    ("https://ex.com/news/2026-09-17-launch", {"has_date": True}),
    ("https://ex.com/p/123456", {"has_numeric_id": True}),
    ("https://ex.com/item/red-shoe-4821", {"has_numeric_id": True}),
    ("https://ex.com/blog/page/3", {"is_paginated": True}),
    ("https://ex.com/blog?page=2", {"is_paginated": True, "query_keys": ["page"], "has_query": True}),
    ("https://ex.com/Docs/API", {"mixed_case": True, "dir_1": "Docs"}),
    ("https://ex.com/files/report.pdf", {"extension": "pdf", "last_dir": "report.pdf"}),
    ("https://ex.com/vs/competitor-a", {"dir_1": "vs", "dir_2": "competitor-a"}),
    ("https://EX.com/A/b?x=1&y=2&x=3", {"host": "ex.com", "query_keys": ["x", "y"]}),
    ("https://ex.com/a/b/c/d/e", {"depth": 5, "dir_3": "c", "last_dir": "e"}),
    ("https://ex.com/about.html", {"extension": "html", "depth": 1}),
    ("https://ex.com/v2.0/docs", {"extension": None, "dir_1": "v2.0"}),
])
def test_url_parts(url, expected):
    parts = site_graph.url_parts(url)
    for k, v in expected.items():
        assert parts[k] == v, f"{url}: {k}={parts[k]!r}, expected {v!r}"


def test_url_parts_dirs_list_matches_dir_columns():
    parts = site_graph.url_parts("https://ex.com/a/b/c/d")
    assert parts["dirs"] == ["a", "b", "c", "d"]
    assert (parts["dir_1"], parts["dir_2"], parts["dir_3"]) == ("a", "b", "c")


# --- page_key / same_site ---------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("https://ex.com/guide/", "https://ex.com/guide"),
    ("https://EX.com/guide", "https://ex.com/guide"),
    ("https://ex.com/guide#top", "https://ex.com/guide"),
    ("https://ex.com/guide?utm=1", "https://ex.com/guide"),
    ("https://ex.com", "https://ex.com/"),
])
def test_page_key_identifies_the_same_page(a, b):
    assert site_graph.page_key(a) == site_graph.page_key(b)


def test_page_key_keeps_distinct_pages_distinct():
    assert site_graph.page_key("https://ex.com/a") != site_graph.page_key("https://ex.com/b")
    assert site_graph.page_key("http://ex.com/a") != site_graph.page_key("https://ex.com/a")


@pytest.mark.parametrize("host,site,expected", [
    ("www.ex.com", "ex.com", True),
    ("ex.com", "www.ex.com", True),
    ("EX.COM", "ex.com", True),
    ("blog.ex.com", "ex.com", False),
    ("other.com", "ex.com", False),
])
def test_same_site(host, site, expected):
    assert site_graph.same_site(host, site) is expected


# --- link regions -----------------------------------------------------------

def _regions(html):
    soup = BeautifulSoup(html, "html.parser")
    return {a["href"]: site_graph.link_region(a) for a in soup.find_all("a", href=True)}


def test_region_landmarks():
    html = """
    <header><a href="/logo">logo</a><nav><a href="/pricing">Pricing</a></nav></header>
    <main><p><a href="/in-body">body</a></p></main>
    <aside><a href="/related">related</a></aside>
    <footer><a href="/privacy">Privacy</a><nav><a href="/sitemap">Sitemap</a></nav></footer>
    <div><a href="/loose">loose</a></div>
    """
    r = _regions(html)
    assert r["/logo"] == "header"
    assert r["/pricing"] == "nav"       # nearest ancestor wins over the enclosing header
    assert r["/in-body"] == "main"
    assert r["/related"] == "aside"
    assert r["/privacy"] == "footer"
    assert r["/sitemap"] == "nav"       # a nav inside the footer is still navigation
    assert r["/loose"] == "other"


def test_region_aria_roles_count_as_landmarks():
    html = """
    <div role="banner"><a href="/a">a</a></div>
    <div role="navigation"><a href="/b">b</a></div>
    <div role="main"><a href="/c">c</a></div>
    <div role="contentinfo"><a href="/d">d</a></div>
    <div role="complementary"><a href="/e">e</a></div>
    """
    r = _regions(html)
    assert (r["/a"], r["/b"], r["/c"], r["/d"], r["/e"]) == ("header", "nav", "main", "footer", "aside")


@pytest.mark.parametrize("wrapper", [
    '<nav aria-label="Breadcrumb"><ol><li><a href="/x">X</a></li></ol></nav>',
    '<ol class="breadcrumb"><li><a href="/x">X</a></li></ol>',
    '<ul class="site-breadcrumbs"><li><a href="/x">X</a></li></ul>',
    '<div id="breadcrumbs"><a href="/x">X</a></div>',
    '<ol itemscope itemtype="https://schema.org/BreadcrumbList"><li><a href="/x">X</a></li></ol>',
    '<main><nav aria-label="breadcrumb"><a href="/x">X</a></nav></main>',
])
def test_breadcrumb_variants_beat_nav_and_main(wrapper):
    assert _regions(wrapper)["/x"] == "breadcrumb"


def test_article_counts_as_main_content():
    assert _regions('<article><a href="/x">x</a></article>')["/x"] == "main"


# --- extract_page -----------------------------------------------------------

def test_extract_page_collects_structure_and_links():
    html = _page(
        '<header><nav><a href="/pricing">Pricing</a><a href="https://other.com/" rel="nofollow sponsored">Out</a></nav></header>'
        '<main><h1>Hello <em>world</em></h1><p>' + "word " * 50 + '</p><a href="/guide#section">Guide</a>'
        '<a href="mailto:x@y.z">mail</a><a href="javascript:void(0)">js</a></main>'
        '<footer><a href="/privacy">Privacy</a></footer>',
        head='<link rel="canonical" href="/hello/"><meta name="robots" content="NOINDEX, follow">'
             '<script type="application/ld+json">{"@context":"https://schema.org","@type":["WebPage","FAQPage"]}</script>'
             '<script type="application/ld+json">{"@graph":[{"@type":"Organization"},{"@type":"BreadcrumbList"}]}</script>'
             '<script type="application/ld+json">[{"@type":"Article"}]</script>',
    )
    page = site_graph.extract_page(html, "https://ex.com/hello", "ex.com")
    assert page["title"] == "T"
    assert page["h1"] == "Hello world"
    assert page["canonical"] == "https://ex.com/hello/"
    assert page["robots_meta"] == "noindex, follow"
    assert page["lang"] == "en"
    assert page["jsonld_types"] == ["WebPage", "FAQPage", "Organization", "BreadcrumbList", "Article"]
    assert page["word_count"] >= 50
    assert page["main_text_hash"]
    hrefs = {l["href"]: l for l in page["out_links"]}
    assert set(hrefs) == {"https://ex.com/pricing", "https://other.com/", "https://ex.com/guide", "https://ex.com/privacy"}
    assert hrefs["https://ex.com/guide"]["region"] == "main"
    assert hrefs["https://ex.com/guide"]["key"] == "https://ex.com/guide"
    assert hrefs["https://other.com/"]["internal"] is False
    assert hrefs["https://other.com/"]["rel"] == ["nofollow", "sponsored"]
    assert hrefs["https://other.com/"]["key"] is None
    assert page["internal_out"] == 3 and page["external_out"] == 1
    assert page["region_counts"]["nav"] == 2 and page["region_counts"]["footer"] == 1


def test_extract_page_word_count_excludes_chrome_when_there_is_no_main():
    chrome = "nav " * 200
    html = _page(f"<nav>{chrome}</nav><div><p>one two three</p></div><footer>{chrome}</footer>")
    page = site_graph.extract_page(html, "https://ex.com/", "ex.com")
    assert page["word_count"] == 3


def test_extract_page_tolerates_broken_jsonld_and_empty_page():
    html = _page("", head='<script type="application/ld+json">{not json</script>')
    page = site_graph.extract_page(html, "https://ex.com/", "ex.com")
    assert page["jsonld_types"] == []
    assert page["word_count"] == 0
    assert page["main_text_hash"] is None
    assert page["h1"] is None and page["canonical"] is None


def test_trailing_slash_href_is_kept_as_written():
    """internal_links.py once stripped slashes at extraction and then reported the
    site's canonical 301 as a redirect. The graph stores the href as linked and
    only the KEY is slash-insensitive."""
    page = site_graph.extract_page(_page('<a href="/guide/">g</a>'), "https://ex.com/", "ex.com")
    assert page["out_links"][0]["href"] == "https://ex.com/guide/"
    assert page["out_links"][0]["key"] == "https://ex.com/guide"


# --- sitemap discovery --------------------------------------------------------

URLSET = (
    '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://ex.com/</loc><lastmod>2026-09-01</lastmod></url>"
    "<url><loc>https://ex.com/a</loc></url>"
    "<url><loc>https://ex.com/b/</loc><lastmod>2026-08-30T10:00:00+00:00</lastmod></url>"
    "</urlset>"
)


def test_parse_sitemap_urlset_with_lastmod():
    entries, children, is_index = site_graph.parse_sitemap(URLSET)
    assert not is_index and children == []
    assert entries == [
        {"url": "https://ex.com/", "lastmod": "2026-09-01"},
        {"url": "https://ex.com/a", "lastmod": None},
        {"url": "https://ex.com/b/", "lastmod": "2026-08-30T10:00:00+00:00"},
    ]


def test_parse_sitemap_index():
    xml = "<sitemapindex><sitemap><loc>https://ex.com/s1.xml</loc><lastmod>2026-01-01</lastmod></sitemap><sitemap><loc>https://ex.com/s2.xml</loc></sitemap></sitemapindex>"
    entries, children, is_index = site_graph.parse_sitemap(xml)
    assert is_index and entries == [] and children == ["https://ex.com/s1.xml", "https://ex.com/s2.xml"]


def test_discover_sitemap_from_robots_expands_index_and_records_source(monkeypatch):
    _serve(
        monkeypatch,
        pages={},
        robots="User-agent: *\nSitemap: https://ex.com/sm-index.xml\n",
        sitemaps={
            "https://ex.com/sm-index.xml": "<sitemapindex><sitemap><loc>https://ex.com/s1.xml</loc></sitemap><sitemap><loc>/s2.xml</loc></sitemap></sitemapindex>",
            "https://ex.com/s1.xml": URLSET,
            "https://ex.com/s2.xml": "<urlset><url><loc>https://ex.com/c</loc><lastmod>2026-09-02</lastmod></url></urlset>",
        },
    )
    sm = site_graph.discover_sitemap(SITE)
    assert sm["found"] and sm["complete"], sm["reasons"]
    assert [s["url"] for s in sm["sources"]] == ["https://ex.com/sm-index.xml", "https://ex.com/s1.xml", "https://ex.com/s2.xml"]
    assert sm["sources"][0]["is_index"] is True
    assert sm["urls"]["https://ex.com/c"] == {"lastmod": "2026-09-02", "source": "https://ex.com/s2.xml"}
    assert sm["urls"]["https://ex.com/a"]["lastmod"] is None
    assert len(sm["urls"]) == 4


def test_discover_sitemap_falls_back_to_the_usual_path_without_robots(monkeypatch):
    _serve(monkeypatch, pages={}, sitemaps={"https://ex.com/sitemap.xml": URLSET})
    sm = site_graph.discover_sitemap(SITE)
    assert sm["found"] and sm["complete"]
    assert sm["sources"][0]["url"] == "https://ex.com/sitemap.xml"


def test_no_sitemap_is_not_complete(monkeypatch):
    _serve(monkeypatch, pages={})
    sm = site_graph.discover_sitemap(SITE)
    assert sm["found"] is False and sm["complete"] is False
    assert any("no sitemap" in r for r in sm["reasons"])


def test_unreadable_child_sitemap_makes_discovery_incomplete(monkeypatch):
    _serve(
        monkeypatch,
        pages={},
        robots="Sitemap: https://ex.com/sm-index.xml\n",
        sitemaps={
            "https://ex.com/sm-index.xml": "<sitemapindex><sitemap><loc>https://ex.com/s1.xml</loc></sitemap><sitemap><loc>https://ex.com/missing.xml</loc></sitemap></sitemapindex>",
            "https://ex.com/s1.xml": URLSET,
        },
    )
    sm = site_graph.discover_sitemap(SITE)
    assert sm["found"] is True
    assert sm["complete"] is False
    assert any("missing.xml" in r for r in sm["reasons"])
    assert len(sm["urls"]) == 3  # what could be read is still returned


def test_sitemap_url_cap_marks_truncated(monkeypatch):
    _serve(monkeypatch, pages={}, sitemaps={"https://ex.com/sitemap.xml": URLSET})
    sm = site_graph.discover_sitemap(SITE, max_urls=2)
    assert sm["complete"] is False and len(sm["urls"]) == 2
    assert any("stopped after 2" in r for r in sm["reasons"])


# --- crawl completeness --------------------------------------------------------

def test_complete_crawl_of_a_small_site(monkeypatch):
    pages = {
        SITE: _page("<nav>" + _links("/a", "/b") + "</nav><main><a href='/files/x.pdf'>pdf</a></main>"),
        "https://ex.com/a": _page("<main>" + _links("/", "/b") + "</main>"),
        "https://ex.com/b": _page("<main>" + _links("/a") + "</main>"),
    }
    _serve(monkeypatch, pages)
    c = site_graph.crawl(SITE, max_pages=10, max_depth=3)
    assert c["complete"] is True, c["reasons"]
    assert c["fetched"] == 3 and c["failed"] == [] and c["truncated"] is False
    assert c["pages"]["https://ex.com/a"]["depth"] == 1
    assert c["pages"]["https://ex.com/"]["depth"] == 0


def test_max_pages_cap_marks_the_crawl_incomplete(monkeypatch):
    pages = {SITE: _page(_links("/a", "/b", "/c")), **{f"https://ex.com/{x}": _page("") for x in "abc"}}
    _serve(monkeypatch, pages)
    c = site_graph.crawl(SITE, max_pages=2, max_depth=3)
    assert c["complete"] is False and c["truncated"] is True
    assert c["fetched"] == 2
    assert any("max_pages=2" in r for r in c["reasons"])


def test_depth_cap_marks_the_crawl_incomplete(monkeypatch):
    pages = {SITE: _page(_links("/a")), "https://ex.com/a": _page(_links("/deep")), "https://ex.com/deep": _page("")}
    _serve(monkeypatch, pages)
    c = site_graph.crawl(SITE, max_pages=10, max_depth=1)
    assert c["complete"] is False
    assert "https://ex.com/deep" not in c["pages"]
    assert any("max_depth=1" in r for r in c["reasons"])


def test_failed_fetch_marks_the_crawl_incomplete_and_is_listed(monkeypatch):
    pages = {SITE: _page(_links("/a", "/down")), "https://ex.com/a": _page(""), "https://ex.com/down": None}
    _serve(monkeypatch, pages)
    c = site_graph.crawl(SITE, max_pages=10)
    assert c["complete"] is False
    assert [f["url"] for f in c["failed"]] == ["https://ex.com/down"]
    assert c["failed"][0]["status"] == 500
    assert c["fetched"] == 2


def test_404_target_is_a_failed_fetch_not_a_crash(monkeypatch):
    pages = {SITE: _page(_links("/gone"))}
    _serve(monkeypatch, pages)
    c = site_graph.crawl(SITE, max_pages=10)
    assert c["failed"][0]["error"] == "HTTP 404" and c["complete"] is False


def test_crawl_does_not_fetch_files_or_external_hosts(monkeypatch):
    pages = {SITE: _page(_links("/doc.pdf", "https://other.com/x", "/a")), "https://ex.com/a": _page("")}
    _serve(monkeypatch, pages)
    c = site_graph.crawl(SITE, max_pages=10)
    assert set(c["pages"]) == {"https://ex.com/", "https://ex.com/a"}
    assert c["complete"] is True


def test_www_and_bare_host_are_one_site(monkeypatch):
    pages = {SITE: _page(_links("https://www.ex.com/a")), "https://www.ex.com/a": _page("")}
    _serve(monkeypatch, pages)
    c = site_graph.crawl(SITE, max_pages=10)
    assert "https://www.ex.com/a" in c["pages"]
    assert c["complete"] is True


def test_slash_variants_are_fetched_once(monkeypatch):
    calls = []
    pages = {SITE: _page(_links("/a", "/a/", "/a#x", "/a?utm=1")), "https://ex.com/a": _page("")}
    _serve(monkeypatch, pages)
    real = site_graph.fetch_url
    monkeypatch.setattr(site_graph, "fetch_url", lambda url, timeout=10: (calls.append(url), real(url, timeout))[1])
    c = site_graph.crawl(SITE, max_pages=10)
    assert set(c["pages"]) == {SITE, "https://ex.com/a"}
    assert sum(1 for u in calls if site_graph.page_key(u) == "https://ex.com/a") == 1
    assert c["complete"] is True


# --- build_graph ----------------------------------------------------------------

def test_build_graph_inbound_by_region_and_sitemap_membership(monkeypatch):
    pages = {
        SITE: _page("<header><nav>" + _links("/pricing", "/blog") + "</nav></header><main><a href='/'>self</a>" + _links("/blog") + "</main>"),
        "https://ex.com/pricing": _page("<nav>" + _links("/", "/blog") + "</nav>"),
        "https://ex.com/blog": _page("<nav>" + _links("/", "/pricing") + "</nav><footer>" + _links("/pricing") + "</footer>"),
    }
    sitemap = "<urlset><url><loc>https://ex.com/</loc></url><url><loc>https://ex.com/pricing/</loc><lastmod>2026-09-01</lastmod></url><url><loc>https://ex.com/ghost</loc></url></urlset>"
    _serve(monkeypatch, pages, sitemaps={"https://ex.com/sitemap.xml": sitemap})
    g = site_graph.build_graph(SITE, max_pages=10)

    assert g["schema_version"] == site_graph.GRAPH_SCHEMA_VERSION
    assert g["crawl"]["complete"] is True and g["sitemap"]["complete"] is True
    pricing = g["pages"]["https://ex.com/pricing"]
    assert pricing["inbound_by_region"] == {"breadcrumb": 0, "nav": 2, "header": 0, "footer": 1, "aside": 0, "main": 0, "other": 0}
    assert pricing["inbound_total"] == 3
    assert pricing["in_sitemap"] is True          # /pricing/ in the sitemap == /pricing crawled
    assert g["pages"]["https://ex.com/blog"]["in_sitemap"] is False
    assert pricing["parts"]["dir_1"] == "pricing"
    home = g["pages"]["https://ex.com/"]
    assert home["inbound_total"] == 2               # self-link does not count
    assert g["summary"]["crawled_not_in_sitemap"] == 1  # /blog
    assert g["summary"]["sitemap_not_crawled"] == 1     # /ghost
    assert g["summary"]["sitemap_urls_with_lastmod"] == 1
    assert g["summary"]["links_by_region"]["nav"] == 6


def test_build_graph_without_sitemap_leaves_membership_unknown(monkeypatch):
    _serve(monkeypatch, {SITE: _page("")})
    g = site_graph.build_graph(SITE, max_pages=5)
    assert g["pages"][SITE]["in_sitemap"] is None
    assert g["summary"]["crawled_not_in_sitemap"] is None
    assert g["sitemap"]["found"] is False


def test_build_graph_accepts_a_bare_domain(monkeypatch):
    _serve(monkeypatch, {SITE: _page("")})
    g = site_graph.build_graph("ex.com", max_pages=5)
    assert g["site"] == SITE and g["domain"] == "ex.com"


def test_graph_round_trips_through_json_and_load_graph(monkeypatch, tmp_path):
    _serve(monkeypatch, {SITE: _page(_links("/a")), "https://ex.com/a": _page("")})
    g = site_graph.build_graph(SITE, max_pages=5)
    path = tmp_path / "site_graph.json"
    path.write_text(json.dumps(g), encoding="utf-8")
    loaded = site_graph.load_graph(str(path))
    assert loaded["pages"].keys() == g["pages"].keys()
    assert loaded["crawl"]["complete"] is True


def test_load_graph_rejects_foreign_or_stale_files(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        site_graph.load_graph(str(p))
    p.write_text(json.dumps({"pages": {}, "crawl": {}, "schema_version": 999}), encoding="utf-8")
    with pytest.raises(ValueError):
        site_graph.load_graph(str(p))


# --- fetch_url safety --------------------------------------------------------------

@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://ex.com/x", "http://127.0.0.1/", "http://169.254.169.254/"])
def test_fetch_url_refuses_unsafe_targets_without_raising(url):
    res = site_graph.fetch_url(url, timeout=1)
    assert res["html"] == "" and res["status"] is None
    assert "safety" in (res["error"] or "")
