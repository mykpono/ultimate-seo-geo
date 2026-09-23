"""gsc_insights.py: Search Console rows in, the rows to act on out.

The analyses are pure functions over API-shaped rows, so they are driven here
directly; the fetch is driven through a fake service that pages like the real
one. No test needs credentials or the Google client libraries.
"""

import json
import os
import subprocess
import sys
from datetime import date

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import gsc_insights as gi  # noqa: E402


def row(query, page, clicks, impressions, position):
    return {"query": query, "page": page, "clicks": clicks, "impressions": impressions,
            "ctr": clicks / impressions if impressions else 0, "position": position}


def curve_rows(position, ctr, n=6, impressions=500):
    """n rows at one position with one CTR: enough for a median bucket."""
    return [row(f"bench {position}-{i}", f"https://ex.com/b{position}-{i}", round(impressions * ctr), impressions, position)
            for i in range(n)]


# --- URL identity -----------------------------------------------------------

def test_page_key_merges_fragment_trailing_slash_and_case():
    assert gi.page_key("https://EX.com/Guide/#faq") == gi.page_key("https://ex.com/Guide")
    assert gi.page_key("https://ex.com/") == "https://ex.com/"
    assert gi.page_key("https://ex.com/a?utm=1") == "https://ex.com/a"


def test_fragment_urls_are_one_page_not_cannibalisation():
    """Search Console reports #fragment URLs for jump links; they are the same page."""
    rows = gi._merge_query_page([
        row("widget price", "https://ex.com/pricing", 50, 900, 3.0),
        row("widget price", "https://ex.com/pricing#faq", 5, 100, 4.0),
    ])
    assert len(rows) == 1
    assert rows[0]["impressions"] == 1000 and rows[0]["clicks"] == 55
    assert rows[0]["position"] == 3.1  # impression-weighted
    assert rows[0]["page"] == "https://ex.com/pricing"
    assert gi.cannibalization(rows)["count"] == 0


# --- CTR benchmark ----------------------------------------------------------

def test_ctr_curve_is_the_sites_own_median_and_skips_thin_buckets():
    rows = curve_rows(3, 0.10) + curve_rows(4, 0.07, n=4)  # 4 rows is below CURVE_MIN_ROWS
    rows.append(row("tiny", "https://ex.com/t", 5, 10, 3))  # below CURVE_MIN_IMPRESSIONS, ignored
    curve = gi.ctr_curve(rows)
    assert curve == {3: {"median_ctr": 0.1, "rows": 6}}


def test_low_ctr_uses_half_the_site_median_and_never_an_industry_table():
    rows = curve_rows(2, 0.20) + [
        row("weak snippet", "https://ex.com/w", 30, 1000, 2.0),    # 3% vs 20% median: flagged
        row("fine snippet", "https://ex.com/f", 150, 1000, 2.2),   # 15%: above half the median
        row("no benchmark", "https://ex.com/n", 1, 1000, 6.0),     # position 6 has no bucket
    ]
    result = gi.low_ctr(rows, gi.ctr_curve(rows))
    assert [i["query"] for i in result["items"]] == ["weak snippet"]
    item = result["items"][0]
    assert item["expected_ctr"] == 0.2 and item["clicks_below_median"] == 170
    assert result["rows_without_benchmark"] == 1


# --- Striking distance ------------------------------------------------------

def test_striking_distance_window_and_impression_floor():
    rows = [
        row("in range", "https://ex.com/a", 4, 900, 11.2),
        row("too few impressions", "https://ex.com/b", 1, 150, 9.0),
        row("already top", "https://ex.com/c", 90, 900, 4.0),
        row("too deep", "https://ex.com/d", 0, 900, 16.0),
        row("edge 8", "https://ex.com/e", 2, 300, 8.0),
        row("edge 15", "https://ex.com/f", 1, 300, 15.0),
    ]
    result = gi.striking_distance(rows, {})
    # By impressions, ties by query text: both edges of the window are inside it.
    assert [i["query"] for i in result["items"]] == ["in range", "edge 15", "edge 8"]
    assert result["count"] == 3


