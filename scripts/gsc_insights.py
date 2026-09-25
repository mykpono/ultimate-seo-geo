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
  --human-basis        blended vs human-only impressions, CTR and position, now and
                       against the previous window, with the queries and pages that
                       machine traffic (rank trackers, scrapers, agents) inflates

Every analysis reads human queries only. Queries whose text is machine-shaped
(search operators, URLs, quoted-phrase templates) or whose clicks are impossible
for people at that volume and position are set aside, and so are 12+ word
agent-style queries; --include-machine turns this off.

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
import math
import os
import re
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

# Machine-query classifier (human_basis). Calibrated on 28,768 Improvado query rows
# (18 Aug-15 Sep 2026): every rule's rows together earned 8 clicks on 1.19M impressions.
HUMAN_CTR_FLOOR = ((3.0, 0.002), (10.0, 0.001), (20.0, 0.0005))  # (max position, lowest plausible human CTR)
IMPOSSIBLE_MIN_IMPRESSIONS = 500
IMPOSSIBLE_P = 1e-6            # Poisson P(clicks <= observed) under the floor
AGENT_MIN_WORDS = 12

LIMITS = [
    "Search Console omits anonymised queries: query rows do not sum to page totals.",
    "Average position is impression-weighted over the window; a page ranking 3 on some days and 20 on others averages near 11.",
    "CTR benchmarks are this property's own medians per rounded position, from rows with enough impressions; they are not industry figures.",
    "Search Console has no user agent: machine queries are inferred from query text and from clicks too few for people at that volume and position (see human_basis.criteria).",
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


def fetch_dataset(service, site_url: str, end: date, days: int, *, history: bool, max_rows: int,
                  previous_queries: bool = False) -> dict:
    """Everything the analyses read, in the shape --save-rows writes and --replay reads.

    Always: query x page and page totals for the current window (page totals are
    what generate_report.py --gsc-pages joins to findings). With history (for
    --decay): page totals for the two windows before it and for the current and
    previous windows a year earlier — seven requests in all. With previous_queries
    (for --human-basis): query x page for the window before, one request more.
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
    if previous_queries:
        previous = window(end, days, 1)
        dataset["windows"]["previous"] = [d.isoformat() for d in previous]
        dataset["query_page_previous"] = fetch_rows(service, site_url, previous, ["query", "page"], max_rows)
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


_OPERATOR = re.compile(r"(^|\s)-?(site|inurl|intitle|intext|allinurl|allintitle|cache|related|filetype|ext|before|after):\S", re.I)
_URL = re.compile(r"https?://|www\.|\b[\w-]+\.(com|io|net|org|co)/\S", re.I)
_QUOTED = re.compile(r'"[^"]+"')
_SCRAPER_SYNTAX = re.compile(r"^[%|&*@]|\s\|\s|\sOR\s")


def human_ctr_floor(position: float):
    for max_pos, floor in HUMAN_CTR_FLOOR:
        if position <= max_pos:
            return floor
    return None


def _poisson_cdf(clicks: int, expected: float) -> float:
    """P(X <= clicks) for X ~ Poisson(expected), in log space so large expectations do not underflow wrongly."""
    if expected <= 0:
        return 1.0
    log_term = -expected
    total = math.exp(log_term)
    for k in range(1, int(clicks) + 1):
        log_term += math.log(expected) - math.log(k)
        total += math.exp(log_term)
    return min(1.0, total)


def classify_query(query: str, clicks: int, impressions: int, position: float) -> tuple:
    """("human" | "machine" | "agent_like", [reason codes]) for one query's totals.

    machine, from the text: search operators, URLs, quoted-phrase templates
    ("<brand>" data strategy, two or more quoted phrases), scraper syntax (a
    leading %, " | ", " OR "). machine, from behaviour: so many impressions on
    pages one and two with so few clicks that people cannot produce it, even at
    a floor CTR well below AI Overview citation rates (Poisson P < 1e-6).
    agent_like: 12+ words, the shape of agent and AI Mode fan-out queries.
    """
    reasons = []
    text = str(query or "")
    if _OPERATOR.search(text):
        reasons.append("search_operator")
    if _URL.search(text):
        reasons.append("url_in_query")
    quotes = _QUOTED.findall(text)
    if len(quotes) >= 2 or (quotes and _QUOTED.sub(" ", text).strip()):
        reasons.append("quoted_template")
    if _SCRAPER_SYNTAX.search(text):
        reasons.append("scraper_syntax")
    floor = human_ctr_floor(position or 0)
    if floor and impressions >= IMPOSSIBLE_MIN_IMPRESSIONS and _poisson_cdf(clicks, floor * impressions) < IMPOSSIBLE_P:
        reasons.append("impossible_ctr")
    if reasons:
        return "machine", reasons
    if len(text.split()) >= AGENT_MIN_WORDS:
        return "agent_like", ["long_query"]
    return "human", []


def classify_queries(rows: list) -> dict:
    """{query.lower(): {"label", "reasons", "clicks", "impressions", "position"}} over query x page rows."""
    totals = {}
    for row in rows:
        key = str(row.get("query", "")).lower()
        t = totals.setdefault(key, {"query": row.get("query", ""), "clicks": 0, "impressions": 0, "_pos": 0.0})
        impressions = row.get("impressions", 0) or 0
        t["clicks"] += row.get("clicks", 0) or 0
        t["impressions"] += impressions
        t["_pos"] += (row.get("position", 0) or 0) * impressions
    out = {}
    for key, t in totals.items():
        position = round(t["_pos"] / t["impressions"], 2) if t["impressions"] else 0.0
        label, reasons = classify_query(t["query"], t["clicks"], t["impressions"], position)
        out[key] = {"query": t["query"], "label": label, "reasons": reasons,
                    "clicks": t["clicks"], "impressions": t["impressions"], "position": position}
    return out


def human_rows(rows: list, labels: dict) -> list:
    return [r for r in rows if labels.get(str(r.get("query", "")).lower(), {}).get("label", "human") == "human"]


def _basis(rows: list) -> dict:
    impressions = sum(r.get("impressions", 0) or 0 for r in rows)
    clicks = sum(r.get("clicks", 0) or 0 for r in rows)
    weighted = sum((r.get("position", 0) or 0) * (r.get("impressions", 0) or 0) for r in rows)
    return {"impressions": impressions, "clicks": clicks,
            "ctr": round(clicks / impressions, 5) if impressions else None,
            "position": round(weighted / impressions, 2) if impressions else None}


def _change(before: dict, after: dict) -> dict:
    out = {"clicks": after["clicks"] - before["clicks"]}
    out["impressions_pct"] = (round((after["impressions"] - before["impressions"]) / before["impressions"], 4)
                              if before["impressions"] else None)
    out["position"] = (round(after["position"] - before["position"], 2)
                       if before["position"] is not None and after["position"] is not None else None)
    out["ctr"] = (round(after["ctr"] - before["ctr"], 5)
                  if before["ctr"] is not None and after["ctr"] is not None else None)
    return out


def _split(rows: list, labels: dict) -> dict:
    groups = {"human": [], "machine": [], "agent_like": []}
    for r in rows:
        groups[labels.get(str(r.get("query", "")).lower(), {}).get("label", "human")].append(r)
    return {"blended": _basis(rows), "human": _basis(groups["human"]),
            "machine": _basis(groups["machine"]), "agent_like": _basis(groups["agent_like"])}


def human_basis(rows: list, labels: dict, previous_rows=None, previous_labels=None, *, limit=DEFAULT_LIMIT) -> dict:
    """Blended vs human-only Search Console figures, and what the difference is made of."""
    current = _split(rows, labels)
    blended = current["blended"]["impressions"] or 0
    excluded = current["machine"]["impressions"] + current["agent_like"]["impressions"]
    reasons = {}
    for info in labels.values():
        for code in info["reasons"]:
            slot = reasons.setdefault(code, {"queries": 0, "impressions": 0, "clicks": 0})
            slot["queries"] += 1
            slot["impressions"] += info["impressions"]
            slot["clicks"] += info["clicks"]
    top = sorted((i for i in labels.values() if i["label"] != "human"), key=lambda i: (-i["impressions"], i["query"]))
    pages = {}
    for r in rows:
        page = pages.setdefault(page_key(r.get("page", "")), {"page": r.get("page", ""), "impressions": 0, "non_human_impressions": 0, "clicks": 0})
        imp = r.get("impressions", 0) or 0
        page["impressions"] += imp
        page["clicks"] += r.get("clicks", 0) or 0
        if labels.get(str(r.get("query", "")).lower(), {}).get("label", "human") != "human":
            page["non_human_impressions"] += imp
    dominated = [dict(p, non_human_share=round(p["non_human_impressions"] / p["impressions"], 3))
                 for p in pages.values() if p["impressions"] and p["non_human_impressions"] / p["impressions"] >= 0.5]
    dominated.sort(key=lambda p: (-p["non_human_impressions"], p["page"]))
    out = {
        "criteria": (f"machine: search operators, URLs, quoted-phrase templates, scraper syntax, or clicks below a "
                     f"human CTR floor ({', '.join(f'{f:.2%} to position {p:g}' for p, f in HUMAN_CTR_FLOOR)}) at "
                     f"{IMPOSSIBLE_MIN_IMPRESSIONS}+ impressions with Poisson P < {IMPOSSIBLE_P:g}; "
                     f"agent_like: {AGENT_MIN_WORDS}+ words. The human basis excludes both."),
        "current": current,
        "non_human_share_of_impressions": round(excluded / blended, 4) if blended else None,
        "reasons": reasons,
        "count": len(top),
        "items": [{k: i[k] for k in ("query", "label", "reasons", "impressions", "clicks", "position")} for i in top[:limit]],
        "pages_mostly_non_human": dominated[:limit],
    }
    if previous_rows is None:
        out["change"] = {"status": "not measured", "reason": "no previous-window query rows (run without --replay, or re-save rows)"}
        return out
    previous = _split(previous_rows, previous_labels if previous_labels is not None else classify_queries(previous_rows))
    change = {"blended": _change(previous["blended"], current["blended"]),
              "human": _change(previous["human"], current["human"])}
    bp, hp = change["blended"]["position"], change["human"]["position"]
    if bp and hp is not None and bp < 0:
        change["position_gain_from_non_human"] = round(max(0.0, (bp - hp) / bp), 3)
    out.update(previous=previous, change=change)
    return out


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
    hb = results.get("human_basis")
    share = (hb or {}).get("non_human_share_of_impressions") or 0
    gain = ((hb or {}).get("change") or {}).get("position_gain_from_non_human") or 0
    if hb and (share >= 0.10 or gain >= 0.25):
        cur = hb["current"]
        change = hb.get("change") or {}
        trend = ""
        if "blended" in change:
            trend = (f" Position moved {change['blended']['position']:+.2f} blended but {change['human']['position']:+.2f} "
                     f"on human queries: {gain:.0%} of the apparent gain is a change in who searches, not in rankings.")
        issues.append({
            "code": "non_human_queries", "severity": "medium", "kind": "defect", "lane": "Decision",
            "finding": (f"{share:.0%} of Search Console impressions come from machine or agent-like queries "
                        f"({window_text}); site-level position, CTR and impressions overstate what people see.{trend}"),
            "evidence": ("Largest: " + _examples(hb["items"], lambda i: (
                f"'{i['query']}' {i['impressions']:,} impressions, {i['clicks']} clicks at {i['position']} ({', '.join(i['reasons'])})"))
                + f". Blended position {cur['blended']['position']}, human {cur['human']['position']}; "
                  f"blended CTR {cur['blended']['ctr']:.3%}, human {cur['human']['ctr']:.3%}."),
            "impact": ("Every site-level Search Console trend quoted from the blended numbers is off by the machine share; "
                       "a ranking 'gain' can be a rank tracker or scraper fleet arriving, and CTR can fall while people click as before."),
            "fix": ("Quote Search Console trends on the human basis (human_basis.current.human) and name the basis with the number. "
                    "For pages mostly shown to machines (pages_mostly_non_human), decide whether the topic belongs on the site; "
                    "no on-page change stops the queries."),
            "confidence": "Likely",
            "falsifiability": ("Wrong if the excluded queries earn clicks once the window fills in, or if the site's pages sit in "
                               "a SERP feature that shows but is almost never clicked; re-read the listed queries in the Performance report."),
            "leading_indicator": "Blended minus human position and the non-human impression share, re-read each window.",
            "urls": [p["page"] for p in hb["pages_mostly_non_human"]],
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
    all_rows = _merge_query_page(_rows(qp_block))
    labels = classify_queries(all_rows)
    rows = all_rows if opts.get("include_machine") else human_rows(all_rows, labels)
    curve = ctr_curve(rows)
    results = {}
    if "human_basis" in selected:
        prev_block = dataset.get("query_page_previous")
        prev_rows = _merge_query_page(_rows(prev_block)) if prev_block is not None else None
        results["human_basis"] = human_basis(all_rows, labels, prev_rows, limit=limit)
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
    truncated = [name for name, block in [("query_page", qp_block), ("query_page_previous", dataset.get("query_page_previous")),
                                          *((f"pages.{k}", v) for k, v in (dataset.get("pages") or {}).items())]
                 if isinstance(block, dict) and block.get("truncated")]
    pages_now = page_clicks((dataset.get("pages") or {}).get("current")) if dataset.get("pages") else {}
    out = {
        "site_url": dataset.get("site_url"),
        "windows": windows,
        "query_page_rows": len(all_rows),
        "queries_set_aside": (None if opts.get("include_machine") else
                              {"rows": len(all_rows) - len(rows),
                               "impressions": sum(r["impressions"] for r in all_rows) - sum(r["impressions"] for r in rows),
                               "note": "machine and agent-like queries are left out of every analysis; --include-machine keeps them"}),
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
    hb = result.get("human_basis")
    if hb:
        cur = hb["current"]
        share = hb.get("non_human_share_of_impressions")
        print(f"\nHuman basis: {share:.0%} of impressions are machine or agent-like" if share is not None else "\nHuman basis: no rows")
        for name in ("blended", "human", "machine", "agent_like"):
            b = cur[name]
            ctr = f"{b['ctr']:.3%}" if b["ctr"] is not None else "-"
            print(f"  {name:<10} {b['impressions']:>11,} impr {b['clicks']:>8,} clicks  CTR {ctr:>8}  pos {b['position'] if b['position'] is not None else '-'}")
        change = hb.get("change") or {}
        if "blended" in change:
            print(f"  vs previous window: position {change['blended']['position']:+.2f} blended, {change['human']['position']:+.2f} human"
                  + (f"  ({change['position_gain_from_non_human']:.0%} of the gain is non-human)" if "position_gain_from_non_human" in change else ""))
        elif change:
            print(f"  change: {change['status']} ({change['reason']})")
        for i in hb["items"][:15]:
            print(f"  {i['impressions']:>9,} impr {i['clicks']:>5} clicks  pos {i['position']:>5}  {i['label']:<10} {','.join(i['reasons']):<28} {i['query'][:45]!r}")
        for p in hb["pages_mostly_non_human"][:10]:
            print(f"  page {p['non_human_share']:.0%} non-human  {p['impressions']:>9,} impr  {p['page']}")
    sm = result.get("serve_map")
    if sm:
        print(f"\nServe map: {sm['count']} mismatches, {sm['no_data']} queries without data")
        for i in sm["items"][:25]:
            print(f"  {i['status']:<9} {i['query'][:40]!r}  intended {i['intended']}  served {i['served'] or '-'}")
    print()
    for line in result.get("limits", []):
        print(f"Note: {line}")


ANALYSES = ("striking_distance", "low_ctr", "cannibalization", "decay", "serve_map", "human_basis")


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
    parser.add_argument("--human-basis", action="store_true",
                        help="Blended vs human-only figures, now and vs the previous window (one more request)")
    parser.add_argument("--include-machine", action="store_true",
                        help="Keep machine and agent-like queries in every analysis (default: set aside)")
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
        parser.error("choose an analysis (--striking-distance, --low-ctr, --cannibalization, --decay, --serve-map, --human-basis) or --all")
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
            dataset = fetch_dataset(service, args.site_url, end, args.days, history="decay" in selected,
                                    max_rows=args.max_rows, previous_queries="human_basis" in selected)
        except RuntimeError as exc:
            print(json.dumps({"error": str(exc)}) if args.json else f"Error: {exc}")
            return 1
        if args.save_rows:
            with open(args.save_rows, "w", encoding="utf-8") as fh:
                json.dump(dataset, fh)

    result = analyse(dataset, selected, pairs, {"limit": args.limit, "min_impressions": args.min_impressions,
                                                "include_machine": args.include_machine})
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
