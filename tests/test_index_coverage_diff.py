"""index_coverage_diff.py: two Page indexing exports in, what moved and why out.

Fixtures are written in the shape Search Console's Export button produces: a
zip (or its folder) holding Critical issues.csv / Non-critical issues.csv
(Reason, Source, Validation, Pages) and Chart.csv (Date, Not indexed, Indexed,
Impressions), and per-reason drill-downs as Table.csv (URL, Last crawled).
"""

import csv
import datetime
import json
import os
import subprocess
import sys
import zipfile

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "scripts", "index_coverage_diff.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import index_coverage_diff as icd  # noqa: E402


def export(folder, reasons, indexed=None, not_indexed=None, end="2026-09-20", zip_it=False):
    """Write a Page indexing export; reasons is [(reason, source, pages)]."""
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "Critical issues.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Reason", "Source", "Validation", "Pages"])
        for reason, source, pages in reasons:
            w.writerow([reason, source, "Not Started", f"{pages:,}"])
    with open(os.path.join(folder, "Non-critical issues.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(["Reason", "Source", "Validation", "Pages"])
    if indexed is not None:
        last = datetime.date.fromisoformat(end)
        with open(os.path.join(folder, "Chart.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Date", "Not indexed", "Indexed", "Impressions"])
            for i in range(30, -1, -1):  # written oldest first, like the export; totals drift so only the last day matches
                w.writerow([(last - datetime.timedelta(days=i)).isoformat(), not_indexed + 3 * i, indexed + 7 * i, 500])
    if not zip_it:
        return str(folder)
    path = f"{folder}.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name in os.listdir(folder):
            zf.write(os.path.join(folder, name), f"ex.com-Coverage-{end}/{name}")
    return path


BEFORE = [
    ("Page with redirect", "Website", 310),
    ("Not found (404)", "Website", 120),
    ("Crawled - currently not indexed", "Google systems", 342),
    ("Discovered - currently not indexed", "Google systems", 90),
    ("URL marked ‘noindex’", "Website", 12),
]
AFTER = [
    ("Page with redirect", "Website", 1480),
    ("Not found (404)", "Website", 126),
    ("Crawled - currently not indexed", "Google systems", 406),
    ("Discovered - currently not indexed", "Google systems", 95),
    ("URL marked ‘noindex’", "Website", 140),
    ("Soft 404", "Website", 3),
]


@pytest.fixture
def pair(tmp_path):
    old = export(tmp_path / "w1", BEFORE, 10234, 874, end="2026-09-13", zip_it=True)
    new = export(tmp_path / "w2", AFTER, 9156, 2250, end="2026-09-20")
    return old, new


def by_reason(result):
    return {r["reason"]: r for r in result["reasons"]}


# --- Reading exports --------------------------------------------------------

def test_reads_a_zip_and_a_folder_with_curly_quotes_and_thousands(pair):
    old = icd.load_export(pair[0])
    assert old["reasons"]["url marked 'noindex'"]["pages"] == 12
    assert old["reasons"]["page with redirect"]["pages"] == 310
    assert old["chart"]["as_of"] == "2026-09-13"
    new = icd.load_export(pair[1])
    assert new["reasons"]["page with redirect"]["pages"] == 1480  # "1,480" in the file
    assert set(new["files"]) >= {"Critical issues.csv", "Chart.csv"}


def test_a_file_that_is_not_a_page_indexing_export_fails_loudly(tmp_path):
    perf = tmp_path / "Queries.csv"
    perf.write_text("Top queries,Clicks,Impressions\nx,1,10\n")
    with pytest.raises(ValueError, match="no Page indexing table"):
        icd.load_export(str(perf))


def test_tilde_and_dash_read_as_zero():
    assert icd._number("~") == 0 and icd._number("-") == 0 and icd._number("1,234") == 1234


def test_unknown_reason_names_fall_back_by_substring_or_stay_unclassified():
    assert icd.canonical_reason("Submitted URL blocked by robots.txt") == "url blocked by robots.txt"
    assert icd.canonical_reason("Excluded by ‘noindex’ tag") == "url marked 'noindex'"
    assert icd.canonical_reason("Something Google adds next year") is None


# --- Thresholds -------------------------------------------------------------

@pytest.mark.parametrize("before,after,expected", [
    (310, 1480, True),    # big absolute move
    (120, 126, False),    # +6: below the floor
    (0, 3, False),        # 0 -> 3 is not "infinite %": below the floor
    (90, 101, True),      # +11 on 90 = 12%: past floor and 5%
    (5000, 5040, False),  # +40 on 5,000 = 0.8%
    (5000, 5050, True),   # +50 always counts
])
def test_moved_needs_the_absolute_floor_before_the_percentage(before, after, expected):
    assert icd.moved(before, after) is expected


# --- Diff and classification ------------------------------------------------

def test_movers_classes_and_the_quality_note(pair):
    result = icd.compare(*pair)
    rows = by_reason(result)
    assert {r["reason"] for r in result["movers"]} == {
        "Page with redirect", "Crawled - currently not indexed", "URL marked ‘noindex’"}
    assert rows["URL marked ‘noindex’"]["class"] == "technical"
    assert rows["Crawled - currently not indexed"]["class"] == "quality"
    assert rows["Page with redirect"]["class"] == "expected"
    assert rows["Soft 404"]["before"] == 0 and not rows["Soft 404"]["moved"]
    assert "Resubmitting" in rows["Crawled - currently not indexed"]["action"]
    assert result["notes"] == [icd.QUALITY_NOTE]


def test_totals_come_from_each_exports_last_chart_day(pair):
    totals = {t["state"]: t for t in icd.compare(*pair)["totals"]}
    assert (totals["Indexed"]["before"], totals["Indexed"]["after"], totals["Indexed"]["direction"]) == (10234, 9156, "worse")
    assert totals["Not indexed"]["delta"] == 1376


def test_a_technical_rise_is_investigated_before_a_larger_expected_one(pair):
    """Redirects rose by 1,170 but are expected; noindex rose by 128 and blocks pages."""
    inv = icd.compare(*pair)["investigate"]
    assert inv["reason"] == "URL marked ‘noindex’" and inv["delta"] == 128


def test_an_indexed_drop_outranks_quality_rises_when_nothing_technical_moved(tmp_path):
    old = export(tmp_path / "a", [("Crawled - currently not indexed", "Google systems", 300)], 10000, 300)
    new = export(tmp_path / "b", [("Crawled - currently not indexed", "Google systems", 400)], 9000, 400)
    assert icd.compare(old, new)["investigate"]["reason"] == "Indexed"


def test_shipped_notes_explain_a_move_and_say_when_none_does(pair, tmp_path):
    notes = ["Migrated /products/item-N to /products/category/item-N with 301 redirects"]
    rows = by_reason(icd.compare(*pair, notes=notes))
    assert rows["Page with redirect"]["shipped_matches"] == notes
    assert rows["Page with redirect"]["likely_cause"].startswith("Shipped this period")
    assert rows["Page with redirect"]["cause_confidence"] == "Likely"
    noindex = rows["URL marked ‘noindex’"]
    assert noindex["cause_confidence"] == "Hypothesis"
    assert "No shipped note names a matching change." in noindex["likely_cause"]


def test_nothing_moved_means_nothing_to_investigate(tmp_path):
    old = export(tmp_path / "a", [("Not found (404)", "Website", 100)])
    new = export(tmp_path / "b", [("Not found (404)", "Website", 104)])
    result = icd.compare(old, new)
    assert result["movers"] == [] and result["investigate"] is None and result["issues"] == []
    assert any("No Chart.csv" in line for line in result["limits"])


# --- Findings ---------------------------------------------------------------

def test_findings_follow_the_contract_and_mark_the_one_to_investigate(pair):
    issues = icd.compare(*pair)["issues"]
    for issue in issues:
        for field in ("finding", "evidence", "impact", "fix", "confidence", "falsifiability", "leading_indicator"):
            assert issue[field], (issue["code"], field)
        assert issue["confidence"] == "Confirmed"
    first = [i for i in issues if "investigate_first" in (i.get("tags") or [])]
    assert len(first) == 1 and "noindex" in first[0]["finding"]
    codes = {i["code"]: i for i in issues}
    assert codes["indexed_drop"]["severity"] == "high"
    assert codes["coverage.page-with-redirect"]["severity"] == "low"
    assert codes["coverage.crawled-currently-not-indexed"]["lane"] == "Human"
    assert icd.QUALITY_NOTE in codes["coverage.crawled-currently-not-indexed"]["impact"]
    assert "between 2026-09-13 and 2026-09-20" in codes["indexed_drop"]["finding"]


def test_improvements_are_not_findings(tmp_path):
    old = export(tmp_path / "a", [("Crawled - currently not indexed", "Google systems", 500)])
    new = export(tmp_path / "b", [("Crawled - currently not indexed", "Google systems", 200)])
    result = icd.compare(old, new)
    assert result["movers"][0]["direction"] == "better" and result["issues"] == []


# --- Example URLs -----------------------------------------------------------

def table(path, urls):
    path.write_text("URL,Last crawled\n" + "".join(f"{u},2026-09-18\n" for u in urls), encoding="utf-8")
    return str(path)


def test_example_urls_diff_and_submitted_share(tmp_path, pair):
    old = table(tmp_path / "old.csv", [f"https://ex.com/p{i}" for i in range(0, 300)])
    new = table(tmp_path / "new.csv", [f"https://ex.com/p{i}/" for i in range(40, 380)])  # trailing slash: same page
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text("<urlset>" + "".join(f"<url><loc>https://ex.com/p{i}</loc></url>" for i in range(350, 400)) + "</urlset>")
    ex = icd.compare(*pair, examples=(old, new), sitemap=str(sitemap))["examples"]
    assert (ex["added"], ex["removed"], ex["added_in_sitemap"]) == (80, 40, 30)
    assert ex["sample"] is False and ex["note"] is None and ex["sitemap_complete"] is True


def test_a_capped_example_list_is_called_a_sample(tmp_path, pair):
    old = table(tmp_path / "old.csv", [f"https://ex.com/a{i}" for i in range(1000)])
    new = table(tmp_path / "new.csv", [f"https://ex.com/b{i}" for i in range(1000)])
    ex = icd.compare(*pair, examples=(old, new))["examples"]
    assert ex["sample"] is True and "at most 1,000" in ex["note"]
    assert len(ex["added_urls"]) == icd.LIST_LIMIT


def test_a_sitemap_index_file_is_not_a_complete_page_list(tmp_path):
    index = tmp_path / "index.xml"
    index.write_text("<sitemapindex><sitemap><loc>https://ex.com/s1.xml</loc></sitemap></sitemapindex>")
    assert icd.load_sitemap_urls(str(index))[1] is False


# --- CLI --------------------------------------------------------------------

def test_cli_json_end_to_end(pair, tmp_path):
    shipped = tmp_path / "shipped.txt"
    shipped.write_text("301 redirects for the product migration\n")
    proc = subprocess.run([sys.executable, SCRIPT, *pair, "--shipped", str(shipped), "--json"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["investigate"]["reason"] == "URL marked ‘noindex’"
    assert out["before"]["as_of"] == "2026-09-13" and out["after"]["as_of"] == "2026-09-20"


def test_cli_reports_a_wrong_file_as_an_error(tmp_path):
    bad = tmp_path / "Queries.csv"
    bad.write_text("Top queries,Clicks\nx,1\n")
    proc = subprocess.run([sys.executable, SCRIPT, str(bad), str(bad), "--json"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1 and "no Page indexing table" in json.loads(proc.stdout)["error"]


def test_cli_sitemap_requires_examples(pair):
    proc = subprocess.run([sys.executable, SCRIPT, *pair, "--sitemap", "x.xml"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2 and "--sitemap needs --examples" in proc.stderr