def test_striking_distance_upside_only_from_the_sites_position_3_bucket():
    rows = [row("q", "https://ex.com/a", 4, 1000, 10.0)]
    assert gi.striking_distance(rows, {})["items"][0]["upside_clicks_at_position_3"] == "cannot compute"
    curve = {3: {"median_ctr": 0.1, "rows": 9}}
    result = gi.striking_distance(rows, curve)
    assert result["items"][0]["upside_clicks_at_position_3"] == 96  # 1000 * 10% - 4 clicks already earned
    assert "10.0%" in result["upside_basis"]


# --- Cannibalisation --------------------------------------------------------

def test_cannibalisation_needs_a_second_url_with_a_real_share():
    rows = gi._merge_query_page([
        row("best widgets", "https://ex.com/widgets/", 40, 1200, 6.2),
        row("best widgets", "https://ex.com/blog/widgets-guide", 9, 600, 9.1),
        row("cheap widgets", "https://ex.com/widgets/", 40, 950, 5.0),
        row("cheap widgets", "https://ex.com/blog/other", 0, 50, 40.0),  # 5%: noise, not a split
        row("rare", "https://ex.com/x", 0, 20, 9.0),
        row("rare", "https://ex.com/y", 0, 20, 9.0),  # 40 impressions total: below the floor
    ])
    result = gi.cannibalization(rows)
    assert result["count"] == 1
    hit = result["items"][0]
    assert hit["query"] == "best widgets" and hit["leader"] == "https://ex.com/widgets/"
    assert [p["share"] for p in hit["pages"]] == [0.667, 0.333]


# --- Decay ------------------------------------------------------------------

def _pages(values):
    return {"rows": [{"page": f"https://ex.com/{p}", "clicks": c, "impressions": 1000} for p, c in values.items()]}


def test_decay_needs_two_consecutive_drops_and_tags_seasonal_from_last_year():
    pages = {
        "before_previous": _pages({"trend": 100, "blip": 100, "seasonal": 100, "small": 20, "gone": 100}),
        "previous": _pages({"trend": 80, "blip": 110, "seasonal": 80, "small": 15, "gone": 80}),
        "current": _pages({"trend": 50, "blip": 60, "seasonal": 50, "small": 5}),  # "gone" has no row: 0 clicks
        "previous_last_year": _pages({"trend": 90, "seasonal": 100}),
        "current_last_year": _pages({"trend": 88, "seasonal": 60}),
    }
    result = gi.decay(pages)
    found = {i["page"].rsplit("/", 1)[1]: i for i in result["items"]}
    # blip rose in the previous window (one bad month); small is below the click floor.
    assert set(found) == {"trend", "seasonal", "gone"}
    assert found["trend"]["seasonal"] is False
    assert found["seasonal"]["seasonal"] is True
    assert found["gone"]["seasonal"] == "cannot compute"  # no clicks last year: no basis
    assert found["gone"]["clicks"]["current"] == 0
    assert [i["page"].rsplit("/", 1)[1] for i in result["items"]][0] == "gone"  # most clicks lost first


def test_no_search_console_finding_can_reach_the_critical_level():
    """The check is display-only: none of its findings may trip --fail-on critical."""
    rows = gi._merge_query_page(curve_rows(3, 0.1) + [row("q", "https://ex.com/a", 4, 1000, 10.0),
                                                      row("best", "https://ex.com/a", 40, 1200, 6), row("best", "https://ex.com/b", 9, 600, 9)])
    pages = {"before_previous": _pages({"a": 100}), "previous": _pages({"a": 80}), "current": _pages({"a": 40})}
    results = {"striking_distance": gi.striking_distance(rows, gi.ctr_curve(rows)), "low_ctr": gi.low_ctr(rows, gi.ctr_curve(rows)),
               "cannibalization": gi.cannibalization(rows), "decay": gi.decay(pages),
               "serve_map": gi.serve_map(rows, [("best", "https://ex.com/b")])}
    issues = gi.build_issues(results, "w")
    assert {i["code"] for i in issues} == {"striking_distance", "cannibalization", "decay", "serve_mismatch"}
    assert all(i["severity"] in ("medium", "low") for i in issues)


def test_decay_without_page_history_is_not_measured():
    result = gi.decay({"current": _pages({"a": 10})})
    assert result["status"] == "not measured" and result["count"] == 0


# --- Serve map --------------------------------------------------------------

