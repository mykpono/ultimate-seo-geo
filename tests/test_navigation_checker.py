"""navigation_checker.py: global chrome, money-page reachability, breadcrumbs.

Built on site_graph's link regions and containers. The in-memory sites here
mirror what the real-site run showed:

  * posthog.com — the footer is plain <div>s, so landmark attribution sees no
    footer; links that repeat outside landmarks are used instead
  * developers.cloudflare.com — a 46-link footer that is almost all links to the
    parent company's domain is not a link dump on THIS site
  * a JavaScript-rendered navigation (fewer than three landmark links in raw
    HTML) is reported as not measured, never as missing
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from bs4 import BeautifulSoup  # noqa: E402

import navigation_checker as nav  # noqa: E402
import site_graph  # noqa: E402

S = "https://ex.com"


# --- site_graph additions this checker relies on ----------------------------------------

def _regions(html):
    soup = BeautifulSoup(html, "html.parser")
    return {a["href"]: site_graph.link_region_and_container(a) for a in soup.find_all("a", href=True)}


def test_container_is_the_outermost_landmark():
    html = """
    <header><nav><a href="/a">a</a></nav><a href="/b">b</a></header>
    <main><aside><a href="/c">c</a></aside><article><a href="/d">d</a></article></main>
    <footer><nav><a href="/e">e</a></nav><div><a href="/f">f</a></div></footer>
    <div><a href="/g">g</a></div>
    """
    r = _regions(html)
    assert r["/a"] == ("nav", "header")
    assert r["/b"] == ("header", "header")
    assert r["/c"] == ("aside", "main")
    assert r["/d"] == ("main", "main")
    assert r["/e"] == ("nav", "footer")       # a footer nav is footer navigation
    assert r["/f"] == ("footer", "footer")
    assert r["/g"] == ("other", "other")


def test_breadcrumb_jsonld_names_in_position_order():
    html = """<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
      {"@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":2,"name":"Shoes","item":"https://ex.com/shoes"},
        {"@type":"ListItem","position":1,"item":{"@id":"https://ex.com/","name":"Home"}},
        {"@type":"ListItem","position":3,"name":"Red Shoe"}]}]}</script>
    <nav aria-label="breadcrumb"><a href="/">Home</a><a href="/shoes">Shoes</a><span>Red Shoe</span></nav>"""
    page = site_graph.extract_page(f"<html><head></head><body>{html}</body></html>", S + "/shoes/red", "ex.com")
    assert page["breadcrumb_jsonld"] == ["Home", "Shoes", "Red Shoe"]
    assert page["breadcrumb_visible"] == ["Home", "Shoes"]


def test_breadcrumb_jsonld_tolerates_list_type_and_missing_positions():
    html = '<script type="application/ld+json">{"@type":["WebPage","BreadcrumbList"],"itemListElement":[{"name":"A"},{"name":"B"}]}</script>'
    page = site_graph.extract_page(f"<html><body>{html}</body></html>", S + "/x", "ex.com")
    assert page["breadcrumb_jsonld"] == ["A", "B"]


def test_fetch_defaults_to_utf8_when_no_charset(monkeypatch):
    """developers.cloudflare.com: nav anchor 'agent setup ↗' read as 'agent setup â'."""
    class Resp:
        status_code = 200
        url = S + "/"
        headers = {"Content-Type": "text/html"}
        encoding = "ISO-8859-1"
        content = "agent setup ↗".encode("utf-8")

        @property
        def text(self):
            return self.content.decode(self.encoding, errors="replace")

    monkeypatch.setattr(site_graph.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(site_graph, "validate_url", lambda u: type("R", (), {"ok": True, "normalized_url": u})())
    assert site_graph.fetch_url(S + "/")["html"] == "agent setup ↗"


# --- fixtures ------------------------------------------------------------------------------------

def _link(href, anchor, region, container, internal=True):
    return {"href": href, "key": site_graph.page_key(href) if internal else None, "anchor": anchor, "rel": [], "region": region, "container": container, "internal": internal}


def _page(url, links, depth=1, visible=None, jsonld=None, redirected=False):
    return {
        "url": url, "key": site_graph.page_key(url), "depth": depth, "status": 200, "redirected": redirected,
        "final_url": url, "title": "T", "h1": None, "jsonld_types": [], "word_count": 400,
        "out_links": links, "parts": site_graph.url_parts(url),
        "breadcrumb_visible": visible or [], "breadcrumb_jsonld": jsonld or [],
    }


def _chrome(nav_hrefs, footer_hrefs=(), unlabelled=()):
    links = [_link(S + h, h.strip("/") or "home", "nav", "header") for h in nav_hrefs]
    links += [_link(S + h, h.strip("/"), "footer", "footer") for h in footer_hrefs]
    links += [_link(S + h, h.strip("/"), "other", "other") for h in unlabelled]
    return links


def _graph(pages, failed=(), site=S + "/"):
    return {
        "schema_version": site_graph.GRAPH_SCHEMA_VERSION, "site": site,
        "sitemap": {"found": False, "complete": False, "reasons": [], "urls": {}},
        "crawl": {"complete": not failed, "reasons": [], "failed": list(failed)},
        "pages": {p["key"]: p for p in pages},
    }


NAV = ["/", "/pricing", "/features", "/blog", "/contact"]


def _saas_site(nav=NAV, footer=("/privacy", "/terms", "/about"), n=10, extra_pages=()):
    pages = [_page(S + "/", _chrome(nav, footer), depth=0)]
    pages += [_page(S + p, _chrome(nav, footer)) for p in ("/pricing", "/features", "/blog", "/contact", "/about", "/privacy", "/terms")]
    pages += [_page(S + f"/blog/post-{i}", _chrome(nav, footer)) for i in range(n)]
    pages += list(extra_pages)
    return pages


# --- global link detection ------------------------------------------------------------------------

def test_global_links_need_80_percent_of_pages():
    pages = _saas_site()
    pages[3]["out_links"] = [_link(S + "/one-off", "x", "nav", "header")]  # a page without the chrome
    g = nav.global_links(pages)
    hrefs = {s["href"] for s in g["primary"]}
    assert S + "/pricing" in hrefs and S + "/one-off" not in hrefs
    assert {s["href"] for s in g["footer"]} == {S + "/privacy", S + "/terms", S + "/about"}
    assert g["threshold_pages"] == 15  # ceil(0.8 * 18)


def test_footer_nav_is_not_primary_nav():
    pages = [_page(S + f"/{i}", [_link(S + "/x", "x", "nav", "footer"), _link(S + "/y", "y", "nav", "header")]) for i in range(5)]
    g = nav.global_links(pages)
    assert [s["href"] for s in g["primary"]] == [S + "/y"]
    assert [s["href"] for s in g["footer"]] == [S + "/x"]


def test_repeating_links_outside_landmarks_are_found():
    """posthog.com: the footer is plain <div>s."""
    pages = [_page(S + f"/{i}", _chrome(["/"], unlabelled=["/pricing", "/docs"])) for i in range(6)]
    pages[0]["out_links"].append(_link(S + "/in-body-once", "once", "main", "main"))
    g = nav.global_links(pages)
    assert {s["href"] for s in g["repeating_unlabelled"]} == {S + "/pricing", S + "/docs"}


def test_fewer_than_three_pages_uses_the_homepage_chrome():
    pages = [_page(S + "/", _chrome(["/", "/pricing"]), depth=0)]
    g = nav.global_links(pages)
    assert {s["href"] for s in g["primary"]} == {S + "/", S + "/pricing"}
    assert "homepage" in g["method"]


def test_sample_spans_first_directories():
    pages = [_page(S + "/", [], depth=0)] + [_page(S + f"/blog/{i}", []) for i in range(20)] + [_page(S + "/docs/a", []), _page(S + "/pricing", [])]
    picked = nav.sample_pages(_graph(pages), 4)
    dirs = [(p.get("parts") or {}).get("dir_1") for p in picked]
    assert picked[0]["depth"] == 0
    assert set(dirs) >= {"blog", "docs", "pricing"}


# --- analyze: money pages ------------------------------------------------------------------------------

def _issues(result, kind):
    return [i for i in result["issues"] if i["type"] == kind]


def test_measured_saas_site_with_everything_in_nav_has_no_money_finding():
    r = nav.analyze(_graph(_saas_site()), site_type="saas")
    assert r["status"] == "measured"
    assert not _issues(r, "money_page_not_in_nav")
    assert {t["label"] for t in r["taxonomy"]["nav_links"]} >= {"pricing", "product_feature", "contact"}


def test_pricing_missing_from_nav_is_high_on_saas():
    pages = _saas_site(nav=["/", "/features", "/blog", "/contact"], extra_pages=[_page(S + f"/pricing/{i}", _chrome(["/", "/features", "/blog", "/contact"])) for i in range(2)])
    r = nav.analyze(_graph(pages), site_type="saas")
    f = _issues(r, "money_page_not_in_nav")
    assert [i["label"] for i in f] == ["pricing"] and f[0]["severity"] == "High"
    assert f[0]["confidence"] == "Likely" and "3 pricing page(s)" in f[0]["evidence"]


def test_a_single_page_of_a_type_is_a_low_signal():
    pages = _saas_site(nav=["/", "/features", "/blog", "/contact"])  # exactly one /pricing page
    r = nav.analyze(_graph(pages), site_type="saas")
    f = _issues(r, "money_page_not_in_nav")
    assert f and f[0]["severity"] == "Low"


def test_footer_link_counts_as_reachable():
    pages = _saas_site(nav=["/", "/features", "/blog", "/contact"], footer=("/pricing", "/privacy"))
    r = nav.analyze(_graph(pages), site_type="saas")
    assert not _issues(r, "money_page_not_in_nav")


def test_repeating_unlabelled_link_counts_as_reachable():
    nav_hrefs = ["/", "/features", "/blog", "/contact"]
    pages = [_page(S + "/", _chrome(nav_hrefs, unlabelled=["/pricing"]), depth=0)] + [_page(S + f"/blog/{i}", _chrome(nav_hrefs, unlabelled=["/pricing"])) for i in range(6)] + [_page(S + "/pricing", _chrome(nav_hrefs, unlabelled=["/pricing"]))]
    r = nav.analyze(_graph(pages), site_type="saas")
    assert not _issues(r, "money_page_not_in_nav")
    assert r["repeating_unlabelled"]["count"] == 1


def test_absent_type_is_not_this_checkers_finding():
    pages = [p for p in _saas_site() if "/pricing" not in p["url"]]
    for p in pages:
        p["out_links"] = [l for l in p["out_links"] if "/pricing" not in l["href"]]
    r = nav.analyze(_graph(pages), site_type="saas")
    assert not [i for i in _issues(r, "money_page_not_in_nav") if i["label"] == "pricing"]


# --- analyze: not measured ------------------------------------------------------------------------------

def test_js_only_nav_is_not_measured_and_downgrades_everything():
    pages = [_page(S + "/", [_link(S + "/pricing", "Pricing", "main", "main")], depth=0)] + [_page(S + f"/blog/{i}", []) for i in range(5)] + [_page(S + f"/pricing/{i}", []) for i in range(3)]
    r = nav.analyze(_graph(pages), site_type="saas")
    assert r["status"] == "not_measured"
    nm = _issues(r, "nav_not_measured")
    assert nm and nm[0]["severity"] == "Info" and "render_page.py" in nm[0]["fix"]
    assert all(i["severity"] in ("Low", "Info") for i in r["issues"])
    money = _issues(r, "money_page_not_in_nav")
    assert money and money[0]["confidence"] == "Hypothesis"


# --- analyze: link health, footer, anchors ---------------------------------------------------------------

def test_broken_and_redirected_nav_links():
    pages = _saas_site(nav=NAV + ["/gone", "/moved"])
    pages.append(_page(S + "/moved", _chrome(NAV + ["/gone", "/moved"]), redirected=True))
    pages[-1]["final_url"] = S + "/moved-here"
    r = nav.analyze(_graph(pages, failed=[{"url": S + "/gone", "status": 404, "error": "HTTP 404", "depth": 1}]), site_type="saas")
    b = _issues(r, "nav_link_broken")
    assert b and b[0]["severity"] == "High" and b[0]["links"][0]["status"] == 404
    m = _issues(r, "nav_link_redirect")
    assert m and m[0]["severity"] == "Medium" and m[0]["links"][0]["final_url"] == S + "/moved-here"


def test_a_nav_link_that_refuses_the_crawler_is_unverified_not_broken():
    """/account answering 401, or the site's own rate limiter answering 429, is not a dead link."""
    pages = _saas_site(nav=NAV + ["/account", "/throttled", "/forbidden", "/gone"])
    failed = [{"url": S + "/account", "status": 401, "error": "HTTP 401", "depth": 1},
              {"url": S + "/throttled", "status": 429, "error": "HTTP 429", "depth": 1},
              {"url": S + "/forbidden", "status": 403, "error": "HTTP 403", "depth": 1},
              {"url": S + "/gone", "status": 404, "error": "HTTP 404", "depth": 1}]
    r = nav.analyze(_graph(pages, failed=failed), site_type="saas")
    [broken] = _issues(r, "nav_link_broken")
    # An internal 403 is still an error: a site that forbids its own public page has a problem.
    assert sorted(l["status"] for l in broken["links"]) == [403, 404] and broken["finding"].startswith("2 ")
    [gap] = _issues(r, "nav_link_unverified")
    assert gap["severity"] == "Info" and gap["kind"] == "data_gap"
    assert sorted(l["status"] for l in gap["links"]) == [401, 429] and "browser" in gap["fix"]


