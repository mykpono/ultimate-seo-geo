#!/usr/bin/env python3
"""
Query Google Search Console Search Analytics API (Tier 1 — OAuth2).

Returns clicks, impressions, CTR, and average position grouped by query,
page, country, or device. Complements gsc_export.py (URL Inspection) with
performance data.

Credentials (any one):
  - Service account: set GOOGLE_APPLICATION_CREDENTIALS to the JSON path
  - OAuth token: set GSC_CREDENTIALS to a saved token JSON path
  - OAuth flow: run  python scripts/gsc_export.py --auth  first

Usage:
    python scripts/gsc_query.py https://example.com/ --days 28 --json
    python scripts/gsc_query.py sc-domain:example.com --top-queries 20 --json
    python scripts/gsc_query.py https://example.com/ --query "keyword" --json
    python scripts/gsc_query.py https://example.com/ --top-pages 10 --json
    python scripts/gsc_query.py https://example.com/ --dimension country --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"

TIER_UPGRADE_MSG = (
    "Tier 1 credentials required for Search Console.\n"
    "Options:\n"
    "  1. Service account: set GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json\n"
    "  2. OAuth token: run  python scripts/gsc_export.py --auth  then retry\n"
    "  3. Set GSC_CREDENTIALS=/path/to/token.json\n"
    "Run  python scripts/google_api_tier.py --check  to see current tier."
)

INSTALL_MSG = (
    "Install Google API libraries:\n"
    "  pip install google-api-python-client google-auth google-auth-httplib2\n"
    "Or: pip install -r requirements-gsc.txt"
)


def _load_credentials():
    """Load Google credentials from available sources."""
    try:
        from google.oauth2 import service_account as sa_mod
        from google.oauth2.credentials import Credentials
    except ImportError:
        print(json.dumps({"error": INSTALL_MSG}))
        sys.exit(1)

    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_path and os.path.isfile(sa_path):
        try:
            creds = sa_mod.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
            return creds
        except Exception as e:
            print(json.dumps({"error": f"Failed to load service account: {e}"}))
            sys.exit(1)

    token_path = os.environ.get("GSC_CREDENTIALS")
    if not token_path:
        default = os.path.join(REPO_ROOT, "gsc-oauth-token.json")
        if os.path.isfile(default):
            token_path = default

    if token_path and os.path.isfile(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            if creds.valid:
                return creds
        except Exception as e:
            print(json.dumps({"error": f"Failed to load OAuth token: {e}"}))
            sys.exit(1)

    print(json.dumps({"error": TIER_UPGRADE_MSG}))
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


def print_human(result: dict) -> None:
    """Print GSC query results in a human-readable table."""
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Search Console — {result['site_url']}")
    print(f"Date range: {result['start_date']} to {result['end_date']}")
    print(f"Dimensions: {', '.join(result['dimensions'])}")
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

    if args.top_pages:
        dimension = "page"
        row_limit = args.top_pages
    elif args.top_queries:
        dimension = "query"
        row_limit = args.top_queries

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
        if args.json:
            print(json.dumps({"error": raw["error"]}))
        else:
            print(f"Error: {raw['error']}")
        sys.exit(1)

    rows = format_rows(raw, [dimension])

    result = {
        "site_url": args.site_url,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "dimensions": [dimension],
        "row_count": len(rows),
        "rows": rows,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)


if __name__ == "__main__":
    main()
