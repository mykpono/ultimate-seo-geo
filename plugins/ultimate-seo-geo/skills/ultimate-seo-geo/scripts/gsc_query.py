#!/usr/bin/env python3
"""
Query Google Search Console Search Analytics API (Tier 1 — OAuth2).

Returns clicks, impressions, CTR, and average position grouped by query,
page, country, or device. Complements gsc_export.py (URL Inspection) with
performance data.

Sign in once with  python3 scripts/google_auth.py login  (a browser opens; read-only
access). A service account (GOOGLE_APPLICATION_CREDENTIALS) or a saved token
(GSC_CREDENTIALS) also works; see google_auth.py for the order.

Usage:
    python scripts/gsc_query.py https://example.com/ --days 28 --json
    python scripts/gsc_query.py sc-domain:example.com --top-queries 20 --json
    python scripts/gsc_query.py https://example.com/ --query "keyword" --json
    python scripts/gsc_query.py https://example.com/ --top-pages 10 --json
    python scripts/gsc_query.py https://example.com/ --dimension country --json
    python scripts/gsc_query.py sc-domain:example.com --top-pages 10 --keep-fragments --json

Page rows are merged by page before they are returned. Search Console reports
jump links and sitelinks as their own URLs (/guide#faq, /guide#pricing), so a
long post with a table of contents is split across many rows and any one row
undercounts the page. Rows whose URLs differ only by fragment, query string,
trailing slash or host case are summed (gsc_insights.page_key), position is
re-weighted by impressions and CTR recomputed. --keep-fragments returns the
raw rows instead.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from gsc_insights import page_key  # noqa: E402  stdlib-only; the one page-identity rule

PAGE_SUM_LIMIT = (
    "Page rows merged across fragment URLs are an upper bound for the page: when one result "
    "shows both /guide and /guide#faq, Search Console counts an impression at each URL."
)
PROPERTY_LIMIT = (
    "Figures from a domain property (sc-domain:) and a URL-prefix property never add; "
    "quote the property with every number."
)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"

INSTALL_MSG = (
    "Install the Google libraries once:\n"
    "  python3 scripts/google_auth.py setup"
)


def _load_credentials():
    """Credentials from google_auth.py: service account, GSC_CREDENTIALS, or the saved login."""
    import google_auth
    try:
        return google_auth.load_credentials(SCOPES)[0]
    except google_auth.AuthError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def _build_service(creds):
    """Build the Search Console API service client."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print(json.dumps({"error": INSTALL_MSG}))
        sys.exit(1)
    return build("searchconsole", "v1", credentials=creds)


def query_search_analytics(
    service,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    query_filter: str | None = None,
    row_limit: int = 1000,
) -> dict:
    """
    Query the GSC Search Analytics API.

    Returns raw API response dict with rows of clicks, impressions, ctr, position.
    """
    body: dict = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": min(row_limit, 25000),
    }

    if query_filter:
        body["dimensionFilterGroups"] = [{
            "filters": [{
                "dimension": "query",
                "operator": "contains",
                "expression": query_filter,
            }]
        }]

    try:
        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
        return response
    except Exception as e:
        return {"error": str(e)}


def format_rows(raw_response: dict, dimensions: list[str]) -> list[dict]:
    """Convert API response rows into flat dicts."""
    rows = raw_response.get("rows", [])
    result = []
    for row in rows:
        keys = row.get("keys", [])
        entry: dict = {}
        for i, dim in enumerate(dimensions):
            entry[dim] = keys[i] if i < len(keys) else ""
        entry["clicks"] = row.get("clicks", 0)
        entry["impressions"] = row.get("impressions", 0)
        entry["ctr"] = round(row.get("ctr", 0), 4)
        entry["position"] = round(row.get("position", 0), 1)
        result.append(entry)
    return result


