#!/usr/bin/env python3
"""
Ingest a hand-exported Search Console "Search Generative AI" performance CSV.

WHY THIS SCRIPT EXISTS
----------------------
Search Console's Search Generative AI performance reports (launched June 3, 2026)
show impressions inside AI Overviews, AI Mode and Discover's AI features. That data
is **not available programmatically**: there is no Search Console API endpoint, no
BigQuery export, and `searchanalytics.query`'s `type` field is unchanged and will
never return it. `gsc_query.py` therefore cannot fetch it and must not pretend to.

The only supported path is the one this script implements: the user exports the CSV
from the Search Console UI, and this script normalises it into the same flat row
shape `gsc_query.py:format_rows()` produces, so it can flow into a report.

WHAT THE DATA CONTAINS
----------------------
Impressions only, broken down by page, country, device and date. There are **no**
clicks, no CTR, no position and no query/prompt data. This script does not
synthesise those fields -- a row that has no clicks reports no clicks. Any output
claiming AI clicks or AI CTR is fabricated.

Usage:
    python gsc_ai_import.py exported-ai-performance.csv
    python gsc_ai_import.py exported-ai-performance.csv --json
    python gsc_ai_import.py exported-ai-performance.csv --top 20
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Search Console localises and varies its CSV headers by report tab. Map the ones
# we understand onto the dimension names gsc_query.py already emits.
DIMENSION_ALIASES = {
    "page": "page",
    "pages": "page",
    "url": "page",
    "top pages": "page",
    "landing page": "page",
    "country": "country",
    "countries": "country",
    "device": "device",
    "devices": "device",
    "date": "date",
    "dates": "date",
}

IMPRESSION_ALIASES = {"impressions", "impression", "total impressions"}

# Fields the report does not contain. If a CSV somehow carries them, they are not
# generative-AI metrics and must not be presented as such.
UNSUPPORTED_METRICS = {"clicks", "ctr", "position", "average position", "total clicks"}


def _normalise_header(name: str) -> str:
    return name.replace("﻿", "").strip().lower()


def _parse_impressions(raw: str) -> int:
    """Parse an impression count, tolerating thousands separators and blanks."""
    cleaned = (raw or "").strip().replace(",", "").replace(" ", "").replace(" ", "")
    if not cleaned:
        return 0
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def import_ai_csv(path: str) -> dict:
    """Read an exported generative-AI performance CSV into normalised rows."""
    csv_path = Path(path)
    if not csv_path.is_file():
        return {"error": f"File not found: {path}"}

    try:
        text = csv_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return {"error": f"Could not decode {path} as UTF-8. Re-export the CSV from Search Console."}

    reader = csv.reader(text.splitlines())
    try:
        header = next(reader)
    except StopIteration:
        return {"error": f"{path} is empty."}

    headers = [_normalise_header(h) for h in header]

    dimension_cols: list[tuple[int, str]] = []
    impression_col: int | None = None
    ignored: list[str] = []

    for i, h in enumerate(headers):
        if h in DIMENSION_ALIASES:
            dimension_cols.append((i, DIMENSION_ALIASES[h]))
        elif h in IMPRESSION_ALIASES:
            impression_col = i
        elif h in UNSUPPORTED_METRICS:
            ignored.append(h)

    if impression_col is None:
        return {
            "error": (
                f"No impressions column found in {path}. Columns seen: {headers}. "
                "Export the Search Generative AI performance report from Search Console, "
                "not the standard Performance report."
            )
        }
    if not dimension_cols:
        return {
            "error": (
                f"No recognised dimension column (page, country, device, date) in {path}. "
                f"Columns seen: {headers}."
            )
        }

    dimensions = [name for _, name in dimension_cols]
    rows: list[dict] = []
    for record in reader:
        if not record or all(not c.strip() for c in record):
            continue
        entry: dict = {}
        for idx, name in dimension_cols:
            entry[name] = record[idx].strip() if idx < len(record) else ""
        entry["impressions"] = _parse_impressions(
            record[impression_col] if impression_col < len(record) else ""
        )
        rows.append(entry)

    return {
        "source_file": str(csv_path),
        "surface": "google_generative_ai",
        "dimensions": dimensions,
        "rows": rows,
        "total_impressions": sum(r["impressions"] for r in rows),
        "row_count": len(rows),
        "ignored_columns": ignored,
        "metrics_unavailable": ["clicks", "ctr", "position", "queries"],
        "note": (
            "Impressions only. Search Console's generative AI reports provide no clicks, CTR, "
            "position or query data, and expose no API or BigQuery export. Do not derive or "
            "estimate those metrics from this data."
        ),
    }


def print_human(result: dict, top: int) -> None:
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Search Console — Generative AI performance (imported CSV)")
    print(f"Source: {result['source_file']}")
    print(f"Dimensions: {', '.join(result['dimensions'])}")
    print("=" * 70)

    rows = result["rows"]
    if not rows:
        print("No data rows found in the export.")
        return

    dims = result["dimensions"]
    ranked = sorted(rows, key=lambda r: r["impressions"], reverse=True)

    print(f"{'  '.join(d.upper() for d in dims):<52} {'Impressions':>12}")
    print("-" * 70)
    for row in ranked[:top]:
        dim_values = "  ".join(str(row.get(d, ""))[:25] for d in dims)
        print(f"{dim_values:<52} {row['impressions']:>12,}")

    if len(ranked) > top:
        print(f"\n... and {len(ranked) - top:,} more rows (use --json for full data)")

    print(f"\nTotal impressions: {result['total_impressions']:,} across {result['row_count']:,} rows")

    if result["ignored_columns"]:
        print(
            f"\nIgnored columns: {', '.join(result['ignored_columns'])} — these are not "
            "generative-AI metrics and were not imported."
        )

    print(
        "\nNote: impressions only. The generative AI reports carry no clicks, CTR, position or"
        "\nquery data, and no API or BigQuery export exists. Do not estimate those metrics from"
        "\nthis data — pair it with GA4 for the downstream traffic question instead."
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Import a hand-exported Search Console Search Generative AI performance CSV. "
            "This data has no API; manual export is the only path."
        )
    )
    parser.add_argument("csv_path", help="Path to the CSV exported from Search Console")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--top", type=int, default=25, help="Rows to show in table output (default 25)")

    args = parser.parse_args()
    result = import_ai_csv(args.csv_path)

    if args.json:
        print(json.dumps(result, indent=2))
        sys.exit(1 if "error" in result else 0)

    print_human(result, args.top)


if __name__ == "__main__":
    main()
