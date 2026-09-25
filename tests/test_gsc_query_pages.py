"""gsc_query.py page rows: one page, one row.

Search Console reports jump links as their own URLs. On the Improvado v4.1 audit
the per-post impressions of the ad-fraud posts were read from single anchor rows
(#what-is-ad-fraud and so on), which undercounted the pages by about half. These
tests drive the merge directly and main() through a fake service, so no test
needs credentials or the Google client libraries.
"""

import json
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gsc_query as gq  # noqa: E402

POST = "https://improvado.io/blog/ad-fraud"


def api_row(page, clicks, impressions, position, query=None):
    keys = [query, page] if query else [page]
    return {"keys": keys, "clicks": clicks, "impressions": impressions,
            "ctr": clicks / impressions if impressions else 0, "position": position}


# Ordered by clicks, as the API returns them: the anchor rows sit below other pages.
ANCHOR_CASE = [
    api_row("https://improvado.io/pricing", 40, 120_000, 4.0),
    api_row(POST, 10, 100_000, 6.0),
    api_row(POST + "#what-is-ad-fraud", 5, 60_000, 8.0),
    api_row(POST + "#types-of-ad-fraud", 3, 40_000, 9.0),
    api_row(POST + "/", 0, 1_000, 12.0),
]


class FakeService:
    def __init__(self, rows):
        self.rows = rows
        self.bodies = []

    def searchanalytics(self):
        return self

    def query(self, siteUrl, body):
        self.bodies.append(body)
        self._limit = body["rowLimit"]
        return self

    def execute(self):
        return {"rows": self.rows[: self._limit]}


def run_main(monkeypatch, capsys, rows, argv):
    service = FakeService(rows)
    monkeypatch.setattr(gq, "_load_credentials", lambda: object())
    monkeypatch.setattr(gq, "_build_service", lambda creds: service)
    monkeypatch.setattr(sys, "argv", ["gsc_query.py", *argv, "--json"])
    gq.main()
    return json.loads(capsys.readouterr().out), service


def test_merge_sums_fragment_rows_into_one_page():
    rows = gq.format_rows({"rows": ANCHOR_CASE}, ["page"])
    merged, stats = gq.merge_page_rows(rows, ["page"])
    post = next(r for r in merged if r["page"] == POST)
    assert post["impressions"] == 201_000
    assert post["clicks"] == 18
    # impression-weighted: (100k*6 + 60k*8 + 40k*9 + 1k*12) / 201k
    assert post["position"] == round((600_000 + 480_000 + 360_000 + 12_000) / 201_000, 1)
    assert post["ctr"] == round(18 / 201_000, 4)
    assert len(post["merged_urls"]) == 4
    assert stats == {"rows_in": 5, "rows_out": 2, "merged_rows": 3}


def test_unmerged_page_carries_no_merged_urls():
    rows = gq.format_rows({"rows": ANCHOR_CASE}, ["page"])
    merged, _ = gq.merge_page_rows(rows, ["page"])
    pricing = next(r for r in merged if r["page"].endswith("/pricing"))
    assert "merged_urls" not in pricing
    assert pricing["impressions"] == 120_000


def test_merge_keeps_other_dimensions_in_the_key():
    raw = {"rows": [
        api_row(POST, 1, 100, 5.0, query="ad fraud"),
        api_row(POST + "#types", 1, 50, 7.0, query="ad fraud"),
        api_row(POST + "#types", 1, 70, 3.0, query="click fraud"),
    ]}
    rows = gq.format_rows(raw, ["query", "page"])
    merged, stats = gq.merge_page_rows(rows, ["query", "page"])
    by_query = {r["query"]: r for r in merged}
    assert by_query["ad fraud"]["impressions"] == 150
    assert by_query["click fraud"]["impressions"] == 70
    assert stats["rows_out"] == 2


def test_merge_is_a_no_op_without_the_page_dimension():
    rows = [{"query": "a", "clicks": 1, "impressions": 2, "ctr": 0.5, "position": 1.0}]
    merged, stats = gq.merge_page_rows(rows, ["query"])
    assert merged is rows
    assert stats["merged_rows"] == 0


@pytest.mark.parametrize("site_url,expected", [
    ("sc-domain:improvado.io", "domain"),
    ("SC-DOMAIN:improvado.io", "domain"),
    ("https://improvado.io/", "url_prefix"),
])
def test_property_type(site_url, expected):
    assert gq.property_type(site_url) == expected


def test_top_pages_ranks_by_merged_impressions(monkeypatch, capsys):
    # Raw, the pricing row (120k) outranks every single post row (max 100k);
    # merged, the post (201k) is the top page.
    out, service = run_main(monkeypatch, capsys, ANCHOR_CASE,
                            ["sc-domain:improvado.io", "--top-pages", "1"])
    assert [r["page"] for r in out["rows"]] == [POST]
    assert out["rows"][0]["impressions"] == 201_000
    # the fetch asks for --limit rows, not N, so anchor rows below the top N are still read
    assert service.bodies[0]["rowLimit"] == 1000
    assert out["property_type"] == "domain"
    assert out["page_normalization"] == {"applied": True, "rows_in": 5, "rows_out": 2, "merged_rows": 3}
    assert any("upper bound" in note for note in out["limits"])


def test_keep_fragments_returns_raw_rows(monkeypatch, capsys):
    out, _ = run_main(monkeypatch, capsys, ANCHOR_CASE,
                      ["https://improvado.io/", "--dimension", "page", "--keep-fragments"])
    assert out["row_count"] == 5
    assert out["page_normalization"] == {"applied": False}
    assert out["property_type"] == "url_prefix"
    assert not any("upper bound" in note for note in out["limits"])


def test_query_dimension_is_unchanged(monkeypatch, capsys):
    raw = [api_row("ad fraud", 3, 900, 5.0), api_row("click fraud", 1, 400, 8.0)]
    out, service = run_main(monkeypatch, capsys, raw,
                            ["sc-domain:improvado.io", "--top-queries", "2"])
    assert [r["query"] for r in out["rows"]] == ["ad fraud", "click fraud"]
    assert out["page_normalization"] == {"applied": False}
    assert service.bodies[0]["rowLimit"] == 2


def test_truncated_flag_when_the_row_limit_is_reached(monkeypatch, capsys):
    out, _ = run_main(monkeypatch, capsys, ANCHOR_CASE,
                      ["sc-domain:improvado.io", "--dimension", "page", "--limit", "5"])
    assert out["truncated"] is True
    out, _ = run_main(monkeypatch, capsys, ANCHOR_CASE,
                      ["sc-domain:improvado.io", "--dimension", "page", "--limit", "50"])
    assert out["truncated"] is False
