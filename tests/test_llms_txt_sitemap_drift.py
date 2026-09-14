"""llms_txt_checker.py --check-sitemap: llms.txt links the site no longer lists.

The network is replaced with a fake site keyed by URL. What must hold:

  * a markdown twin (/page.md, /page.html.md) is the same page as /page;
  * a link is only called "not in the sitemap" as plainly as that when every
    sitemap file was read -- otherwise the wording says which files were read;
  * a link from a third-party file is never fetched before the URL-safety check;
  * nothing about llms.txt is raised above Info: Google Search ignores the file.
"""

import gzip
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import llms_txt_checker as lc  # noqa: E402

BASE = "https://example.com"


def fake_site(pages: dict):
    """_get replacement: pages maps URL -> (status, body); anything else is a 404."""
    calls = []

    def fake_get(url, timeout=15, max_redirects=5):
        calls.append(url)
        status, body = pages.get(url, (404, "not found"))
        content = body if isinstance(body, bytes) else body.encode()
        text = "" if isinstance(body, bytes) else body
        return status, text, content, url, None

    fake_get.calls = calls
    return fake_get


def sitemap(*urls):
    return "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>"


def llms(*links):
    return {"exists": True, "parsed": {"links": [{"title": "t", "url": u, "description": ""} for u in links]},
            "quality": {"issues": []}}


def compare(result, pages, **kwargs):
    fake = fake_site(pages)
    with patch.object(lc, "_get", side_effect=fake):
        comparison = lc.compare_with_sitemap(result, BASE, **kwargs)
    return comparison, fake.calls


ROBOTS = {f"{BASE}/robots.txt": (200, f"User-agent: *\nSitemap: {BASE}/sitemap.xml\n")}


# --- page identity -----------------------------------------------------------------


@pytest.mark.parametrize("url,expected", [
    ("https://example.com/docs/page", ("example.com", "/docs/page")),
    ("https://www.example.com/docs/page/", ("example.com", "/docs/page")),
    ("http://example.com/docs/page.md", ("example.com", "/docs/page")),
    ("/docs/page.html.md", ("example.com", "/docs/page.html")),
    ("https://example.com/docs/index.html.md", ("example.com", "/docs")),
    ("https://example.com/docs/index.md", ("example.com", "/docs")),
    ("https://example.com/docs/", ("example.com", "/docs")),
    ("https://example.com/?utm=1#top", ("example.com", "/")),
    ("https://docs.example.com/page", ("docs.example.com", "/page")),
])
def test_page_key_treats_markdown_twins_and_url_noise_as_the_same_page(url, expected):
    assert lc.page_key(url, BASE) == expected


# --- comparison ---------------------------------------------------------------------


def test_links_listed_in_the_sitemap_raise_nothing():
    pages = {**ROBOTS, f"{BASE}/sitemap.xml": (200, sitemap(f"{BASE}/", f"{BASE}/docs/page", f"{BASE}/pricing/"))}
    result = llms(f"{BASE}/docs/page.md", "/pricing", "https://github.com/acme")

    comparison, calls = compare(result, pages)

    assert comparison["status"] == "complete"
    assert (comparison["same_site_links"], comparison["external_links"]) == (2, 1)
    assert comparison["missing_from_sitemap"] == [] and result["quality"]["issues"] == []
    assert "https://github.com/acme" not in calls


def test_nested_llms_txt_files_are_not_pages():
    """developers.cloudflare.com/llms.txt links 106 per-product llms.txt files; none belong in a sitemap."""
    pages = {**ROBOTS, f"{BASE}/sitemap.xml": (200, sitemap(f"{BASE}/cache/"))}
    result = llms(f"{BASE}/cache/llms.txt", f"{BASE}/workers/llms-full.txt", f"{BASE}/cache/index.md")

    comparison, _ = compare(result, pages)

    # same_site_links counts the pages compared; nested llms files are counted on their own.
    assert comparison["llms_file_links"] == 2 and comparison["same_site_links"] == 1
    assert comparison["missing_from_sitemap"] == [] and result["quality"]["issues"] == []


def test_hosts_listed_by_the_sitemap_are_the_same_site():
    """docs.anthropic.com redirects to docs.claude.com, and its llms.txt links there."""
    moved = "https://docs.claude.com"
    pages = {**ROBOTS, f"{BASE}/sitemap.xml": (200, sitemap(f"{moved}/en/intro", f"{moved}/en/api"))}
    result = llms(f"{moved}/en/intro.md", f"{moved}/en/retired.md", "https://github.com/acme")

    comparison, _ = compare(result, pages)

    assert (comparison["same_site_links"], comparison["external_links"]) == (2, 1)
    assert comparison["missing_from_sitemap"] == [f"{moved}/en/retired.md"]


