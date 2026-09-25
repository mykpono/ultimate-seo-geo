#!/usr/bin/env python3
"""
Search Console opportunity analysis (Tier 1 — OAuth2).

gsc_query.py returns rows; this script says which rows to act on. It fetches
query x page performance and page clicks over several date windows, then runs
five analyses over them:

  --striking-distance  queries at average position 8-15 with real impressions
  --low-ctr            queries whose CTR is below half the SITE'S OWN median
                       CTR at that position (not an industry table)
  --cannibalization    queries where a second URL of the site takes a real share
                       of the impressions
  --decay              pages that lost clicks in two consecutive windows (a
                       trend, not one bad month), tagged "seasonal" when the
                       same windows a year earlier fell the same way
  --serve-map CSV      the page you intend for a query vs the page Google shows

Every number comes from the API response. Where the data cannot support a
number the output says so (``"cannot compute"``) rather than estimating, and
any estimate that is printed (upside clicks) names the site's own CTR bucket it
was derived from.

Known limits, stated in every JSON result under "limits":
  * Search Console drops anonymised queries, so query rows never sum to page
    totals. Page totals come from a separate page-dimension request.
  * The API returns at most 25,000 rows per request; this script pages with
    startRow up to --max-rows and reports "truncated" when it stops early.
  * Data lags about three days; windows end 3 days before today by default.

Credentials are gsc_query.py's (service account, GSC_CREDENTIALS, or the token
written by gsc_export.py --auth).

Usage:
    python scripts/gsc_insights.py sc-domain:example.com --all --json
    python scripts/gsc_insights.py https://example.com/ --striking-distance --low-ctr
    python scripts/gsc_insights.py sc-domain:example.com --serve-map targets.csv --json
    python scripts/gsc_insights.py sc-domain:example.com --all --save-rows rows.json
    python scripts/gsc_insights.py --replay rows.json --all --json      # no API call
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import date, timedelta
from urllib.parse import urlparse

API_PAGE_SIZE = 25000
DEFAULT_MAX_ROWS = 100000

# Thresholds. Each is a CLI flag; these are the defaults the docs quote.
STRIKING_MIN_POS = 8.0
STRIKING_MAX_POS = 15.0
STRIKING_MIN_IMPRESSIONS = 200
LOW_CTR_MAX_POS = 10.0
LOW_CTR_RATIO = 0.5
LOW_CTR_MIN_IMPRESSIONS = 100
CURVE_MIN_IMPRESSIONS = 20   # a row below this says little about CTR
CURVE_MIN_ROWS = 5           # a position bucket needs this many rows for a median
CANNIBAL_MIN_IMPRESSIONS = 50
CANNIBAL_MIN_SHARE = 0.10
DECAY_MIN_CLICKS = 30
DECAY_MIN_DROP = 0.20
DEFAULT_LIMIT = 25

LIMITS = [
    "Search Console omits anonymised queries: query rows do not sum to page totals.",
    "Average position is impression-weighted over the window; a page ranking 3 on some days and 20 on others averages near 11.",
    "CTR benchmarks are this property's own medians per rounded position, from rows with enough impressions; they are not industry figures.",
]


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

def page_key(url: str) -> str:
    """Identity of a page across Search Console, sitemaps and crawls.

    Same rule as link_profile.page_key (scheme and host lower-cased, trailing
    slash and query/fragment dropped), so /guide/ and /guide#faq are one page.
    Search Console reports fragment URLs for sitelinks and jump links; counted
    apart they would read as two pages competing for one query.
    """
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(url or "").strip().rstrip("/").lower()
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


# ---------------------------------------------------------------------------
# Date windows
# ---------------------------------------------------------------------------

def window(end: date, days: int, offset: int = 0) -> tuple:
    """(start, end) of the days-long window ending `offset` whole windows before `end`."""
    last = end - timedelta(days=days * offset)
    return last - timedelta(days=days - 1), last


def year_before(bounds: tuple) -> tuple:
    start, end = bounds
    return start - timedelta(days=364), end - timedelta(days=364)  # 52 weeks keeps weekdays aligned


# ---------------------------------------------------------------------------
# Fetch (the only part that touches the API)
# ---------------------------------------------------------------------------

def fetch_rows(service, site_url: str, bounds: tuple, dimensions: list, max_rows: int = DEFAULT_MAX_ROWS) -> dict:
    """{"rows": [...], "truncated": bool} for one date window, paged with startRow.

    Raises RuntimeError with the API's message on failure: a partial fetch
    silently analysed as complete would under-report every finding.
    """
    rows = []
    start_row = 0
    while True:
        body = {
            "startDate": bounds[0].isoformat(),
            "endDate": bounds[1].isoformat(),
            "dimensions": dimensions,
            "rowLimit": min(API_PAGE_SIZE, max_rows - len(rows)),
            "startRow": start_row,
            "dataState": "final",
        }
        try:
            response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        except Exception as exc:  # the client raises HttpError, socket errors, auth errors
            raise RuntimeError(f"Search Analytics query failed ({','.join(dimensions)}, "
                               f"{body['startDate']}..{body['endDate']}): {exc}") from exc
        batch = response.get("rows", []) or []
        for row in batch:
            keys = row.get("keys", [])
            entry = {dim: (keys[i] if i < len(keys) else "") for i, dim in enumerate(dimensions)}
            entry.update(clicks=row.get("clicks", 0), impressions=row.get("impressions", 0),
                         ctr=row.get("ctr", 0.0), position=row.get("position", 0.0))
            rows.append(entry)
        if len(batch) < body["rowLimit"]:
            return {"rows": rows, "truncated": False}
        if len(rows) >= max_rows:
            return {"rows": rows, "truncated": True}
        start_row += len(batch)


def fetch_dataset(service, site_url: str, end: date, days: int, *, history: bool, max_rows: int) -> dict:
    """Everything the analyses read, in the shape --save-rows writes and --replay reads.

    Always: query x page and page totals for the current window (page totals are
    what generate_report.py --gsc-pages joins to findings). With history (for
    --decay): page totals for the two windows before it and for the current and
    previous windows a year earlier — seven requests in all.
    """
    current = window(end, days)
    named = {"current": current}
    if history:
        named["previous"] = window(end, days, 1)
        named["before_previous"] = window(end, days, 2)
        named["current_last_year"] = year_before(current)
        named["previous_last_year"] = year_before(named["previous"])
    dataset = {
        "site_url": site_url,
        "days": days,
        "windows": {name: [d.isoformat() for d in bounds] for name, bounds in named.items()},
        "query_page": fetch_rows(service, site_url, current, ["query", "page"], max_rows),
        "pages": {name: fetch_rows(service, site_url, bounds, ["page"], max_rows) for name, bounds in named.items()},
    }
    return dataset


# ---------------------------------------------------------------------------
# Analyses (pure: rows in, results out; tests drive these directly)
# ---------------------------------------------------------------------------

def _rows(block) -> list:
    if isinstance(block, dict):
        return block.get("rows", []) or []
    return block or []


def _merge_query_page(rows: list) -> list:
    """Collapse rows whose pages share a page_key (fragments, trailing slashes).

    Position is re-weighted by impressions, CTR recomputed from the sums.
    """
    merged = {}
    for row in rows:
        query = str(row.get("query", "")).strip()
        page = str(row.get("page", "")).strip()
        if not query or not page:
            continue
        key = (query.lower(), page_key(page))
        slot = merged.setdefault(key, {"query": query, "page": page, "clicks": 0, "impressions": 0, "_pos": 0.0})
        impressions = row.get("impressions", 0) or 0
        slot["clicks"] += row.get("clicks", 0) or 0
        slot["impressions"] += impressions
        slot["_pos"] += (row.get("position", 0) or 0) * impressions
        if len(page) < len(slot["page"]):
            slot["page"] = page  # prefer the fragment-free spelling
    out = []
    for slot in merged.values():
        impressions = slot["impressions"]
        out.append({
            "query": slot["query"],
            "page": slot["page"],
            "clicks": slot["clicks"],
            "impressions": impressions,
            "ctr": round(slot["clicks"] / impressions, 4) if impressions else 0.0,
            "position": round(slot["_pos"] / impressions, 1) if impressions else 0.0,
        })
    return out


def ctr_curve(rows: list, min_impressions: int = CURVE_MIN_IMPRESSIONS, min_rows: int = CURVE_MIN_ROWS) -> dict:
    """{position: {"median_ctr", "rows"}} for rounded positions 1-10 with enough data.

    A bucket with fewer than min_rows qualifying rows is left out: a median of
    two queries is not a benchmark. Consumers must treat a missing bucket as
    "cannot compute", never fall back to an industry table.
    """
    buckets = {}
    for row in rows:
        impressions = row.get("impressions", 0) or 0
        position = row.get("position", 0) or 0
        if impressions < min_impressions or not 0.5 <= position < 10.5:
            continue
        buckets.setdefault(int(position + 0.5), []).append((row.get("clicks", 0) or 0) / impressions)
    return {
        pos: {"median_ctr": round(statistics.median(values), 4), "rows": len(values)}
        for pos, values in sorted(buckets.items()) if len(values) >= min_rows
    }


def striking_distance(rows: list, curve: dict, *, min_pos=STRIKING_MIN_POS, max_pos=STRIKING_MAX_POS,
                      min_impressions=STRIKING_MIN_IMPRESSIONS, limit=DEFAULT_LIMIT) -> dict:
    hits = [r for r in rows if min_pos <= (r.get("position") or 0) <= max_pos
            and (r.get("impressions") or 0) >= min_impressions]
    hits.sort(key=lambda r: (-r["impressions"], r["query"]))
    target = curve.get(3)
    items = []
    for row in hits[:limit]:
        item = dict(row)
        if target:
            item["upside_clicks_at_position_3"] = max(0, round(row["impressions"] * target["median_ctr"] - row["clicks"]))
        else:
            item["upside_clicks_at_position_3"] = "cannot compute"
        items.append(item)
    return {
        "criteria": f"average position {min_pos:g}-{max_pos:g}, at least {min_impressions} impressions",
        "upside_basis": (f"this property's median CTR at position 3 ({target['median_ctr']:.1%}, {target['rows']} rows)"
                         if target else "cannot compute: fewer than "
                         f"{CURVE_MIN_ROWS} qualifying rows at position 3"),
        "count": len(hits),
        "items": items,
    }


def low_ctr(rows: list, curve: dict, *, max_pos=LOW_CTR_MAX_POS, ratio=LOW_CTR_RATIO,
            min_impressions=LOW_CTR_MIN_IMPRESSIONS, limit=DEFAULT_LIMIT) -> dict:
    hits, skipped = [], 0
    for row in rows:
        position = row.get("position") or 0
        impressions = row.get("impressions") or 0
        if not 0.5 <= position <= max_pos or impressions < min_impressions:
            continue
        bench = curve.get(int(position + 0.5))
        if not bench:
            skipped += 1
            continue
        expected = bench["median_ctr"]
        if expected > 0 and row["ctr"] < ratio * expected:
            item = dict(row)
            item["expected_ctr"] = expected
            item["clicks_below_median"] = round(impressions * expected - row["clicks"])
            hits.append(item)
    hits.sort(key=lambda r: (-r["clicks_below_median"], r["query"]))
    return {
        "criteria": (f"position <= {max_pos:g}, at least {min_impressions} impressions, CTR below "
                     f"{ratio:.0%} of this property's median CTR at the same rounded position"),
        "benchmark": {str(k): v for k, v in curve.items()},
        "rows_without_benchmark": skipped,
        "count": len(hits),
        "items": hits[:limit],
    }


def cannibalization(rows: list, *, min_impressions=CANNIBAL_MIN_IMPRESSIONS, min_share=CANNIBAL_MIN_SHARE,
                    limit=DEFAULT_LIMIT) -> dict:
    by_query = {}
    for row in rows:
        by_query.setdefault(row["query"].lower(), []).append(row)
    hits = []
    for query_rows in by_query.values():
        total = sum(r["impressions"] for r in query_rows)
        if total < min_impressions or len(query_rows) < 2:
            continue
        ranked = sorted(query_rows, key=lambda r: -r["impressions"])
        competing = [r for r in ranked if r["impressions"] / total >= min_share]
        if len(competing) < 2:
            continue
        hits.append({
            "query": ranked[0]["query"],
            "impressions": total,
            "clicks": sum(r["clicks"] for r in query_rows),
            "leader": ranked[0]["page"],
            "pages": [{"page": r["page"], "impressions": r["impressions"], "clicks": r["clicks"],
                       "share": round(r["impressions"] / total, 3), "position": r["position"]} for r in competing],
        })
    hits.sort(key=lambda h: (-h["impressions"], h["query"]))
    return {
        "criteria": f"at least {min_impressions} impressions, a second URL with at least {min_share:.0%} of them",
        "count": len(hits),
        "items": hits[:limit],
    }


def page_clicks(block) -> dict:
    """{page_key: {"page", "clicks", "impressions"}} for one page-dimension window."""
    out = {}
    for row in _rows(block):
        page = str(row.get("page", "")).strip()
        if not page:
            continue
        slot = out.setdefault(page_key(page), {"page": page, "clicks": 0, "impressions": 0})
        slot["clicks"] += row.get("clicks", 0) or 0
        slot["impressions"] += row.get("impressions", 0) or 0
    return out


def decay(pages: dict, *, min_clicks=DECAY_MIN_CLICKS, min_drop=DECAY_MIN_DROP, limit=DEFAULT_LIMIT) -> dict:
    """Pages whose clicks fell in the latest window AND the one before it.

    current <= previous * (1 - min_drop), previous < before_previous, and
    previous >= min_clicks. One falling window is noise; two in a row is a trend.
    "seasonal" is set when the same two windows a year earlier also fell by
    min_drop; it is "cannot compute" when last year had no clicks for the page.
    """
    names = ("current", "previous", "before_previous")
    if not all(name in pages for name in names):
        return {"status": "not measured", "reason": "page windows were not fetched", "count": 0, "items": []}
    cur, prev, before = (page_clicks(pages[n]) for n in names)
    ly_cur = page_clicks(pages["current_last_year"]) if "current_last_year" in pages else None
    ly_prev = page_clicks(pages["previous_last_year"]) if "previous_last_year" in pages else None
    hits = []
    for key, p in prev.items():
        p_clicks = p["clicks"]
        c_clicks = cur.get(key, {}).get("clicks", 0)
        b_clicks = before.get(key, {}).get("clicks", 0)
        if p_clicks < min_clicks or c_clicks > p_clicks * (1 - min_drop) or not p_clicks < b_clicks:
            continue
        seasonal = "cannot compute"
        if ly_cur is not None and ly_prev is not None:
            ly_p = ly_prev.get(key, {}).get("clicks", 0)
            ly_c = ly_cur.get(key, {}).get("clicks", 0)
            if ly_p > 0:
                seasonal = ly_c <= ly_p * (1 - min_drop)
        hits.append({
            "page": p["page"],
            "clicks": {"before_previous": b_clicks, "previous": p_clicks, "current": c_clicks},
            "change_latest": round((c_clicks - p_clicks) / p_clicks, 3),
            "clicks_lost": p_clicks - c_clicks,
            "seasonal": seasonal,
        })
    hits.sort(key=lambda h: (-h["clicks_lost"], h["page"]))
    return {
        "criteria": (f"at least {min_clicks} clicks in the previous window, clicks down at least {min_drop:.0%} "
                     "in the latest window, and down in the previous window too"),
        "count": len(hits),
        "items": hits[:limit],
    }


_PAGE_COLUMNS = ("top pages", "page", "pages", "url", "landing page")


def _number(value) -> float:
    text = str(value if value is not None else "").strip().replace(",", "")
    try:
        return float(text) if text else 0.0
    except ValueError as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def load_page_traffic(path: str) -> dict:
    """Page clicks and impressions from any of the shapes this repo produces.

    Accepted: this script's --json output ("pages"), its --save-rows file
    (pages.current), gsc_query.py --dimension page --json ("rows"), and the
    Pages CSV that the Search Console Performance report exports ("Top pages",
    "Clicks", "Impressions"). Returns {"source", "window", "pages": [...],
    "total_clicks", "total_impressions"}. Raises ValueError for anything else,
    so a wrong file fails the run instead of silently joining nothing.
    """
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            fields = {name.strip().lower(): name for name in (reader.fieldnames or [])}
            page_col = next((fields[c] for c in _PAGE_COLUMNS if c in fields), None)
            if not page_col or "clicks" not in fields:
                raise ValueError(f"{path}: expected a Search Console Pages export with a page column and Clicks "
                                 f"(found: {', '.join(reader.fieldnames or []) or 'no header'})")
            rows = [{"page": r[page_col], "clicks": round(_number(r.get(fields["clicks"]))),
                     "impressions": round(_number(r.get(fields.get("impressions", ""), 0)))}
                    for r in reader if (r.get(page_col) or "").strip()]
        source, window_bounds = "Search Console Pages export (CSV)", None
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: not a JSON object")
        windows = data.get("windows") or {}
        if isinstance(data.get("pages"), list):
            rows, source = data["pages"], "gsc_insights.py"
        elif isinstance(data.get("pages"), dict) and "current" in data["pages"]:
            rows, source = _rows(data["pages"]["current"]), "gsc_insights.py --save-rows"
        elif isinstance(data.get("rows"), list) and "page" in (data.get("dimensions") or []):
            rows, source = data["rows"], "gsc_query.py"
            windows = {"current": [data.get("start_date"), data.get("end_date")]}
        else:
            raise ValueError(f"{path}: no page rows (expected gsc_insights.py or gsc_query.py --dimension page output)")
        window_bounds = windows.get("current")
    merged = page_clicks(rows)
    pages = sorted(merged.values(), key=lambda v: -v["clicks"])
    return {
        "source": source,
        "window": window_bounds,
        "pages": pages,
        "total_clicks": sum(p["clicks"] for p in pages),
        "total_impressions": sum(p["impressions"] for p in pages),
    }


def load_serve_map(path: str) -> list:
    """[(query, intended_url)] from a CSV with columns query,url (header optional)."""
    pairs = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if len(row) < 2 or not row[0].strip():
                continue
            query, url = row[0].strip(), row[1].strip()
            if query.lower() in ("query", "keyword") and not url.lower().startswith("http"):
                continue  # header
            pairs.append((query, url))
    return pairs


def serve_map(rows: list, pairs: list) -> dict:
    by_query = {}
    for row in rows:
        by_query.setdefault(row["query"].lower(), []).append(row)
    items = []
    for query, intended in pairs:
        candidates = sorted(by_query.get(query.lower(), []), key=lambda r: -r["impressions"])
        if not candidates:
            items.append({"query": query, "intended": intended, "served": None, "status": "no data",
                          "note": "No impressions for this exact query in the window."})
            continue
        served = candidates[0]
        intended_row = next((r for r in candidates if page_key(r["page"]) == page_key(intended)), None)
        status = "match" if page_key(served["page"]) == page_key(intended) else "mismatch"
        items.append({
            "query": query,
            "intended": intended,
            "served": served["page"],
            "status": status,
            "served_impressions": served["impressions"],
            "served_position": served["position"],
            "intended_impressions": intended_row["impressions"] if intended_row else 0,
            "intended_position": intended_row["position"] if intended_row else None,
        })
    order = {"mismatch": 0, "no data": 1, "match": 2}
    items.sort(key=lambda i: (order[i["status"]], -(i.get("served_impressions") or 0)))
    return {
        "count": sum(1 for i in items if i["status"] == "mismatch"),
        "no_data": sum(1 for i in items if i["status"] == "no data"),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Findings (the report contract: references/procedures/02-full-site-audit.md)
# ---------------------------------------------------------------------------

def _examples(items: list, fmt, n: int = 3) -> str:
    return "; ".join(fmt(i) for i in items[:n])


def build_issues(results: dict, window_text: str) -> list:
    """One finding per analysis that found something, in the repo's finding shape."""
    issues = []
    sd = results.get("striking_distance")
    if sd and sd["count"]:
        issues.append({
            "code": "striking_distance", "severity": "medium", "kind": "opportunity", "lane": "Auto",
            "finding": f"{sd['count']} queries rank at average position 8-15 with real impressions ({window_text}).",
            "evidence": "Top by impressions: " + _examples(sd["items"], lambda i: (
                f"'{i['query']}' at {i['position']} on {i['page']} ({i['impressions']:,} impressions)")),
            "impact": ("Page two earns almost no clicks. Moving to position 3 at this property's own position-3 CTR "
                       f"is worth the upside_clicks_at_position_3 figure per query; basis: {sd['upside_basis']}."),
            "fix": ("For each query, check the ranking page's title, H1 and first paragraph for the query's words; "
                    "add the missing one, then add one internal link with the query as anchor from a related page."),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the queries are already in the title, H1 and opening paragraph and still sit at 8-15 after four weeks.",
            "leading_indicator": "Average position for each query in Search Console, re-checked four weeks after the change.",
            "urls": [i["page"] for i in sd["items"]],
        })
    lc = results.get("low_ctr")
    if lc and lc["count"]:
        issues.append({
            "code": "low_ctr", "severity": "medium", "kind": "opportunity", "lane": "Auto",
            "finding": f"{lc['count']} queries earn less than half this property's usual CTR for their position ({window_text}).",
            "evidence": "Largest gaps: " + _examples(lc["items"], lambda i: (
                f"'{i['query']}' at {i['position']}: {i['ctr']:.1%} vs {i['expected_ctr']:.1%} median")),
            "impact": "The snippet loses the click at a rank already earned; clicks_below_median counts the shortfall per query against this property's own median.",
            "fix": ("Rewrite the title and meta description of each page to lead with the query's words and a reason to click. "
                    "Where a SERP feature (video, AI Overview, map pack) sits above the result, note it instead of rewriting."),
            "confidence": "Likely",
            "falsifiability": "Wrong if CTR stays below half the median four weeks after new titles ship, which points to a SERP feature rather than the snippet.",
            "leading_indicator": "CTR for each query at a stable position, re-exported four weeks after the rewrite.",
            "urls": [i["page"] for i in lc["items"]],
        })
    cn = results.get("cannibalization")
    if cn and cn["count"]:
        issues.append({
            "code": "cannibalization", "severity": "medium", "kind": "defect", "lane": "Assisted",
            "finding": f"{cn['count']} queries split their impressions across two or more of the site's URLs ({window_text}).",
            "evidence": "Largest: " + _examples(cn["items"], lambda i: (
                f"'{i['query']}' across {len(i['pages'])} URLs, leader {i['leader']}")),
            "impact": "Two pages answering one query split links and relevance; Google rotates between them and neither holds the position.",
            "fix": ("Per query, pick the page that should rank. Merge the other into it with a 301, or re-target the other page "
                    "at a different query and link it to the winner. Redirects are high-risk: confirm before shipping."),
            "confidence": "Likely",
            "falsifiability": "Wrong if the pages serve different intents that Google shows for different searchers (for example a product page and a guide).",
            "leading_indicator": "Share of the query's impressions held by the chosen page, four weeks after the change.",
            "urls": [p["page"] for i in cn["items"] for p in i["pages"]],
        })
    dc = results.get("decay")
    if dc and dc.get("count"):
        trend = [i for i in dc["items"] if i["seasonal"] is not True]
        issues.append({
            # medium, not high: "high" reads as critical in the report and trips --fail-on critical,
            # and a display-only check must never fail a build on its own.
            "code": "decay", "severity": "medium" if trend else "low", "kind": "defect", "lane": "Assisted",
            "finding": (f"{dc['count']} pages lost clicks in two consecutive windows"
                        + (f"; {dc['count'] - len(trend)} of them fell the same way last year (seasonal)." if len(trend) < dc["count"] else ".")),
            "evidence": "Largest losses: " + _examples(dc["items"], lambda i: (
                f"{i['page']} {i['clicks']['before_previous']} -> {i['clicks']['previous']} -> {i['clicks']['current']} clicks")),
            "impact": "A page falling two windows in a row is losing rankings or demand, not noise; refreshing it early recovers more than rewriting it after it drops out.",
            "fix": ("Open each non-seasonal page's queries (gsc_query.py --query) for the lost windows, find which queries fell, "
                    "compare the page with the three pages now outranking it, and refresh the stale facts and sections."),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the loss is a tracking change (a redirect, a canonical move) rather than a ranking loss: check the page's own impressions and the destination URL first.",
            "leading_indicator": "Weekly clicks of each refreshed page for six weeks after the refresh.",
            "urls": [i["page"] for i in dc["items"]],
        })
    sm = results.get("serve_map")
    if sm and sm["count"]:
        issues.append({
            "code": "serve_mismatch", "severity": "medium", "kind": "defect", "lane": "Assisted",
            "finding": f"For {sm['count']} target queries Google shows a different page from the one intended ({window_text}).",
            "evidence": _examples([i for i in sm["items"] if i["status"] == "mismatch"], lambda i: (
                f"'{i['query']}': intended {i['intended']}, served {i['served']}")),
            "impact": "The page built for the query is not the one ranking, so work on it does not move the query.",
            "fix": ("Per query, either strengthen the intended page (the query in its title and H1, internal links to it with the query "
                    "as anchor) or accept the served page and update the keyword map."),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the served page answers the query better; then the map, not the site, is wrong.",
            "leading_indicator": "Which page holds the most impressions for each query, re-checked four weeks later.",
            "urls": [i["served"] for i in sm["items"] if i["status"] == "mismatch"],
        })
    return issues