def test_serve_map_compares_the_intended_page_with_the_most_impressions(tmp_path):
    csv_path = tmp_path / "map.csv"
    csv_path.write_text("query,url\nbest widgets,https://ex.com/blog/widgets-guide\n"
                        "widget price,https://ex.com/pricing/\nnothing,https://ex.com/x\n", encoding="utf-8")
    pairs = gi.load_serve_map(str(csv_path))
    assert pairs[0] == ("best widgets", "https://ex.com/blog/widgets-guide")
    rows = gi._merge_query_page([
        row("best widgets", "https://ex.com/widgets/", 40, 1200, 6.2),
        row("best widgets", "https://ex.com/blog/widgets-guide", 9, 600, 9.1),
        row("Widget Price", "https://ex.com/pricing", 50, 900, 3.0),
    ])
    result = gi.serve_map(rows, pairs)
    status = {i["query"]: i["status"] for i in result["items"]}
    assert status == {"best widgets": "mismatch", "widget price": "match", "nothing": "no data"}
    assert result["items"][0]["status"] == "mismatch"
    assert result["items"][0]["intended_impressions"] == 600


# --- Findings ---------------------------------------------------------------

def test_findings_follow_the_report_contract_and_name_their_urls():
    rows = curve_rows(3, 0.10) + [row("q", "https://ex.com/a", 4, 1000, 10.0)]
    dataset = {"windows": {"current": ["2026-08-24", "2026-09-20"]}, "query_page": {"rows": rows}}
    result = gi.analyse(dataset, {"striking_distance", "low_ctr", "cannibalization"})
    issue = next(i for i in result["issues"] if i["code"] == "striking_distance")
    for field in ("finding", "evidence", "impact", "fix", "confidence", "falsifiability", "leading_indicator"):
        assert issue[field], field
    assert issue["kind"] == "opportunity" and issue["lane"] == "Auto"
    assert issue["urls"] == ["https://ex.com/a"]
    assert "2026-08-24 to 2026-09-20" in issue["finding"]


def test_redirect_advice_is_never_in_the_auto_lane():
    rows = gi._merge_query_page([row("best", "https://ex.com/a", 40, 1200, 6), row("best", "https://ex.com/b", 9, 600, 9)])
    issues = gi.build_issues({"cannibalization": gi.cannibalization(rows)}, "w")
    assert issues[0]["lane"] == "Assisted" and "301" in issues[0]["fix"]


# --- Fetch ------------------------------------------------------------------

class FakeService:
    """Answers searchanalytics().query(...).execute() from a row list, honouring startRow/rowLimit."""

    def __init__(self, total, fail=False):
        self.total, self.fail, self.bodies = total, fail, []

    def searchanalytics(self):
        return self

    def query(self, siteUrl, body):
        self.bodies.append(body)
        self._body = body
        return self

    def execute(self):
        if self.fail:
            raise OSError("403 User does not have sufficient permission")
        start, limit = self._body["startRow"], self._body["rowLimit"]
        return {"rows": [{"keys": [f"q{i}", f"https://ex.com/{i}"], "clicks": 1, "impressions": 10,
                          "ctr": 0.1, "position": 5.0} for i in range(start, min(self.total, start + limit))]}


def test_fetch_pages_with_start_row_until_a_short_page(monkeypatch):
    monkeypatch.setattr(gi, "API_PAGE_SIZE", 10)
    service = FakeService(total=25)
    result = gi.fetch_rows(service, "sc-domain:ex.com", (date(2026, 9, 1), date(2026, 9, 28)), ["query", "page"])
    assert len(result["rows"]) == 25 and result["truncated"] is False
    assert [b["startRow"] for b in service.bodies] == [0, 10, 20]
    assert result["rows"][0] == {"query": "q0", "page": "https://ex.com/0", "clicks": 1, "impressions": 10,
                                 "ctr": 0.1, "position": 5.0}


def test_fetch_reports_truncation_at_the_row_cap(monkeypatch):
    monkeypatch.setattr(gi, "API_PAGE_SIZE", 10)
    result = gi.fetch_rows(FakeService(total=50), "p", (date(2026, 9, 1), date(2026, 9, 28)), ["page"], max_rows=20)
    assert len(result["rows"]) == 20 and result["truncated"] is True