def test_a_link_missing_from_the_sitemap_is_checked_and_reported_dead():
    pages = {**ROBOTS, f"{BASE}/sitemap.xml": (200, sitemap(f"{BASE}/")),
             f"{BASE}/moved": (200, "<html>still here</html>")}
    result = llms(f"{BASE}/old-guide.md", f"{BASE}/moved")

    comparison, _ = compare(result, pages)

    assert comparison["missing_from_sitemap"] == [f"{BASE}/old-guide.md", f"{BASE}/moved"]
    assert comparison["dead_links"] == [{"url": f"{BASE}/old-guide.md", "status": 404}]
    assert any("2 llms.txt link(s) are not in the sitemap:" in i for i in result["quality"]["issues"])
    assert any("1 llms.txt link(s) are dead" in i for i in result["quality"]["issues"])


def test_duplicate_links_are_reported_once():
    pages = {**ROBOTS, f"{BASE}/sitemap.xml": (200, sitemap(f"{BASE}/"))}
    comparison, _ = compare(llms(f"{BASE}/gone", f"{BASE}/gone"), pages)

    assert comparison["missing_from_sitemap"] == [f"{BASE}/gone"]


def test_sitemap_indexes_and_gzipped_children_are_followed():
    pages = {
        **ROBOTS,
        f"{BASE}/sitemap.xml": (200, f"<sitemapindex><sitemap><loc>{BASE}/posts.xml.gz</loc></sitemap></sitemapindex>"),
        f"{BASE}/posts.xml.gz": (200, gzip.compress(sitemap(f"{BASE}/blog/a").encode())),
    }
    comparison, _ = compare(llms(f"{BASE}/blog/a.md"), pages)

    assert comparison["sitemap_files"] == [f"{BASE}/sitemap.xml", f"{BASE}/posts.xml.gz"]
    assert comparison["missing_from_sitemap"] == []


def test_without_a_sitemap_nothing_is_called_missing():
    result = llms(f"{BASE}/docs")
    comparison, _ = compare(result, {})

    assert comparison["status"] == "no sitemap" and comparison["missing_from_sitemap"] == []
    assert result["quality"]["issues"] == ["ℹ️ No sitemap could be read, so llms.txt links were not compared against one"]


def test_an_unreadable_child_sitemap_makes_the_claim_partial():
    pages = {
        **ROBOTS,
        f"{BASE}/sitemap.xml": (200, f"<sitemapindex><sitemap><loc>{BASE}/a.xml</loc></sitemap>"
                                     f"<sitemap><loc>{BASE}/b.xml</loc></sitemap></sitemapindex>"),
        f"{BASE}/a.xml": (200, sitemap(f"{BASE}/")),
        f"{BASE}/b.xml": (503, "unavailable"),
    }
    result = llms(f"{BASE}/pricing")
    comparison, _ = compare(result, pages)

    assert comparison["status"] == "partial"
    assert any("not in the sitemap files that could be read" in i for i in result["quality"]["issues"])


def test_dead_link_checks_are_capped():
    pages = {**ROBOTS, f"{BASE}/sitemap.xml": (200, sitemap(f"{BASE}/"))}
    links = [f"{BASE}/gone-{n}" for n in range(8)]
    result = llms(*links)
    comparison, calls = compare(result, pages, max_link_checks=3)

    assert comparison["links_checked"] == 3
    assert sum(1 for c in calls if "/gone-" in c) == 3
    assert any("5 more not checked" in i for i in result["quality"]["issues"])


def test_nothing_is_compared_when_llms_txt_is_absent():
    result = {"exists": False, "parsed": {"links": []}, "quality": {"issues": []}}
    comparison, calls = compare(result, {})

    assert comparison["status"] == "no llms.txt" and calls == []


def test_every_new_issue_is_informational():
    pages = {**ROBOTS, f"{BASE}/sitemap.xml": (200, sitemap(f"{BASE}/"))}
    result = llms(f"{BASE}/gone", f"{BASE}/also-gone")
    compare(result, pages)

    assert result["quality"]["issues"]
    assert all(issue.startswith("ℹ️") for issue in result["quality"]["issues"])


# --- URL safety ------------------------------------------------------------------------


def test_a_link_resolving_to_a_private_address_is_never_requested():
    with (
        patch("url_safety.socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]),
        patch.object(lc.requests, "get") as requests_get,
    ):
        status, _, _, _, error = lc._get("https://internal.example.com/admin")

    assert status is None and "URL safety check failed" in error
    requests_get.assert_not_called()


def test_a_redirect_to_a_private_address_is_not_followed():
    class Redirect:
        status_code = 302
        is_redirect = True
        headers = {"Location": "http://127.0.0.1/admin"}
        text = ""
        content = b""

    with (
        patch("url_safety.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]),
        patch.object(lc.requests, "get", return_value=Redirect()) as requests_get,
    ):
        status, _, _, _, error = lc._get("https://example.com/docs")

    assert status is None and "URL safety check failed" in error
    assert requests_get.call_count == 1
