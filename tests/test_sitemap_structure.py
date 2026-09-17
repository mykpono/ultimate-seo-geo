"""sitemap_checker.py --lastmod / --structure / --reconcile: additive analyses.

The default output (no flags) must not change: generate_report.py reads the
`score` and the existing keys, and nothing here may move the Health Score.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import site_graph  # noqa: E402
import sitemap_checker as sc  # noqa: E402

S = "https://ex.com"
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def _urlset(entries):
    rows = "".join(f"<url><loc>{u}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>" for u, lm in entries)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'


def _index(children):
    return "<sitemapindex>" + "".join(f"<sitemap><loc>{c}</loc></sitemap>" for c in children) + "</sitemapindex>"


def _serve(monkeypatch, files, robots=None):
    """files: url -> xml (200). robots: text or None (404)."""
    def fake_fetch(url, timeout=12):
        if url.endswith("/robots.txt"):
            return (200, robots) if robots is not None else (404, "")
        if url in files:
            return 200, files[url]
        return 404, ""
    monkeypatch.setattr(sc, "_fetch", fake_fetch)
    monkeypatch.setattr(sc, "_head_check", lambda url, timeout=10: {"url": url, "status": 200, "error": None, "soft_404": False, "redirect": None})
    monkeypatch.setattr(sc, "_page_modified_date", lambda url, timeout=10: (None, None))


DEFAULT_KEYS = {"url", "robots_url", "sitemap_urls", "primary_sitemap_url", "primary_status", "url_count_estimate",
                "url_health", "url_patterns", "issues", "recommendations", "score"}


# --- default output is unchanged --------------------------------------------------------

def test_default_output_has_no_new_keys_and_same_score(monkeypatch):
    _serve(monkeypatch, {S + "/sitemap.xml": _urlset([(S + "/", "2020-01-01")] * 30)}, robots=f"Sitemap: {S}/sitemap.xml\n")
    out = sc.check_sitemaps(S, sample_size=5)
    assert set(out) == DEFAULT_KEYS
    assert out["score"] == 100
    flagged = sc.check_sitemaps(S, sample_size=5, lastmod=True, structure=True, lastmod_pages=False)
    assert flagged["score"] == out["score"]
    assert {"lastmod", "structure"} <= set(flagged)


# --- parsing ------------------------------------------------------------------------------

def test_parse_entries_with_lastmod_and_index():
    entries, children, is_index = sc._parse_entries(_urlset([(S + "/a", "2026-09-01"), (S + "/b", None)]))
    assert not is_index and entries == [{"url": S + "/a", "lastmod": "2026-09-01"}, {"url": S + "/b", "lastmod": None}]
    entries, children, is_index = sc._parse_entries(_index([S + "/s1.xml", "/s2.xml"]))
    assert is_index and entries == [] and children == [S + "/s1.xml", "/s2.xml"]


@pytest.mark.parametrize("value,ok", [
    ("2026-09-01", True), ("2026-09-01T10:00:00Z", True), ("2026-09-01T10:00:00+02:00", True),
    ("2026-09-01T10:00:00.123-0500", True), ("2026-9-1", False), ("yesterday", False), ("2026-13-01", False), ("", False),
])
def test_w3c_dates(value, ok):
    assert (sc._parse_w3c(value) is not None) is ok


def test_w3c_offset_is_applied():
    assert sc._parse_w3c("2026-09-01T10:00:00+02:00") == datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)


# --- lastmod --------------------------------------------------------------------------------

def _entries(n, lastmod):
    return [{"url": f"{S}/p{i}", "lastmod": lastmod(i) if callable(lastmod) else lastmod, "source": "sm"} for i in range(n)]


def test_lastmod_coverage_and_no_lastmod_info():
    r, issues = sc.analyze_lastmod(_entries(10, None), check_pages=False, now=NOW)
    assert r["coverage"] == 0.0 and r["with_lastmod"] == 0
    assert [i["severity"] for i in issues] == ["info"]


def test_identical_lastmod_everywhere_is_a_warning():
    r, issues = sc.analyze_lastmod(_entries(40, "2026-09-10"), check_pages=False, now=NOW)
    assert r["most_common_share"] == 1.0
    assert any("same date" in i["finding"] and i["severity"] == "warning" for i in issues)


def test_varied_lastmod_is_clean():
    r, issues = sc.analyze_lastmod(_entries(40, lambda i: f"2026-0{1 + i % 8}-{10 + i % 15:02d}"), check_pages=False, now=NOW)
    assert r["most_common_share"] < sc.LASTMOD_IDENTICAL_SHARE and issues == []


def test_future_and_invalid_lastmod():
    ents = _entries(5, "2026-09-01") + [{"url": S + "/f", "lastmod": "2027-01-01", "source": "sm"}, {"url": S + "/bad", "lastmod": "last tuesday", "source": "sm"}]
    r, issues = sc.analyze_lastmod(ents, check_pages=False, now=NOW)
    assert r["future_count"] == 1 and r["invalid_count"] == 1
    sev = {i["severity"] for i in issues}
    assert "high" in sev and "warning" in sev


def test_tomorrow_is_within_grace():
    ents = _entries(3, (NOW + timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    r, _ = sc.analyze_lastmod(ents, check_pages=False, now=NOW)
    assert r["future_count"] == 0


def test_all_within_24h_is_info_not_warning():
    ents = _entries(25, lambda i: (NOW - timedelta(hours=i % 20)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    r, issues = sc.analyze_lastmod(ents, check_pages=False, now=NOW)
    assert r["within_24h"] == 25
    assert [i["severity"] for i in issues] == ["info"]


def test_page_dates_stale_and_ahead(monkeypatch):
    dates = {
        S + "/p0": (NOW - timedelta(days=2), "dateModified"),        # page newer than lastmod by 28 days -> stale
        S + "/p1": (NOW - timedelta(days=90), "Last-Modified"),      # lastmod 60 days after the page -> ahead
        S + "/p2": (NOW - timedelta(days=31), "article:modified_time"),  # agree (within a week)
        S + "/p3": (None, None),
    }
    monkeypatch.setattr(sc, "_page_modified_date", lambda url, timeout=10: dates.get(url, (None, None)))
    ents = _entries(4, (NOW - timedelta(days=30)).strftime("%Y-%m-%d"))
    r, issues = sc.analyze_lastmod(ents, sample=10, check_pages=True, now=NOW)
    pc = r["page_check"]
    assert pc["checked"] == 4 and pc["compared"] == 3 and pc["no_signal"] == 1
    assert [x["url"] for x in pc["stale"]] == [S + "/p0"] and [x["url"] for x in pc["ahead"]] == [S + "/p1"] and pc["agree"] == 1
    assert any("changed after their <lastmod>" in i["finding"] for i in issues)


def test_page_modified_date_sources(monkeypatch):
    class Resp:
        def __init__(self, text, headers):
            self.status_code, self.text, self.headers = 200, text, headers
    cases = [
        ('<meta property="article:modified_time" content="2026-09-01T10:00:00Z">', {}, "article:modified_time"),
        ('<script type="application/ld+json">{"@type":"Article","dateModified":"2026-09-02"}</script>', {}, "dateModified"),
        ("", {"Last-Modified": "Wed, 03 Sep 2026 10:00:00 GMT"}, "Last-Modified"),
        ("", {}, None),
    ]
    for text, headers, expected in cases:
        monkeypatch.setattr(sc.requests, "get", lambda *a, _t=text, _h=headers, **k: Resp(_t, _h))
        dt, source = sc._page_modified_date(S + "/x")
        assert source == expected and (dt is not None) is (expected is not None)


# --- structure ------------------------------------------------------------------------------------

def _files(*specs):
    return [{"url": u, "status": st, "url_count": n, "is_index": idx, "bytes": 0} for u, st, n, idx in specs]


def test_single_big_file_should_be_split():
    ents = _entries(sc.SINGLE_FILE_WARN + 1, None)
    r, issues = sc.analyze_structure(_files((S + "/sitemap.xml", 200, len(ents), False)), ents, "ex.com", is_index=False)
    assert r["is_index"] is False and any("single sitemap file" in i["finding"] for i in issues)


def test_over_limit_is_critical():
    ents = _entries(sc.FILE_LIMIT + 1, None)
    _, issues = sc.analyze_structure(_files((S + "/sitemap.xml", 200, len(ents), False)), ents, "ex.com", is_index=False)
    assert any(i["severity"] == "critical" for i in issues)


def test_index_organised_by_section():
    ents = [{"url": f"{S}/blog/{i}", "lastmod": None, "source": S + "/blog.xml"} for i in range(10)]
    ents += [{"url": f"{S}/docs/{i}", "lastmod": None, "source": S + "/docs.xml"} for i in range(10)]
    files = _files((S + "/sitemap_index.xml", 200, 0, True), (S + "/blog.xml", 200, 10, False), (S + "/docs.xml", 200, 10, False))
    r, issues = sc.analyze_structure(files, ents, "ex.com", is_index=True)
    assert r["by_section"] is True and r["children"] == 2
    assert {sf["top_section"] for sf in r["section_files"]} == {"/blog/", "/docs/"}
    assert issues == []


def test_index_not_organised_by_section_is_info():
    ents = [{"url": f"{S}/{'blog' if i % 2 else 'docs'}/{i}", "lastmod": None, "source": S + f"/s{(i // 5) % 2}.xml"} for i in range(20)]  # each file mixes both sections
    files = _files((S + "/idx.xml", 200, 0, True), (S + "/s0.xml", 200, 10, False), (S + "/s1.xml", 200, 10, False))
    r, issues = sc.analyze_structure(files, ents, "ex.com", is_index=True)
    assert r["by_section"] is False and [i["severity"] for i in issues] == ["info"]


def test_unreadable_empty_duplicate_foreign_and_http():
    ents = [{"url": S + "/a", "lastmod": None, "source": S + "/s1.xml"}, {"url": S + "/a", "lastmod": None, "source": S + "/s2.xml"},
            {"url": "https://other.com/x", "lastmod": None, "source": S + "/s1.xml"}, {"url": "http://ex.com/b", "lastmod": None, "source": S + "/s1.xml"},
            {"url": "https://www.ex.com/c", "lastmod": None, "source": S + "/s1.xml"}]
    files = _files((S + "/idx.xml", 200, 0, True), (S + "/s1.xml", 200, 4, False), (S + "/s2.xml", 200, 1, False), (S + "/s3.xml", 200, 0, False), (S + "/s4.xml", 404, 0, False))
    r, issues = sc.analyze_structure(files, ents, "ex.com", is_index=True)
    assert r["duplicates"] == [S + "/a"] and r["other_hosts"] == {"other.com": 1} and r["http_entries"] == 1
    assert r["empty_children"] == [S + "/s3.xml"] and r["unreadable_children"] == [S + "/s4.xml (HTTP 404)"]
    kinds = {i["severity"] for i in issues}
    assert "high" in kinds and "warning" in kinds
    assert not any("www.ex.com" in i["finding"] for i in issues)  # www is the same site


def test_collect_entries_follows_index_and_records_sources(monkeypatch):
    files = {
        S + "/idx.xml": _index([S + "/s1.xml", "/s2.xml", S + "/missing.xml"]),
        S + "/s1.xml": _urlset([(S + "/a", "2026-09-01")]),
        S + "/s2.xml": _urlset([(S + "/b", None)]),
    }
    _serve(monkeypatch, files)
    c = sc._collect_entries(S + "/idx.xml", files[S + "/idx.xml"], S)
    assert c["is_index"] and [f["status"] for f in c["files"]] == [200, 200, 200, 404]
    assert {e["url"]: e["source"] for e in c["entries"]} == {S + "/a": S + "/s1.xml", S + "/b": S + "/s2.xml"}


# --- reconcile ----------------------------------------------------------------------------------------

def _page(url, status=200, robots=None, canonical=None, redirected=False, final_url=None):
    return {"url": url, "key": site_graph.page_key(url), "status": status, "robots_meta": robots, "canonical": canonical,
            "redirected": redirected, "final_url": final_url or url, "depth": 1, "out_links": []}


def _graph(pages, failed=(), complete=True):
    return {"schema_version": site_graph.GRAPH_SCHEMA_VERSION, "site": S + "/", "sitemap": {}, "crawl": {"complete": complete, "failed": list(failed), "reasons": []},
            "pages": {p["key"]: p for p in pages}}


def test_reconcile_buckets():
    pages = [
        _page(S + "/"), _page(S + "/unlisted"), _page(S + "/unlisted-noindex", robots="noindex, follow"),
        _page(S + "/unlisted-canon", canonical=S + "/other"),
        _page(S + "/listed-noindex", robots="NOINDEX"), _page(S + "/listed-canon", canonical=S + "/canon-target"),
        _page(S + "/listed-redirect", redirected=True, final_url=S + "/moved"),
    ]
    sitemap = [S + "/", S + "/listed-noindex/", S + "/listed-canon", S + "/listed-redirect", S + "/gone", S + "/orphan", S + "/file.pdf"]
    entries = [{"url": u, "lastmod": None, "source": "sm"} for u in sitemap]
    g = _graph(pages, failed=[{"url": S + "/gone", "status": 404, "error": "HTTP 404", "depth": 1}], complete=True)
    r, issues = sc.reconcile_with_graph(entries, g)
    assert r["crawled_not_in_sitemap"]["examples"] == [S + "/unlisted"]      # noindex and canonicalised pages are not expected in the sitemap
    assert r["sitemap_noindex"]["examples"] == [S + "/listed-noindex/"]      # slash-insensitive match
    assert r["sitemap_canonicalised_elsewhere"]["examples"][0]["canonical"] == S + "/canon-target"
    assert r["sitemap_redirect"]["examples"][0]["final_url"] == S + "/moved"
    assert r["sitemap_non_200"]["examples"] == [{"url": S + "/gone", "status": 404}]
    assert r["sitemap_unreached_by_crawl"] == {"count": 1, "examples": [S + "/orphan"], "status": "complete"}  # the pdf is not a page
    sev = {i["severity"] for i in issues}
    assert "high" in sev and "warning" in sev
    assert any("not reached by a complete crawl" in i["finding"] for i in issues)


def test_reconcile_orphans_need_a_complete_crawl():
    g = _graph([_page(S + "/")], complete=False)
    entries = [{"url": S + "/", "lastmod": None, "source": "sm"}, {"url": S + "/never", "lastmod": None, "source": "sm"}]
    r, issues = sc.reconcile_with_graph(entries, g)
    assert r["sitemap_unreached_by_crawl"] == {"count": 0, "examples": [], "status": "inconclusive"}
    assert r["not_crawled"] == 1
    assert not any("not reached by a complete crawl" in i["finding"] for i in issues)


def test_reconcile_flag_loads_the_graph_file(monkeypatch, tmp_path):
    g = _graph([_page(S + "/"), _page(S + "/extra")])
    path = tmp_path / "g.json"
    path.write_text(json.dumps(g), encoding="utf-8")
    _serve(monkeypatch, {S + "/sitemap.xml": _urlset([(S + "/", None)])}, robots=f"Sitemap: {S}/sitemap.xml\n")
    out = sc.check_sitemaps(S, sample_size=0, reconcile_graph=str(path))
    assert out["reconcile"]["crawled_not_in_sitemap"]["examples"] == [S + "/extra"]
    assert out["score"] == sc.check_sitemaps(S, sample_size=0)["score"]