def test_only_refused_nav_links_raise_no_broken_finding():
    pages = _saas_site(nav=NAV + ["/account"])
    r = nav.analyze(_graph(pages, failed=[{"url": S + "/account", "status": 401, "error": "HTTP 401", "depth": 1}]),
                    site_type="saas")
    assert not _issues(r, "nav_link_broken") and _issues(r, "nav_link_unverified")


def test_footer_dump_counts_internal_links_only():
    """developers.cloudflare.com: 46 footer links, 45 of them to another domain."""
    ext = [_link(f"https://parent.com/{i}", f"p{i}", "footer", "footer", internal=False) for i in range(45)]
    pages = [_page(S + f"/{i}", _chrome(NAV) + ext + [_link(S + "/privacy", "privacy", "footer", "footer")]) for i in range(5)]
    r = nav.analyze(_graph(pages), site_type="docs")
    assert not _issues(r, "footer_link_dump")
    big = [_link(S + f"/deep/{i}", f"d{i}", "footer", "footer") for i in range(120)]
    pages = [_page(S + f"/{i}", _chrome(NAV) + big) for i in range(5)]
    r = nav.analyze(_graph(pages), site_type="docs")
    d = _issues(r, "footer_link_dump")
    assert d and "120 global internal links" in d[0]["finding"]


