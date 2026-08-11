#!/usr/bin/env python3
"""
Fetch historical Core Web Vitals from the Chrome UX Report (CrUX) History API.

Tier 0 — requires only a Google API key (PAGESPEED_API_KEY or GOOGLE_API_KEY).
Returns 25 collection periods (~6 months) of p75 field data per metric.

Usage:
    python scripts/crux_history.py https://example.com --json
    python scripts/crux_history.py https://example.com --metric lcp --json
    python scripts/crux_history.py --origin https://example.com --json
"""

import argparse
import json
import sys

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required: pip install requests"}))
    sys.exit(1)

import os

CRUX_HISTORY_API = "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"

METRIC_KEYS = {
    "lcp": "largest_contentful_paint",
    "inp": "interaction_to_next_paint",
    "cls": "cumulative_layout_shift",
    "fcp": "first_contentful_paint",
    "ttfb": "experimental_time_to_first_byte",
}

METRIC_LABELS = {
    "largest_contentful_paint": "LCP",
    "interaction_to_next_paint": "INP",
    "cumulative_layout_shift": "CLS",
    "first_contentful_paint": "FCP",
    "experimental_time_to_first_byte": "TTFB",
}

METRIC_UNITS = {
    "largest_contentful_paint": "ms",
    "interaction_to_next_paint": "ms",
    "cumulative_layout_shift": "",
    "first_contentful_paint": "ms",
    "experimental_time_to_first_byte": "ms",
}