def property_type(site_url: str) -> str:
    """'domain' for sc-domain: properties, 'url_prefix' otherwise."""
    return "domain" if str(site_url).strip().lower().startswith("sc-domain:") else "url_prefix"


def merge_page_rows(rows: list[dict], dimensions: list[str]) -> tuple[list[dict], dict]:
    """Sum rows whose page differs only by fragment, query, trailing slash or host case.

    Other dimensions stay part of the key, so query x page rows merge per query.
    Returns (rows, stats); a merged row carries "merged_urls" with every spelling
    it absorbed, and keeps the shortest spelling as "page".
    """
    stats = {"rows_in": len(rows), "rows_out": len(rows), "merged_rows": 0}
    if "page" not in dimensions:
        return rows, stats
    others = [d for d in dimensions if d != "page"]
    slots: dict = {}
    for row in rows:
        key = tuple(str(row.get(d, "")) for d in others) + (page_key(row.get("page", "")),)
        slot = slots.get(key)
        if slot is None:
            slot = slots[key] = {**row, "clicks": 0, "impressions": 0, "_pos": 0.0, "_urls": []}
        impressions = row.get("impressions", 0) or 0
        slot["clicks"] += row.get("clicks", 0) or 0
        slot["impressions"] += impressions
        slot["_pos"] += (row.get("position", 0) or 0) * impressions
        slot["_urls"].append(row.get("page", ""))
        if len(str(row.get("page", ""))) < len(str(slot["page"])):
            slot["page"] = row.get("page", "")
    out = []
    for slot in slots.values():
        urls = slot.pop("_urls")
        pos = slot.pop("_pos")
        impressions = slot["impressions"]
        slot["ctr"] = round(slot["clicks"] / impressions, 4) if impressions else 0.0
        slot["position"] = round(pos / impressions, 1) if impressions else 0.0
        if len(urls) > 1:
            slot["merged_urls"] = urls
        out.append(slot)
    stats["rows_out"] = len(out)
    stats["merged_rows"] = len(rows) - len(out)
    return out, stats


def print_human(result: dict) -> None:
    """Print GSC query results in a human-readable table."""
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Search Console — {result['site_url']}")
    print(f"Date range: {result['start_date']} to {result['end_date']}")
    print(f"Dimensions: {', '.join(result['dimensions'])}")
    norm = result.get("page_normalization") or {}
    if norm.get("applied"):
        print(f"Page rows merged: {norm['rows_in']} rows -> {norm['rows_out']} pages "
              f"({norm['merged_rows']} fragment/variant rows folded in)")
    print("=" * 70)

    rows = result.get("rows", [])
    if not rows:
        print("No data returned for this query.")
        return

    dims = result["dimensions"]
    header_parts = [f"{'  '.join(d.upper() for d in dims):<50}", "Clicks", "Impr", "CTR", "Pos"]
    print(f"{'  '.join(header_parts)}")
    print("-" * 70)

    for row in rows[:50]:
        dim_values = "  ".join(str(row.get(d, ""))[:25] for d in dims)
        clicks = row.get("clicks", 0)
        impressions = row.get("impressions", 0)
        ctr = row.get("ctr", 0)
        position = row.get("position", 0)
        print(f"{dim_values:<50} {clicks:>6} {impressions:>6} {ctr:>6.1%} {position:>5.1f}")

    if len(rows) > 50:
        print(f"\n... and {len(rows) - 50} more rows (use --json for full data)")

    total_clicks = sum(r.get("clicks", 0) for r in rows)
    total_impressions = sum(r.get("impressions", 0) for r in rows)
    avg_ctr = total_clicks / total_impressions if total_impressions else 0
    print(f"\nTotals: {total_clicks:,} clicks, {total_impressions:,} impressions, {avg_ctr:.1%} CTR")