def test_fetch_failure_raises_instead_of_returning_partial_rows():
    with pytest.raises(RuntimeError, match="sufficient permission"):
        gi.fetch_rows(FakeService(total=5, fail=True), "p", (date(2026, 9, 1), date(2026, 9, 28)), ["page"])


def test_windows_are_consecutive_and_exact_length():
    end = date(2026, 9, 20)
    assert gi.window(end, 28) == (date(2026, 8, 24), date(2026, 9, 20))
    assert gi.window(end, 28, 1) == (date(2026, 7, 27), date(2026, 8, 23))
    ly = gi.year_before(gi.window(end, 28))
    assert ly[0].weekday() == date(2026, 8, 24).weekday()


def test_dataset_fetches_history_only_for_decay():
    service = FakeService(total=3)
    without = gi.fetch_dataset(service, "p", date(2026, 9, 20), 28, history=False, max_rows=100)
    assert set(without["pages"]) == {"current"} and len(service.bodies) == 2
    with_history = gi.fetch_dataset(FakeService(total=3), "p", date(2026, 9, 20), 28, history=True, max_rows=100)
    assert set(with_history["pages"]) == {"current", "previous", "before_previous",
                                          "current_last_year", "previous_last_year"}


# --- Page traffic loader (what generate_report.py --gsc-pages reads) ---------

def test_load_page_traffic_reads_the_search_console_pages_csv(tmp_path):
    path = tmp_path / "Pages.csv"
    path.write_text("﻿Top pages,Clicks,Impressions,CTR,Position\n"
                    "https://ex.com/a/,1200,30000,4%,7.1\nhttps://ex.com/a#x,3,50,6%,2\nhttps://ex.com/b,\"1,050\",9000,1%,9\n",
                    encoding="utf-8")
    traffic = gi.load_page_traffic(str(path))
    assert traffic["source"].startswith("Search Console Pages export")
    assert traffic["pages"][0] == {"page": "https://ex.com/a/", "clicks": 1203, "impressions": 30050}
    assert traffic["total_clicks"] == 2253


def test_load_page_traffic_reads_gsc_query_and_insights_output(tmp_path):
    q = tmp_path / "q.json"
    q.write_text(json.dumps({"dimensions": ["page"], "start_date": "2026-08-24", "end_date": "2026-09-20",
                             "rows": [{"page": "https://ex.com/a", "clicks": 5, "impressions": 50}]}))
    assert gi.load_page_traffic(str(q))["window"] == ["2026-08-24", "2026-09-20"]
    i = tmp_path / "i.json"
    i.write_text(json.dumps({"windows": {"current": ["a", "b"]}, "pages": [{"page": "https://ex.com/a", "clicks": 5, "impressions": 50}]}))
    assert gi.load_page_traffic(str(i))["total_clicks"] == 5


def test_load_page_traffic_rejects_a_file_with_no_page_rows(tmp_path):
    bad = tmp_path / "q.json"
    bad.write_text(json.dumps({"dimensions": ["query"], "rows": [{"query": "x", "clicks": 1}]}))
    with pytest.raises(ValueError, match="no page rows"):
        gi.load_page_traffic(str(bad))
    csv_bad = tmp_path / "Queries.csv"
    csv_bad.write_text("Top queries,Clicks\nx,1\n")
    with pytest.raises(ValueError, match="Pages export"):
        gi.load_page_traffic(str(csv_bad))


# --- CLI --------------------------------------------------------------------

def test_cli_replay_runs_every_analysis_without_google_libraries(tmp_path):
    dataset = {
        "site_url": "sc-domain:ex.com", "windows": {"current": ["2026-08-24", "2026-09-20"]},
        "query_page": {"rows": curve_rows(3, 0.1) + [row("q", "https://ex.com/a", 4, 1000, 10.0)], "truncated": True},
        "pages": {"current": _pages({"a": 50})},
    }
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(dataset))
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gsc_insights.py"), "--replay", str(path), "--all", "--json"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["striking_distance"]["count"] == 1
    assert out["decay"]["status"] == "not measured"
    assert out["truncated"] == ["query_page"] and any("Row cap" in line for line in out["limits"])
    assert out["pages"] == [{"page": "https://ex.com/a", "clicks": 50, "impressions": 1000}]


def test_cli_requires_an_analysis():
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gsc_insights.py"), "sc-domain:ex.com"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2 and "choose an analysis" in proc.stderr