def get_api_key() -> str | None:
    """Resolve API key from environment."""
    return os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def query_crux_history(
    url: str | None = None,
    origin: str | None = None,
    form_factor: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Query the CrUX History API.

    Exactly one of url or origin must be provided.
    """
    key = api_key or get_api_key()
    if not key:
        return {
            "error": (
                "API key required. Set PAGESPEED_API_KEY or GOOGLE_API_KEY, "
                "or pass --api-key. Get a key at "
                "https://console.cloud.google.com/apis/credentials"
            )
        }

    body: dict = {}
    if url:
        body["url"] = url
    elif origin:
        body["origin"] = origin.rstrip("/")
    else:
        return {"error": "Provide a URL or origin."}

    if form_factor and form_factor.upper() != "ALL":
        body["formFactor"] = form_factor.upper()

    try:
        resp = requests.post(
            CRUX_HISTORY_API,
            params={"key": key},
            json=body,
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code == 404:
        target = url or origin
        return {"error": f"No CrUX data available for {target}. The site may not have enough traffic."}

    if resp.status_code == 429:
        return {"error": "Rate limited by CrUX API. Wait a minute or check your API key quota."}

    if resp.status_code != 200:
        return {"error": f"CrUX API error: HTTP {resp.status_code} — {resp.text[:500]}"}

    try:
        return resp.json()
    except (ValueError, json.JSONDecodeError) as e:
        return {"error": f"Failed to parse API response: {e}"}


def _parse_collection_periods(raw_periods: list[dict]) -> list[str]:
    """Extract date strings from collectionPeriods."""
    dates = []
    for period in raw_periods:
        last_date = period.get("lastDate", {})
        y = last_date.get("year", 0)
        m = last_date.get("month", 0)
        d = last_date.get("day", 0)
        dates.append(f"{y:04d}-{m:02d}-{d:02d}")
    return dates


def parse_history(raw: dict, metrics_filter: list[str] | None = None) -> dict:
    """
    Parse raw CrUX History API response into a structured result.

    Returns dict with collection_periods, metrics (each with p75 timeseries
    and per-bucket percentages), and metadata.
    """
    if "error" in raw:
        return raw

    record = raw.get("record", {})
    key_data = record.get("key", {})
    metrics_data = record.get("metrics", {})
    raw_periods = raw.get("record", {}).get("collectionPeriods", [])

    periods = _parse_collection_periods(raw_periods)
    target = key_data.get("url") or key_data.get("origin", "unknown")
    form_factor = key_data.get("formFactor", "ALL_FORM_FACTORS")

    parsed_metrics = {}
    for api_name, metric_obj in metrics_data.items():
        label = METRIC_LABELS.get(api_name, api_name)
        unit = METRIC_UNITS.get(api_name, "")

        if metrics_filter and api_name not in metrics_filter:
            continue

        percents = metric_obj.get("percentilesTimeseries", {})
        p75_values = percents.get("p75s", [])

        histograms = metric_obj.get("histogramTimeseries", [])
        good_pcts = []
        ni_pcts = []
        poor_pcts = []
        if len(histograms) >= 3:
            good_pcts = [
                round((d.get("density") or 0) * 100, 1)
                for d in histograms[0].get("densities", [])
            ]
            ni_pcts = [
                round((d.get("density") or 0) * 100, 1)
                for d in histograms[1].get("densities", [])
            ]
            poor_pcts = [
                round((d.get("density") or 0) * 100, 1)
                for d in histograms[2].get("densities", [])
            ]

        parsed_metrics[label] = {
            "api_name": api_name,
            "unit": unit,
            "p75_timeseries": p75_values,
            "good_pct_timeseries": good_pcts,
            "needs_improvement_pct_timeseries": ni_pcts,
            "poor_pct_timeseries": poor_pcts,
        }

    return {
        "target": target,
        "form_factor": form_factor,
        "collection_periods": periods,
        "period_count": len(periods),
        "metrics": parsed_metrics,
    }


def print_human(result: dict) -> None:
    """Print CrUX history in a human-readable table."""
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"CrUX History — {result['target']}")
    print(f"Form Factor: {result['form_factor']}")
    print(f"Periods: {result['period_count']} collection windows")
    print("=" * 60)

    periods = result.get("collection_periods", [])

    for metric_label, data in result.get("metrics", {}).items():
        p75s = data.get("p75_timeseries", [])
        unit = data.get("unit", "")
        print(f"\n{metric_label} (p75):")

        display_count = min(len(periods), len(p75s), 10)
        if display_count == 0:
            print("  No data available")
            continue

        start = len(periods) - display_count
        for i in range(start, len(periods)):
            if i < len(p75s):
                val = p75s[i]
                period = periods[i] if i < len(periods) else "?"
                if unit == "ms" and isinstance(val, (int, float)) and val >= 1000:
                    display = f"{val/1000:.1f}s"
                elif unit == "ms":
                    display = f"{val}{unit}"
                else:
                    display = str(val)
                print(f"  {period}  {display}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch historical Core Web Vitals from CrUX History API (Tier 0 — API key only)"
    )
    parser.add_argument(
        "target", nargs="?",
        help="URL or origin to query (used as URL; use --origin for origin-level data)",
    )
    parser.add_argument(
        "--origin", "-O",
        help="Query at origin level instead of URL level",
    )
    parser.add_argument(
        "--metric", "-m",
        choices=["lcp", "inp", "cls", "fcp", "ttfb", "all"],
        default="all",
        help="Filter to a specific metric (default: all)",
    )
    parser.add_argument(
        "--form-factor", "-f",
        choices=["phone", "desktop", "tablet", "all"],
        default="all",
        help="Form factor filter (default: all)",
    )
    parser.add_argument(
        "--api-key",
        help="Google API key (or set PAGESPEED_API_KEY / GOOGLE_API_KEY env var)",
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    url = args.target
    origin = args.origin

    if not url and not origin:
        parser.print_help()
        print("\nError: provide a URL as positional argument or use --origin.", file=sys.stderr)
        sys.exit(1)

    metrics_filter = None
    if args.metric and args.metric != "all":
        api_name = METRIC_KEYS.get(args.metric)
        if api_name:
            metrics_filter = [api_name]

    form_factor = args.form_factor if args.form_factor != "all" else None

    raw = query_crux_history(
        url=url if not origin else None,
        origin=origin or None,
        form_factor=form_factor,
        api_key=args.api_key,
    )

    result = parse_history(raw, metrics_filter=metrics_filter)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)


if __name__ == "__main__":
    main()