def test_generic_and_ambiguous_anchors():
    links = _chrome(NAV) + [_link(S + "/x", "Learn more", "nav", "header"), _link(S + "/y", "", "nav", "header"),
                            _link(S + "/z1", "Guide", "nav", "header"), _link(S + "/z2", "Guide", "nav", "header")]
    pages = [_page(S + f"/{i}", links) for i in range(5)]
    r = nav.analyze(_graph(pages), site_type="generic")
    g = _issues(r, "nav_generic_anchor")
    assert g and "2 generic and 1 ambiguous" in g[0]["finding"]


# --- analyze: breadcrumbs -----------------------------------------------------------------------------------

def test_breadcrumb_mismatch_and_missing():
    ok = _page(S + "/shoes/red", _chrome(NAV), visible=["Home", "Shoes"], jsonld=["Home", "Shoes", "Red"])
    bad = _page(S + "/shoes/blue", _chrome(NAV), visible=["Home", "Sneakers"], jsonld=["Home", "Shoes", "Blue"])
    none = _page(S + "/shoes/green", _chrome(NAV))
    pages = [_page(S + "/", _chrome(NAV), depth=0), ok, bad, none] + [_page(S + f"/blog/{i}", _chrome(NAV), visible=["Home", "Blog"], jsonld=["Home", "Blog", f"{i}"]) for i in range(4)]
    r = nav.analyze(_graph(pages), site_type="ecommerce")
    m = _issues(r, "breadcrumb_schema_mismatch")
    assert m and m[0]["severity"] == "Medium" and m[0]["pages"] == [S + "/shoes/blue"]
    miss = _issues(r, "breadcrumb_missing")
    assert miss and miss[0]["pages"] == [S + "/shoes/green"]
    assert r["breadcrumbs"]["with_visible"] == 6


