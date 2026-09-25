"""redirect_checker.py --graph: the site's own links that redirect, ranked by the pages that carry them.

Calibrated on 40-page graphs of python.org, backlinko.com, moz.com and
smashingmagazine.com (nav links redirecting on 34-39 pages each were the real
finds). Two first-draft traps are tests here: query-string variants
(?utm_content=...) are not redirects, and a suspect that serves directly
(/category/x and /category/x/ both 200) is not reported as one.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "scripts", "redirect_checker.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import redirect_checker as rc  # noqa: E402

S = "https://ex.com"


def link(href, region="main", container="main"):
    return {"href": href, "key": href.split("?")[0].split("#")[0].rstrip("/") or href, "region": region,
            "container": container, "internal": True}


def page(path, links=(), final=None):
    url = f"{S}{path}"
    return {"url": url, "key": url.rstrip("/"), "final_url": final or url, "out_links": list(links)}


def graph(*pages):
    return {"pages": {p["key"]: p for p in pages}}


def walker(chains):
    """check_redirects stand-in: chains maps a start URL to its hop statuses and final URL."""
    def check(url):
        statuses, final, loop = chains.get(url, ([200], url, False))
        return {"chain": [{"status": s} for s in statuses], "total_hops": max(0, len(statuses) - 1),
                "final_url": final, "has_loop": loop, "has_downgrade": False, "error": None}
    return check


def test_a_link_whose_written_url_is_not_where_the_page_ends_is_a_suspect():
    g = graph(
        page("/a", [link(f"{S}/gallery"), link(f"{S}/about/"), link(f"{S}/a")]),   # /a links to itself: ignored
        page("/gallery/", final=f"{S}/gallery/"),
        page("/about/", final=f"{S}/about/"),
    )
    found = rc.redirecting_links(g)["links"]
    assert set(found) == {f"{S}/gallery"}  # /gallery -> /gallery/ is a real hop; /about/ is where it ends


def test_a_pages_link_to_itself_is_not_a_suspect():
    """Logo and breadcrumb links point at the page itself; site_graph leaves them out of inbound counts too."""
    g = graph(page("/a/", [link(f"{S}/a")], final=f"{S}/a/"))
    assert rc.redirecting_links(g)["links"] == {}


def test_query_string_variants_are_not_suspects():
    """moz.com: ?utm_content=... and ?learnContentType=... variants of one fetched page."""
    g = graph(page("/a", [link(f"{S}/pricing?utm_content=footer")]),
              page("/pricing", final=f"{S}/pricing?utm_content=header"))
    assert rc.redirecting_links(g)["links"] == {}


def test_navigation_placement_and_unfetched_targets_are_recorded():
    g = graph(page("/a", [link(f"{S}/old", region="nav", container="header"), link(f"{S}/never-fetched")]),
              page("/b", [link(f"{S}/old")]),
              page("/old", final=f"{S}/new"))
    found = rc.redirecting_links(g)
    slot = found["links"][f"{S}/old"]
    assert slot["chrome"] and slot["content"] and slot["sources"] == {f"{S}/a", f"{S}/b"}
    assert found["unfetched_targets"] == 1


def _site():
    return graph(
        page("/1", [link(f"{S}/one-hop", "nav", "header"), link(f"{S}/chain"), link(f"{S}/loop"),
                    link(f"{S}/dead"), link(f"{S}/both"), link(f"{S}/temp")]),
        page("/2", [link(f"{S}/one-hop", "nav", "header"), link(f"{S}/chain")]),
        page("/3", [link(f"{S}/one-hop", "nav", "header")]),
        page("/one-hop", final=f"{S}/one-hop/"), page("/chain", final=f"{S}/end"), page("/loop", final=f"{S}/x"),
        page("/dead", final=f"{S}/y"), page("/both", final=f"{S}/both/"), page("/temp", final=f"{S}/t2"),
    )


CHAINS = {
    f"{S}/one-hop": ([301, 200], f"{S}/one-hop/", False),
    f"{S}/chain": ([301, 301, 200], f"{S}/end", False),
    f"{S}/loop": ([301, 301], None, True),
    f"{S}/dead": ([301, 404], f"{S}/y", False),
    f"{S}/both": ([200], f"{S}/both", False),        # smashing: both spellings serve 200
    f"{S}/temp": ([302, 200], f"{S}/t2", False),
}


def test_walks_classify_every_suspect_and_rank_by_linking_pages():
    result = rc.audit_site_redirects(_site(), check=walker(CHAINS))
    assert result["counts"] == {"single_hop": 2, "chains": 2, "loops": 1, "ends_in_error": 1,
                                "temporary": 1, "serves_directly": 1}
    assert result["suspects"] == 6 and result["redirecting_links"] == 5
    hrefs = [r["href"] for r in result["redirects"]]
    assert hrefs[0] == f"{S}/one-hop" and hrefs[1] == f"{S}/chain"   # 3 linking pages, then 2
    assert f"{S}/both" not in hrefs
    top = result["redirects"][0]
    assert top["in_navigation"] and top["linking_pages"] == 3 and top["statuses"] == [301, 200]


def test_chains_and_errors_are_assisted_and_single_hops_are_auto():
    issues = {i["code"]: i for i in rc.audit_site_redirects(_site(), check=walker(CHAINS))["issues"]}
    chains = issues["redirects.site_chains"]
    assert (chains["lane"], chains["severity"]) == ("Assisted", "medium")
    assert "2 internal link target(s) redirect through 2+ hops or loop, and 1 redirect to an error page" in chains["finding"]
    single = issues["redirects.links_to_redirects"]
    assert (single["lane"], single["severity"]) == ("Auto", "low")
    assert "fix those once in the template" in single["fix"] and "make it a 301" in single["fix"]
    for issue in issues.values():
        for field in ("finding", "evidence", "impact", "fix", "confidence", "falsifiability", "leading_indicator"):
            assert issue[field], field


def test_max_checks_walks_the_busiest_first_and_counts_the_rest():
    result = rc.audit_site_redirects(_site(), max_checks=1, check=walker(CHAINS))
    assert result["checked"] == 1 and result["not_checked"] == 5
    assert result["redirects"][0]["href"] == f"{S}/one-hop"


def test_no_suspects_means_no_findings():
    result = rc.audit_site_redirects(graph(page("/a", [link(f"{S}/b")]), page("/b")), check=walker({}))
    assert (result["suspects"], result["issues"]) == (0, [])


def test_cli_needs_urls_or_a_graph(tmp_path):
    none = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, timeout=60)
    assert none.returncode == 2 and "--graph" in none.stderr
    bad = tmp_path / "g.json"
    bad.write_text(json.dumps({"pages": {}}))
    proc = subprocess.run([sys.executable, SCRIPT, "--graph", str(bad)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2 and "--graph" in proc.stderr
