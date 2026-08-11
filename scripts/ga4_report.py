#!/usr/bin/env python3
"""
Query GA4 Data API for traffic, landing page, and engagement data (Tier 2 — OAuth2).

Returns sessions, users, engagement rate, bounce rate, and conversions grouped
by landing page, source/medium, or date.

Credentials (any one):
  - Service account: set GOOGLE_APPLICATION_CREDENTIALS to the JSON path
  - OAuth token: set GA4_CREDENTIALS to a saved token JSON path

Usage:
    python scripts/ga4_report.py --property 123456789 --days 28 --json
    python scripts/ga4_report.py --property 123456789 --organic-only --json
    python scripts/ga4_report.py --property 123456789 --top-landing 20 --json
    python scripts/ga4_report.py --property 123456789 --metrics sessions,users --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

TIER_UPGRADE_MSG = (
    "Tier 2 credentials required for GA4 Data API.\n"
    "Options:\n"
    "  1. Service account: set GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json\n"
    "     (service account must be added as a viewer to the GA4 property)\n"
    "  2. OAuth token: set GA4_CREDENTIALS=/path/to/token.json\n"
    "Run  python scripts/google_api_tier.py --check  to see current tier."
)

INSTALL_MSG = (
    "Install the GA4 Data API client:\n"
    "  pip install google-analytics-data google-auth"
)

VALID_METRICS = [
    "sessions", "totalUsers", "newUsers", "activeUsers",
    "screenPageViews", "engagementRate", "bounceRate",
    "averageSessionDuration", "conversions", "eventCount",
]

DEFAULT_METRICS = ["sessions", "totalUsers", "engagementRate", "bounceRate", "screenPageViews"]


def _load_ga4_client(property_id: str):
    """Build the GA4 BetaAnalyticsDataClient with available credentials."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            FilterExpression,
            Filter,
            Metric,
            RunReportRequest,
        )
    except ImportError:
        print(json.dumps({"error": INSTALL_MSG}))
        sys.exit(1)

    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_path and os.path.isfile(sa_path):
        try:
            client = BetaAnalyticsDataClient()
            return client
        except Exception as e:
            print(json.dumps({"error": f"Failed to init GA4 client with service account: {e}"}))
            sys.exit(1)

    token_path = os.environ.get("GA4_CREDENTIALS")
    if not token_path:
        default = os.path.join(REPO_ROOT, "ga4-oauth-token.json")
        if os.path.isfile(default):
            token_path = default

    if token_path and os.path.isfile(token_path):
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(
                token_path,
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            client = BetaAnalyticsDataClient(credentials=creds)
            return client
        except Exception as e:
            print(json.dumps({"error": f"Failed to load GA4 OAuth token: {e}"}))
            sys.exit(1)

    print(json.dumps({"error": TIER_UPGRADE_MSG}))
    sys.exit(1)


def run_ga4_report(
    property_id: str,
    start_date: str,
    end_date: str,
    metrics: list[str],
    dimensions: list[str],
    organic_only: bool = False,
    row_limit: int = 100,
) -> dict:
    """
    Run a GA4 Data API report and return structured results.
    """
    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            Metric,
            RunReportRequest,
        )
    except ImportError:
        return {"error": INSTALL_MSG}

    client = _load_ga4_client(property_id)
    property_path = f"properties/{property_id}"

    request_metrics = [Metric(name=m) for m in metrics]
    request_dimensions = [Dimension(name=d) for d in dimensions]

    dimension_filter = None
    if organic_only:
        dimension_filter = FilterExpression(
            filter=Filter(
                field_name="sessionDefaultChannelGroup",
                string_filter=Filter.StringFilter(
                    value="Organic Search",
                    match_type=Filter.StringFilter.MatchType.EXACT,
                ),
            )
        )

    try:
        request = RunReportRequest(
            property=property_path,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=request_metrics,
            dimensions=request_dimensions,
            dimension_filter=dimension_filter,
            limit=row_limit,
        )
        response = client.run_report(request)
    except Exception as e:
        return {"error": f"GA4 API error: {e}"}

    rows = []
    for row in response.rows:
        entry = {}
        for i, dim_value in enumerate(row.dimension_values):
            dim_name = dimensions[i] if i < len(dimensions) else f"dimension_{i}"
            entry[dim_name] = dim_value.value
        for i, metric_value in enumerate(row.metric_values):
            metric_name = metrics[i] if i < len(metrics) else f"metric_{i}"
            val = metric_value.value
            try:
                if "." in val:
                    entry[metric_name] = round(float(val), 4)
                else:
                    entry[metric_name] = int(val)
            except (ValueError, TypeError):
                entry[metric_name] = val
        rows.append(entry)

    totals = {}
    if response.totals:
        for i, metric_value in enumerate(response.totals[0].metric_values):
            metric_name = metrics[i] if i < len(metrics) else f"metric_{i}"
            val = metric_value.value
            try:
                if "." in val:
                    totals[metric_name] = round(float(val), 4)
                else:
                    totals[metric_name] = int(val)
            except (ValueError, TypeError):
                totals[metric_name] = val

    return {
        "property_id": property_id,
        "start_date": start_date,
        "end_date": end_date,
        "dimensions": dimensions,
        "metrics": metrics,
        "organic_only": organic_only,
        "row_count": len(rows),
        "rows": rows,
        "totals": totals,
    }