def test_breadcrumb_absent_only_for_hierarchical_site_types():
    pages = [_page(S + "/", _chrome(NAV), depth=0)] + [_page(S + f"/shoes/{i}", _chrome(NAV)) for i in range(4)]
    assert _issues(nav.analyze(_graph(pages), site_type="ecommerce"), "breadcrumb_absent")
    assert not _issues(nav.analyze(_graph(pages), site_type="saas"), "breadcrumb_absent")


def test_breadcrumb_jsonld_without_visible_trail():
    pages = [_page(S + "/", _chrome(NAV), depth=0)] + [_page(S + f"/docs/{i}", _chrome(NAV), jsonld=["Home", "Docs", str(i)]) for i in range(4)]
    j = _issues(nav.analyze(_graph(pages), site_type="docs"), "breadcrumb_jsonld_only")
    assert j and j[0]["severity"] == "Low"


def test_current_page_as_last_schema_item_is_not_a_mismatch():
    pages = [_page(S + "/", _chrome(NAV), depth=0)] + [_page(S + f"/a/{i}", _chrome(NAV), visible=["Home", "A"], jsonld=["Home", "A", f"Item {i}"]) for i in range(4)]
    assert not _issues(nav.analyze(_graph(pages), site_type="docs"), "breadcrumb_schema_mismatch")


# --- output contract ----------------------------------------------------------------------------------------

def test_issues_carry_contract_fields_and_are_severity_ordered():
    pages = _saas_site(nav=["/", "/blog"], footer=[])
    r = nav.analyze(_graph(pages), site_type="saas")
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    sev = [i["severity"] for i in r["issues"]]
    assert sev == sorted(sev, key=order.get) and sev
    for i in r["issues"]:
        for k in ("type", "severity", "finding", "evidence", "impact", "fix", "confidence"):
            assert i.get(k), (i["type"], k)
    assert r["taxonomy"]["sections"] == ["blog"]