def analyse(dataset: dict, selected: set, pairs=None, opts=None) -> dict:
    opts = opts or {}
    limit = opts.get("limit", DEFAULT_LIMIT)
    qp_block = dataset.get("query_page") or {}
    rows = _merge_query_page(_rows(qp_block))
    curve = ctr_curve(rows)
    results = {}
    if "striking_distance" in selected:
        results["striking_distance"] = striking_distance(
            rows, curve, min_impressions=opts.get("min_impressions", STRIKING_MIN_IMPRESSIONS), limit=limit)
    if "low_ctr" in selected:
        results["low_ctr"] = low_ctr(rows, curve, limit=limit)
    if "cannibalization" in selected:
        results["cannibalization"] = cannibalization(rows, limit=limit)
    if "decay" in selected:
        results["decay"] = decay(dataset.get("pages") or {}, limit=limit)
    if "serve_map" in selected:
        results["serve_map"] = serve_map(rows, pairs or [])

    windows = dataset.get("windows") or {}
    cur = windows.get("current") or ["?", "?"]
    window_text = f"{cur[0]} to {cur[1]}"
    truncated = [name for name, block in [("query_page", qp_block), *((f"pages.{k}", v) for k, v in (dataset.get("pages") or {}).items())]
                 if isinstance(block, dict) and block.get("truncated")]
    pages_now = page_clicks((dataset.get("pages") or {}).get("current")) if dataset.get("pages") else {}
    out = {
        "site_url": dataset.get("site_url"),
        "windows": windows,
        "query_page_rows": len(rows),
        "truncated": truncated,
        "limits": LIMITS + ([f"Row cap reached for {', '.join(truncated)}: results cover the top rows only."] if truncated else []),
        "ctr_curve": {str(k): v for k, v in curve.items()},
        **results,
        "issues": build_issues(results, window_text),
    }
    if pages_now:
        # The page totals generate_report.py --gsc-pages joins to findings.
        out["pages"] = [{"page": v["page"], "clicks": v["clicks"], "impressions": v["impressions"]}
                        for v in sorted(pages_now.values(), key=lambda v: -v["clicks"])]
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_human(result: dict) -> None:
    print(f"Search Console insights — {result.get('site_url') or '(replay)'}")
    cur = (result.get("windows") or {}).get("current")
    if cur:
        print(f"Window: {cur[0]} to {cur[1]}   query x page rows: {result['query_page_rows']:,}")
    if result.get("truncated"):
        print(f"⚠️  Row cap reached for {', '.join(result['truncated'])}; results cover the top rows only.")
    print("=" * 78)

    sd = result.get("striking_distance")
    if sd:
        print(f"\nStriking distance ({sd['criteria']}): {sd['count']}")
        print(f"  upside basis: {sd['upside_basis']}")
        for i in sd["items"][:15]:
            print(f"  {i['position']:>5}  {i['impressions']:>7,} impr  +{i['upside_clicks_at_position_3']} clicks  "
                  f"{i['query'][:40]!r}  {i['page']}")
    lc = result.get("low_ctr")
    if lc:
        print(f"\nLow CTR ({lc['criteria']}): {lc['count']}")
        if not lc["benchmark"]:
            print("  cannot compute: no position bucket has enough rows for a median")
        for i in lc["items"][:15]:
            print(f"  {i['position']:>5}  {i['ctr']:.1%} vs {i['expected_ctr']:.1%}  -{i['clicks_below_median']} clicks  "
                  f"{i['query'][:40]!r}  {i['page']}")
    cn = result.get("cannibalization")
    if cn:
        print(f"\nCannibalisation ({cn['criteria']}): {cn['count']}")
        for i in cn["items"][:15]:
            split = ", ".join(f"{p['page']} {p['share']:.0%}" for p in i["pages"])
            print(f"  {i['impressions']:>7,} impr  {i['query'][:40]!r}  {split}")
    dc = result.get("decay")
    if dc:
        if dc.get("status") == "not measured":
            print(f"\nDecay: not measured — {dc['reason']}")
        else:
            print(f"\nDecay ({dc['criteria']}): {dc['count']}")
            for i in dc["items"][:15]:
                c = i["clicks"]
                tag = "seasonal" if i["seasonal"] is True else "trend" if i["seasonal"] is False else "no last-year data"
                print(f"  {c['before_previous']:>6} -> {c['previous']:>6} -> {c['current']:>6}  [{tag}]  {i['page']}")
    sm = result.get("serve_map")
    if sm:
        print(f"\nServe map: {sm['count']} mismatches, {sm['no_data']} queries without data")
        for i in sm["items"][:25]:
            print(f"  {i['status']:<9} {i['query'][:40]!r}  intended {i['intended']}  served {i['served'] or '-'}")
    print()
    for line in result.get("limits", []):
        print(f"Note: {line}")