def print_human(result: dict) -> None:
    """Print GA4 report results in a human-readable table."""
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"GA4 Report — Property {result['property_id']}")
    print(f"Date range: {result['start_date']} to {result['end_date']}")
    if result.get("organic_only"):
        print("Filter: Organic Search only")
    print("=" * 70)

    rows = result.get("rows", [])
    if not rows:
        print("No data returned for this query.")
        return

    dims = result["dimensions"]
    metrics = result["metrics"]

    header = f"{'  '.join(d.upper() for d in dims):<40}"
    for m in metrics[:5]:
        header += f" {m:>12}"
    print(header)
    print("-" * 70)

    for row in rows[:30]:
        dim_str = "  ".join(str(row.get(d, ""))[:20] for d in dims)
        line = f"{dim_str:<40}"
        for m in metrics[:5]:
            val = row.get(m, "")
            if isinstance(val, float):
                if val < 1:
                    line += f" {val:>11.1%}"
                else:
                    line += f" {val:>12.1f}"
            else:
                line += f" {val:>12}"
        print(line)

    if len(rows) > 30:
        print(f"\n... and {len(rows) - 30} more rows (use --json for full data)")

    totals = result.get("totals", {})
    if totals:
        print(f"\nTotals:")
        for m, v in totals.items():
            if isinstance(v, float) and v < 1:
                print(f"  {m}: {v:.1%}")
            else:
                print(f"  {m}: {v:,}" if isinstance(v, int) else f"  {m}: {v}")


def main():
    parser = argparse.ArgumentParser(
        description="Query GA4 Data API for traffic and engagement data (Tier 2 — OAuth2 required)"
    )
    parser.add_argument(
        "--property", "-p", required=True,
        help="GA4 property ID (numeric, e.g. 123456789)",
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
        help="End date (YYYY-MM-DD). Defaults to yesterday.",
    )
    parser.add_argument(
        "--organic-only", action="store_true",
        help="Filter to Organic Search traffic only",
    )
    parser.add_argument(
        "--top-landing", type=int,
        help="Top N landing pages by sessions",
    )
    parser.add_argument(
        "--dimension",
        choices=["landingPage", "sessionDefaultChannelGroup", "sessionSourceMedium", "date", "country"],
        default="landingPage",
        help="Dimension to group by (default: landingPage)",
    )
    parser.add_argument(
        "--metrics", "-m",
        help=f"Comma-separated metrics (default: {','.join(DEFAULT_METRICS)}). "
             f"Available: {', '.join(VALID_METRICS)}",
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max rows to return (default: 100)",
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    end = date.today() - timedelta(days=1)
    if args.end_date:
        end = date.fromisoformat(args.end_date)
    start = end - timedelta(days=args.days)
    if args.start_date:
        start = date.fromisoformat(args.start_date)

    metrics = DEFAULT_METRICS
    if args.metrics:
        metrics = [m.strip() for m in args.metrics.split(",")]
        invalid = [m for m in metrics if m not in VALID_METRICS]
        if invalid:
            print(f"Error: invalid metrics: {', '.join(invalid)}")
            print(f"Valid metrics: {', '.join(VALID_METRICS)}")
            sys.exit(1)

    dimension = args.dimension
    row_limit = args.limit

    if args.top_landing:
        dimension = "landingPage"
        row_limit = args.top_landing

    result = run_ga4_report(
        property_id=args.property,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        metrics=metrics,
        dimensions=[dimension],
        organic_only=args.organic_only,
        row_limit=row_limit,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)


if __name__ == "__main__":
    main()
