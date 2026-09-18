"""The internal-links and redirects scores measure the site, not the report's wording.

Both used to count issue strings. Internal links charged a broken page twice (once
as its summary line, once per page) and a 5xx page only once, so a server error
scored better than a 404. Redirects charged 25 per line, so a loop (a page that
never loads) scored 75 like a single 302, two 302s scored 25, and the correct
http -> https upgrade was penalised as "mixed protocol" exactly like a downgrade.
"""

import datetime
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report as gr  # noqa: E402
import internal_links  # noqa: E402
import redirect_checker  # noqa: E402

SITE = "https://ex.com/"


def _score(check, section):
    return gr.calculate_overall_score({"sections": {check: section}})["raw_categories"][check]


# --- internal links -----------------------------------------------------------------------

def _il(**lists):
    """An internal_links section shaped like the script's: one summary issue per non-empty list."""
    section = {"issues": [f"summary of {k}" for k, v in lists.items() if v and k != "other"]}
    section["issues"] += [f"other problem {n}" for n in range(lists.pop("other", 0))]
    section.update({k: [{"url": f"{SITE}{k}/{n}"} for n in range(v)] for k, v in lists.items()})
    return section


@pytest.mark.parametrize("pages,expected", [(1, 85), (2, 70), (7, 0)])
def test_a_broken_page_is_charged_once(pages, expected):
    assert _score("internal_links", _il(broken_internal_pages=pages)) == expected


def test_a_server_error_costs_what_a_404_costs():
    assert _score("internal_links", _il(server_error_pages=1)) == _score("internal_links", _il(broken_internal_pages=1)) == 85


def test_each_page_kind_and_other_problems():
    assert _score("internal_links", _il(soft_404_pages=1)) == 90
    assert _score("internal_links", _il(redirected_pages=2)) == 90
    assert _score("internal_links", _il(other=2)) == 80
    assert _score("internal_links", _il(broken_internal_pages=1, redirected_pages=1, other=1)) == 70
    assert _score("internal_links", {"issues": []}) == 100


class _Resp:
    def __init__(self, url, status, text=""):
        self.url, self.status_code, self.text, self.history = url, status, text, []
        self.headers = {"content-type": "text/html; charset=utf-8"}


def _page(*hrefs):
    return "<html><head><title>Page</title></head><body>" + "".join(f'<a href="{h}">link {h}</a>' for h in hrefs) + "</body></html>"


def test_internal_links_summarises_each_page_list_in_exactly_one_issue(monkeypatch):
    """The score subtracts one summary issue per non-empty list; pin that the script emits one."""
    site = {SITE: (200, _page("/gone", "/gone2", "/down", "/a")),
            f"{SITE}gone": (404, ""), f"{SITE}gone2": (410, ""), f"{SITE}down": (503, ""),
            f"{SITE}a": (200, _page("/"))}
    monkeypatch.setattr(internal_links.requests, "get",
                        lambda url, **kw: _Resp(url, *site.get(url, (200, _page()))))
    result = internal_links.crawl_site(SITE, max_depth=2, max_pages=10)
    assert len(result["broken_internal_pages"]) == 2 and len(result["server_error_pages"]) == 1
    for key in gr.INTERNAL_LINK_PAGE_PENALTY:
        if result.get(key):
            summaries = [i for i in result["issues"] if f"{len(result[key])} internal" in i]
            assert len(summaries) == 1, (key, result["issues"])
    # 2 broken + 1 server error at 15 each, plus whatever other problems the crawl raised.
    other = len(result["issues"]) - 2
    assert _score("internal_links", result) == max(0, 100 - 45 - other * gr.INTERNAL_LINK_ISSUE_PENALTY)


# --- redirects: drive the real checker --------------------------------------------------------

class _Hop:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self.elapsed = datetime.timedelta(milliseconds=5)


class _Safe:
    def __init__(self, url):
        self.ok, self.reason, self.normalized_url = True, "", url


def _chain(monkeypatch, url, *hops):
    queue = list(hops)
    monkeypatch.setattr(redirect_checker.requests, "head", lambda u, **kw: queue.pop(0))
    monkeypatch.setattr(redirect_checker, "validate_url", lambda u, **kw: _Safe(u))
    return redirect_checker.check_redirects(url)


CASES = {
    "no redirect": ("https://ex.com/", [_Hop(200)], 100),
    "http -> https upgrade": ("http://ex.com/", [_Hop(301, "https://ex.com/"), _Hop(200)], 100),
    "one 301": ("https://ex.com/", [_Hop(301, "https://www.ex.com/"), _Hop(200)], 100),
    "one 302": ("https://ex.com/", [_Hop(302, "https://www.ex.com/"), _Hop(200)], 85),
    "two 302 hops": ("https://ex.com/", [_Hop(302, "https://ex.com/x"), _Hop(302, "https://ex.com/y"), _Hop(200)], 70),
    "three 301 hops": ("https://ex.com/", [_Hop(301, "https://ex.com/x"), _Hop(301, "https://ex.com/y"),
                                          _Hop(301, "https://ex.com/z"), _Hop(200)], 60),
    "https -> http downgrade": ("https://ex.com/", [_Hop(301, "http://ex.com/"), _Hop(200)], 60),
    "loop": ("https://ex.com/a", [_Hop(301, "https://ex.com/b"), _Hop(301, "https://ex.com/a")], 0),
    "no Location": ("https://ex.com/", [_Hop(301)], 0),
}