ANALYSES = ("striking_distance", "low_ctr", "cannibalization", "decay", "serve_map")


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Console opportunity analysis (Tier 1 — OAuth2)")
    parser.add_argument("site_url", nargs="?", help='GSC property, e.g. "https://example.com/" or "sc-domain:example.com"')
    parser.add_argument("--days", type=int, default=28, help="Window length in days (default: 28)")
    parser.add_argument("--end-date", help="Last day of the current window (YYYY-MM-DD). Default: 3 days ago")
    parser.add_argument("--striking-distance", action="store_true", help="Queries at average position 8-15")
    parser.add_argument("--low-ctr", action="store_true", help="CTR below half the property's own median at that position")
    parser.add_argument("--cannibalization", action="store_true", help="Queries split across two or more URLs")
    parser.add_argument("--decay", action="store_true", help="Pages down in two consecutive windows (fetches 5 page windows)")
    parser.add_argument("--serve-map", metavar="CSV", help="CSV of query,intended_url: which page Google actually shows")
    parser.add_argument("--all", action="store_true", help="Run every analysis (--serve-map still needs its CSV)")
    parser.add_argument("--min-impressions", type=int, default=STRIKING_MIN_IMPRESSIONS,
                        help=f"Striking-distance impression floor (default: {STRIKING_MIN_IMPRESSIONS}); lower it for small sites")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Items listed per analysis (default: {DEFAULT_LIMIT})")
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS, help=f"Row cap per request window (default: {DEFAULT_MAX_ROWS:,})")
    parser.add_argument("--save-rows", metavar="PATH", help="Also write the fetched rows to PATH for --replay")
    parser.add_argument("--replay", metavar="PATH", help="Analyse rows saved by --save-rows instead of calling the API")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    selected = {name for name in ANALYSES if getattr(args, name, None)}
    if args.all:
        selected |= set(ANALYSES) - {"serve_map"}
    if args.serve_map:
        selected.add("serve_map")
    if not selected:
        parser.error("choose an analysis (--striking-distance, --low-ctr, --cannibalization, --decay, --serve-map) or --all")
    if not args.replay and not args.site_url:
        parser.error("site_url is required unless --replay is given")
    if args.days < 1 or args.max_rows < 1 or args.limit < 1:
        parser.error("--days, --max-rows and --limit must be positive")

    pairs = None
    if args.serve_map:
        try:
            pairs = load_serve_map(args.serve_map)
        except OSError as exc:
            parser.error(f"--serve-map: cannot read {args.serve_map}: {exc}")
        if not pairs:
            parser.error(f"--serve-map: {args.serve_map} has no query,url rows")

    if args.replay:
        try:
            with open(args.replay, encoding="utf-8") as fh:
                dataset = json.load(fh)
        except (OSError, ValueError) as exc:
            parser.error(f"--replay: cannot read {args.replay}: {exc}")
        if not isinstance(dataset, dict) or "query_page" not in dataset:
            parser.error(f"--replay: {args.replay} was not written by --save-rows")
        if "decay" in selected and "previous" not in (dataset.get("pages") or {}):
            print("Note: the replay file has no page windows; decay is reported as not measured.", file=sys.stderr)
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import gsc_query  # credential handling lives there; imported late so --replay needs no Google libraries

        end = date.fromisoformat(args.end_date) if args.end_date else date.today() - timedelta(days=3)
        service = gsc_query._build_service(gsc_query._load_credentials())
        try:
            dataset = fetch_dataset(service, args.site_url, end, args.days,
                                    history="decay" in selected, max_rows=args.max_rows)
        except RuntimeError as exc:
            print(json.dumps({"error": str(exc)}) if args.json else f"Error: {exc}")
            return 1
        if args.save_rows:
            with open(args.save_rows, "w", encoding="utf-8") as fh:
                json.dump(dataset, fh)

    result = analyse(dataset, selected, pairs, {"limit": args.limit, "min_impressions": args.min_impressions})
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
