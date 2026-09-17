"""site_architecture.py: sections, equity by section, hubs, navigation, hygiene.

Real-site lessons pinned here:

  * lab.mykpono.com — a JavaScript homepage with no raw-HTML links is a
    "complete" crawl of one page; equity over it put the homepage at 100%.
    Equity now needs at least ten fetched pages covering most of the sitemap.
  * smashingmagazine.com — dated "what is X" blog posts are not evergreen URLs
    carrying a date; year directories (/2010/) are not sections that need a hub
    or a nav link.
  * posthog.com — /questions/ is 59% of the site and nothing in it is linked
    from the global navigation: a real finding, kept.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import site_architecture as arch  # noqa: E402
import site_graph  # noqa: E402

S = "https://ex.com"


# --- fixtures ---------------------------------------------------------------------------------

def _link(href, region="main", container="main", rel=None):
    return {"href": href, "key": site_graph.page_key(href), "anchor": href.rsplit("/", 1)[-1] or "home", "rel": rel or [], "region": region, "container": container, "internal": True}


def _page(url, links=(), depth=1, words=500):
    return {
        "url": url, "key": site_graph.page_key(url), "depth": depth, "status": 200, "redirected": False, "final_url": url,
        "title": "T", "h1": None, "jsonld_types": [], "word_count": words, "out_links": list(links),
        "parts": site_graph.url_parts(url), "breadcrumb_visible": [], "breadcrumb_jsonld": [],
    }


def _graph(pages, sitemap_urls=(), crawl_complete=True, sitemap_complete=None, site=S + "/"):
    if sitemap_complete is None:
        sitemap_complete = bool(sitemap_urls)
    return {
        "schema_version": site_graph.GRAPH_SCHEMA_VERSION, "site": site,
        "sitemap": {"found": bool(sitemap_urls), "complete": sitemap_complete, "reasons": [] if sitemap_complete else ["stopped after 2 sitemap files"],
                    "urls": {u: {"lastmod": None, "source": S + "/sitemap.xml"} for u in sitemap_urls}},
        "crawl": {"complete": crawl_complete, "reasons": [] if crawl_complete else ["crawl stopped at max_pages=5: 9 discovered URL(s) not fetched"], "failed": []},
        "pages": {p["key"]: p for p in pages},
    }


NAV = [S + "/", S + "/pricing", S + "/features", S + "/blog"]


def _chrome():
    return [_link(h, "nav", "header") for h in NAV]


def _site(n_blog=12, n_features=3, extra=()):
    """A complete SaaS crawl: home links everything, blog posts link each other and the hub."""
    pages = [_page(S + "/", _chrome() + [_link(S + f"/blog/post-{i}") for i in range(n_blog)] + [_link(S + f"/features/f{i}") for i in range(n_features)], depth=0)]
    pages += [_page(S + "/pricing", _chrome()), _page(S + "/features", _chrome() + [_link(S + f"/features/f{i}") for i in range(n_features)]),
              _page(S + "/blog", _chrome() + [_link(S + f"/blog/post-{i}") for i in range(n_blog)])]
    pages += [_page(S + f"/features/f{i}", _chrome() + [_link(S + "/pricing")]) for i in range(n_features)]
    pages += [_page(S + f"/blog/post-{i}", _chrome() + [_link(S + f"/blog/post-{(i + 1) % n_blog}"), _link(S + "/blog")]) for i in range(n_blog)]
    pages += list(extra)
    return pages


# --- sections -----------------------------------------------------------------------------------

def test_sections_by_first_directory_with_hub_nav_and_labels():
    pages = _site()
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    sec = {s["path"]: s for s in r["sections"]}
    assert sec["/blog/"]["url_count"] == 13 and sec["/blog/"]["dominant_label"] == "blog_article"
    assert sec["/blog/"]["hub"]["exists"] and sec["/blog/"]["hub"]["status"] == 200
    assert sec["/blog/"]["in_nav"] is True and sec["/features/"]["in_nav"] is True
    assert sec["/features/"]["intent"] == "MOFU" and sec["/pricing/"]["intent"] == "BOFU"
    assert sec["/blog/"]["avg_depth"] == 1.0 and sec["/blog/"]["avg_word_count"] == 500
    assert sec["/blog/"]["sitemap_source"] == S + "/sitemap.xml"
    assert r["inventory"]["complete"] is True


def test_locale_prefix_is_not_a_section():
    urls = [S + "/", S + "/en/blog/a", S + "/en/blog/b", S + "/de/blog/c"]
    r = arch.analyze(_graph([], urls, crawl_complete=False), site_type="generic")
    paths = {s["path"] for s in r["sections"]}
    assert "/blog/" in paths and "/en/" not in paths and "/de/" not in paths


def test_dominant_section_is_split_one_level_down():
    urls = [S + "/", S + "/pricing"] + [S + f"/docs/{sub}/{i}" for sub in ("api", "guides", "sdk") for i in range(25)] + [S + "/docs/x"]
    r = arch.analyze(_graph([], urls, crawl_complete=False), site_type="docs")
    subs = {s["path"]: s for s in r["sections"] if s["parent"] == "/docs/"}
    assert set(subs) == {"/docs/api/", "/docs/guides/", "/docs/sdk/"}
    assert subs["/docs/api/"]["url_count"] == 25
    assert next(s for s in r["sections"] if s["path"] == "/docs/")["url_count"] == 76


def test_small_sections_are_not_split():
    urls = [S + "/"] + [S + f"/blog/{sub}/{i}" for sub in ("a", "b") for i in range(10)]
    r = arch.analyze(_graph([], urls, crawl_complete=False), site_type="generic")
    assert not [s for s in r["sections"] if s["parent"]]


# --- equity -----------------------------------------------------------------------------------------

def test_pagerank_sums_to_one_and_rewards_linked_pages():
    pages = {p["key"]: p for p in [
        _page(S + "/", [_link(S + "/a"), _link(S + "/b")], depth=0),
        _page(S + "/a", [_link(S + "/b")]),
        _page(S + "/b", [_link(S + "/a")]),
        _page(S + "/lonely", []),
    ]}
    pr = arch.pagerank(pages)
    assert abs(sum(pr.values()) - 1) < 1e-9
    assert pr[S + "/a"] > pr[S + "/lonely"] and pr[S + "/b"] > pr[S + "/lonely"]


def test_chrome_links_weigh_a_quarter_of_content_links():
    pages = {p["key"]: p for p in [
        _page(S + "/", [_link(S + "/content"), _link(S + "/chrome", "nav", "header")], depth=0),
        _page(S + "/content", []), _page(S + "/chrome", []), _page(S + "/nothing", []),
    ]}
    pr = arch.pagerank(pages)
    base = pr[S + "/nothing"]  # what a page gets with no inbound link at all
    ratio = (pr[S + "/chrome"] - base) / (pr[S + "/content"] - base)
    assert abs(ratio - arch.CHROME_WEIGHT) < 1e-6
    uniform = arch.pagerank(pages, chrome_weight=1.0)
    assert abs(uniform[S + "/chrome"] - uniform[S + "/content"]) < 1e-9


def test_nofollow_self_links_and_unknown_targets_are_dropped():
    pages = {p["key"]: p for p in [
        _page(S + "/", [_link(S + "/a", rel=["nofollow"]), _link(S + "/", "nav", "header"), _link(S + "/not-fetched")], depth=0),
        _page(S + "/a", []),
    ]}
    pr = arch.pagerank(pages)
    assert abs(pr[S + "/"] - pr[S + "/a"]) < 1e-9  # home is dangling: nothing counted


def test_log_normalisation_tops_at_100():
    n = arch.normalise_log({"a": 0.5, "b": 0.05, "c": 0.005})
    assert n == {"a": 100, "b": 50, "c": 0}
    assert arch.normalise_log({"a": 1.0}) == {"a": 100}


def test_equity_measured_on_a_complete_crawl_and_summed_per_section():
    pages = _site()
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    assert r["equity"]["status"] == "measured"
    shares = r["equity"]["by_section"]
    assert abs(sum(shares.values()) - 1) < 0.01
    assert shares["/blog/"] > shares["/pricing/"]
    assert r["equity"]["top_pages"][0]["score"] == 100


@pytest.mark.parametrize("case", ["incomplete", "too_few", "sitemap_uncovered"])
def test_equity_gates(case):
    pages = _site()
    if case == "incomplete":
        g = _graph(pages, [p["url"] for p in pages], crawl_complete=False)
    elif case == "too_few":
        few = [_page(S + "/", [_link(S + "/a")], depth=0), _page(S + "/a", [])]
        g = _graph(few, [p["url"] for p in few])
    else:
        g = _graph(pages, [p["url"] for p in pages] + [S + f"/unseen/{i}" for i in range(40)])
    reason = arch.equity_gate(g)
    assert reason
    r = arch.analyze(g, site_type="saas")
    assert r["equity"]["status"] == "not measured" and r["equity"]["reason"] == reason
    assert [i for i in r["issues"] if i["type"] == "equity_not_measured"]
    assert all(s["equity_share"] is None for s in r["sections"])


def test_js_homepage_one_page_complete_crawl_is_not_measured():
    """lab.mykpono.com: 1 page fetched, 0 links, 23 sitemap URLs, crawl 'complete'."""
    g = _graph([_page(S + "/", [], depth=0)], [S + "/"] + [S + f"/p{i}" for i in range(23)])
    assert "only 1 page" in arch.equity_gate(g)


def test_equity_mismatch_finding():
    """Blog posts link only to each other; features are reachable only from the homepage."""
    n_blog = 30
    chrome = [_link(S + "/", "nav", "header"), _link(S + "/blog", "nav", "header")]
    pages = [_page(S + "/", chrome + [_link(S + f"/blog/post-{i}") for i in range(n_blog)] + [_link(S + "/features"), _link(S + "/pricing")], depth=0),
             _page(S + "/pricing", chrome), _page(S + "/features", chrome + [_link(S + f"/features/f{i}") for i in range(6)]), _page(S + "/blog", chrome + [_link(S + f"/blog/post-{i}") for i in range(n_blog)])]
    pages += [_page(S + f"/features/f{i}", chrome) for i in range(6)]
    pages += [_page(S + f"/blog/post-{i}", chrome + [_link(S + f"/blog/post-{(i + j) % n_blog}") for j in range(1, 6)]) for i in range(n_blog)]
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    m = [i for i in r["issues"] if i["type"] == "section_equity_mismatch"]
    assert m and m[0]["severity"] == "Medium" and "/features/" in m[0]["sections"]
    assert "/blog/" in m[0]["finding"]


# --- navigation and hubs ----------------------------------------------------------------------------

def test_big_section_not_in_nav_is_medium_when_nav_measured():
    extra = [_page(S + f"/questions/{i}", _chrome()) for i in range(20)]
    pages = _site(extra=extra)
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    f = [i for i in r["issues"] if i["type"] == "section_not_in_nav"]
    assert [i["section"] for i in f] == ["/questions/"] and f[0]["severity"] == "Medium"


def test_section_not_in_nav_is_info_when_nav_not_measured():
    pages = [_page(S + "/", [_link(S + f"/questions/{i}") for i in range(20)], depth=0)] + [_page(S + f"/questions/{i}", []) for i in range(20)]
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    f = [i for i in r["issues"] if i["type"] == "section_not_in_nav"]
    assert f and f[0]["severity"] == "Info" and f[0]["confidence"] == "Hypothesis"


def test_meta_sections_and_year_directories_need_no_nav_or_hub():
    urls = [S + "/", S + "/pricing"] + [S + f"/2010/03/post-{i}" for i in range(30)] + [S + f"/tags/{i}" for i in range(30)] + [S + f"/privacy/{i}" for i in range(6)]
    r = arch.analyze(_graph(_site(), urls, crawl_complete=False), site_type="publisher")
    kinds = {(i["type"], i.get("section")) for i in r["issues"]}
    assert not [k for k in kinds if k[1] in ("/2010/", "/tags/", "/privacy/")]


def test_children_without_hub():
    """smashingmagazine.com: 1,665 /author/ pages and no /author/ page."""
    pages = _site(extra=[_page(S + f"/author/{i}", _chrome()) for i in range(8)])
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    f = [i for i in r["issues"] if i["type"] == "children_without_hub"]
    assert [i["section"] for i in f] == ["/author/"] and f[0]["severity"] == "Medium" and "opportunity" in f[0]["tags"]
    pages.append(_page(S + "/author", _chrome()))
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    assert not [i for i in r["issues"] if i["type"] == "children_without_hub"]


def test_hub_in_sitemap_but_not_fetched_still_counts():
    urls = [S + "/", S + "/customers"] + [S + f"/customers/{i}" for i in range(8)]
    r = arch.analyze(_graph([], urls, crawl_complete=False), site_type="saas")
    sec = next(s for s in r["sections"] if s["path"] == "/customers/")
    assert sec["hub"]["exists"] and sec["hub"]["status"] == "in sitemap"
    assert not [i for i in r["issues"] if i["type"] == "children_without_hub"]


def test_children_without_hub_is_info_on_incomplete_inventory():
    urls = [S + "/"] + [S + f"/customers/{i}" for i in range(8)]
    r = arch.analyze(_graph([], urls, crawl_complete=False, sitemap_complete=False), site_type="saas")
    f = [i for i in r["issues"] if i["type"] == "children_without_hub"]
    assert f and f[0]["severity"] == "Info"


def test_deep_money_section():
    deep = [_page(S + f"/features/deep{i}", _chrome(), depth=6) for i in range(4)]  # with the 4 shallow pages: avg 3.5
    pages = _site(extra=deep)
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    f = [i for i in r["issues"] if i["type"] == "deep_section"]
    assert f and f[0]["section"] == "/features/" and f[0]["severity"] == "Low"


# --- hygiene ------------------------------------------------------------------------------------------

def test_url_hygiene_findings():
    urls = [S + "/", S + "/Docs/API", S + "/pricing/2024/plan", S + "/blog?page=2", S + "/blog/a/", S + "/blog/b"]
    urls += [S + f"/a/b/c/d/e/{i}" for i in range(12)]
    r = arch.analyze(_graph([], urls, crawl_complete=False), site_type="generic")
    kinds = {i["type"] for i in r["issues"]}
    assert {"url_deep_paths", "url_mixed_case", "url_trailing_slash_inconsistent", "url_dated_evergreen", "url_query_in_sitemap"} <= kinds
    h = r["hygiene"]
    assert h["mixed_case"]["examples"] == [S + "/Docs/API"]
    assert h["dated_evergreen"]["examples"] == [S + "/pricing/2024/plan"]
    assert h["trailing_slash_inconsistent_sections"] == ["blog"]


def test_dated_blog_definition_is_not_a_dated_evergreen_url():
    """smashingmagazine.com: /2010/03/what-is-x is a dated article, not a glossary page with a date."""
    urls = [S + "/", S + "/2010/03/what-is-a-grid", S + "/2011/01/what-is-css"]
    r = arch.analyze(_graph([], urls, crawl_complete=False), site_type="publisher")
    assert r["hygiene"]["dated_evergreen"]["count"] == 0


# --- output ------------------------------------------------------------------------------------------------

def test_mermaid_tree_and_contract_fields():
    pages = _site()
    r = arch.analyze(_graph(pages, [p["url"] for p in pages]), site_type="saas")
    assert r["mermaid"].startswith("graph TD") and '/blog/ (13 · blog_article)' in r["mermaid"]
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    sev = [i["severity"] for i in r["issues"]]
    assert sev == sorted(sev, key=order.get)
    for i in r["issues"]:
        for k in ("type", "severity", "finding", "evidence", "impact", "fix", "confidence"):
            assert i.get(k), (i["type"], k)
    assert "keys" not in r["sections"][0]