def main():
    parser = argparse.ArgumentParser(
        description="Query Google Search Console Search Analytics (Tier 1 — OAuth2 required)"
    )
    parser.add_argument(
        "site_url",
        help='GSC property URL, e.g. "https://example.com/" or "sc-domain:example.com"',
    )
    parser.add_argument(
        "--days", "-d", type=int, default=28,
        help="Number of days to query (default: 28)",
    )
    parser.add_argument(
        "--start-date",
        help="Start date (YYYY-MM-DD). Overrides --days.",
    )
    parser.add_argument(
        "--end-date",
        help="End date (YYYY-MM-DD). Defaults to 3 days ago (data delay).",
    )
    parser.add_argument(
        "--query", "-q",
        help="Filter results to queries containing this string",
    )
    parser.add_argument(
        "--dimension",
        # Full set the Search Analytics API accepts. searchAppearance and hour
        # were missing, which made the documented "group by searchAppearance"
        # workflow in references/schema-types.md impossible to actually run.
        choices=["query", "page", "country", "device", "date", "searchAppearance", "hour"],
        default="query",
        help=(
            "Primary dimension to group by (default: query). "
            "'searchAppearance' lists the rich-result types a property appears as — "
            "the only way to check whether a given appearance type still returns data."
        ),
    )
    parser.add_argument(
        "--top-pages", type=int,
        help="Shortcut: top N pages by impressions (sets --dimension page, sorts by impressions)",
    )
    parser.add_argument(
        "--top-queries", type=int,
        help="Shortcut: top N queries by impressions (sets --dimension query, sorts by impressions)",
    )
    parser.add_argument(
        "--limit", type=int, default=1000,
        help="Max rows to return (default: 1000, API max: 25000)",
    )
    parser.add_argument(
        "--keep-fragments", action="store_true",
        help="Return raw page rows; do not merge /page#fragment and other spellings of one page",
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    end = date.today() - timedelta(days=3)
    if args.end_date:
        end = date.fromisoformat(args.end_date)
    start = end - timedelta(days=args.days)
    if args.start_date:
        start = date.fromisoformat(args.start_date)

    dimension = args.dimension
    row_limit = args.limit
    top_n = None

    if args.top_pages:
        dimension = "page"
        top_n = args.top_pages
    elif args.top_queries:
        dimension = "query"
        top_n = args.top_queries
    if top_n and dimension == "query":
        row_limit = top_n
    # --top-pages fetches --limit rows, merges, then keeps N: the fragment rows of a
    # top page can sit far below it in the API's click order.

    creds = _load_credentials()
    service = _build_service(creds)

    raw = query_search_analytics(
        service=service,
        site_url=args.site_url,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        dimensions=[dimension],
        query_filter=args.query,
        row_limit=row_limit,
    )

    if "error" in raw:
        import google_auth
        if google_auth.is_sign_in_error(raw["error"]):
            raw["error"] = (f"Google rejected the saved sign-in ({raw['error']}). Sign in again:\n  "
                            f"python3 {os.path.join(SCRIPT_DIR, 'google_auth.py')} login")
        if args.json:
            print(json.dumps({"error": raw["error"]}))
        else:
            print(f"Error: {raw['error']}")
        sys.exit(1)

    rows = format_rows(raw, [dimension])
    fetched = len(rows)
    limits = [PROPERTY_LIMIT]
    normalization = {"applied": False}
    if dimension == "page" and not args.keep_fragments:
        rows, stats = merge_page_rows(rows, [dimension])
        normalization = {"applied": True, **stats}
        limits.insert(0, PAGE_SUM_LIMIT)
    if top_n:
        rows = sorted(rows, key=lambda r: r.get("impressions", 0), reverse=True)[:top_n]

    result = {
        "site_url": args.site_url,
        "property_type": property_type(args.site_url),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "dimensions": [dimension],
        "row_count": len(rows),
        "truncated": fetched >= min(row_limit, 25000),
        "page_normalization": normalization,
        "limits": limits,
        "rows": rows,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)


if __name__ == "__main__":
    main()