@pytest.mark.parametrize("name", CASES)
def test_redirect_score(monkeypatch, name):
    url, hops, expected = CASES[name]
    assert _score("redirects", _chain(monkeypatch, url, *hops)) == expected


def test_scores_rank_the_cases_by_how_bad_they_are(monkeypatch):
    s = {name: _score("redirects", _chain(monkeypatch, url, *hops)) for name, (url, hops, _) in CASES.items()}
    assert s["loop"] < s["https -> http downgrade"] <= s["three 301 hops"] < s["two 302 hops"] < s["one 302"] < s["no redirect"]
    assert s["http -> https upgrade"] == s["no redirect"]


def test_many_302_hops_are_charged_once(monkeypatch):
    two = _chain(monkeypatch, *CASES["two 302 hops"][:1], *CASES["two 302 hops"][1])
    assert sum("302" in i for i in two["issues"]) == 2  # the report still names each hop
    assert _score("redirects", two) == 70


def test_an_upgrade_is_not_flagged_and_a_downgrade_is(monkeypatch):
    up = _chain(monkeypatch, "http://ex.com/", _Hop(301, "https://ex.com/"), _Hop(200))
    assert up["issues"] == [] and up["has_mixed_protocol"] and not up["has_downgrade"]
    down = _chain(monkeypatch, "https://ex.com/", _Hop(301, "http://ex.com/"), _Hop(200))
    assert down["has_downgrade"] and down["issues"] == ["🔴 Redirect downgrades HTTPS to HTTP at step 1 — keep every hop on https"]
    # A downgrade that is later upgraded again is still a downgrade.
    back = _chain(monkeypatch, "https://ex.com/", _Hop(301, "http://ex.com/x"), _Hop(301, "https://ex.com/y"), _Hop(200))
    assert back["has_downgrade"]


def test_a_failed_check_is_unmeasured_not_zero():
    scores = gr.calculate_overall_score({"sections": {"redirects": {"error": "timeout", "final_url": None}}})
    assert "redirects" in scores["unmeasured"] and scores["raw_categories"]["redirects"] is None


# --- internal links: the site's own 401 / 429 is unverified, not broken -------------------------

def _crawl(monkeypatch, statuses):
    site = {SITE: (200, _page(*statuses))}
    site.update({f"{SITE}{path.strip('/')}": (code, "") for path, code in statuses.items()})
    monkeypatch.setattr(internal_links.requests, "get",
                        lambda url, **kw: _Resp(url, *site.get(url, (200, _page()))))
    return internal_links.crawl_site(SITE, max_depth=1, max_pages=10)


def test_a_login_page_or_a_throttled_crawl_is_not_a_broken_page(monkeypatch):
    result = _crawl(monkeypatch, {"/account": 401, "/busy": 429, "/private": 403, "/gone": 404})
    assert sorted(p["status"] for p in result["refused_pages"]) == [401, 429]
    # 403 from the site's own server is still an error: it forbids its own public page.
    assert sorted(p["status"] for p in result["broken_internal_pages"]) == [403, 404]
    assert result["refused_pages"][0]["linked_from"] == [SITE]


def test_refused_pages_are_one_open_question_that_costs_nothing(monkeypatch):
    refused = _crawl(monkeypatch, {"/account": 401, "/busy": 429})
    [gap] = [i for i in refused["issues"] if isinstance(i, dict)]
    assert gap["kind"] == "data_gap" and gap["severity"] == "info" and "browser" in gap["fix"]
    assert "/account -> HTTP 401" in gap["evidence"] and "/busy -> HTTP 429" in gap["evidence"]
    assert not refused["broken_internal_pages"]
    clean = _crawl(monkeypatch, {})
    assert _score("internal_links", refused) == _score("internal_links", clean)
    # The report files it under Open questions, not the plan.
    collected = gr._collect_issues({"sections": {"internal_links": refused}})
    assert [i["kind"] for i in collected if i["finding"] == gap["finding"]] == ["data_gap"]


def test_an_info_note_is_never_charged_but_a_warning_line_is():
    note = {"severity": "info", "kind": "data_gap", "finding": "1 internal page(s) could not be verified"}
    assert _score("internal_links", {"issues": [note]}) == 100
    assert _score("internal_links", {"issues": [note, "⚠️ 9 link(s) have no anchor text"]}) == 90
