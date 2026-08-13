#!/usr/bin/env python3
"""
Fetch live Google organic results via the SerpBase API.

Complements gsc_query.py (Google Search Console — your own site's
performance) with what Google actually shows for a keyword right now:
titles, URLs, snippets, and positions for the top N organic results.

Credentials:
  - Set SERPBASE_API_KEY to your SerpBase API key (get one at
    https://serpbase.dev — free tier available), or pass --api-key.

Usage:
    python scripts/serp_api.py "best seo tools 2026" --json
    python scripts/serp_api.py "site audit checklist" --num 20 --json
    SERPBASE_API_KEY=... python scripts/serp_api.py "keyword" --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    print(
        "Error: requests library required. Install with: pip install requests",
        file=sys.stderr,
    )
    sys.exit(1)

SERPBASE_ENDPOINT = "https://api.serpbase.dev/google/search"
USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-SerpBase/1.8)"

NO_KEY_MSG = (
    "SERPBASE_API_KEY not set. Get a free API key at https://serpbase.dev "
    "and export it (or pass --api-key)."
)


def fetch_serp(
    query: str,
    api_key: str,
    num: int = 10,
    timeout: int = 30,
) -> dict:
    """Return parsed organic results for *query* via the SerpBase API.

    On failure returns {"error": ...} instead of raising, so callers can
    degrade gracefully when the API is unreachable.
    """
    try:
        resp = requests.get(
            SERPBASE_ENDPOINT,
            params={"q": query, "api_key": api_key, "num": num},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    if resp.status_code != 200:
        return {"error": f"SerpBase API returned HTTP {resp.status_code}: {resp.text[:200]}"}

    try:
        data = resp.json()
    except ValueError:
        return {"error": "SerpBase API returned invalid JSON."}

    results = []
    for item in data.get("organic_results", []):
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "position": item.get("position"),
                "title": item.get("title"),
                "link": item.get("link") or item.get("url"),
                "snippet": item.get("snippet"),
            }
        )
    return {"query": query, "count": len(results), "organic_results": results}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch live Google organic results via the SerpBase API."
    )
    parser.add_argument("query", help="Search query (quote it if it contains spaces)")
    parser.add_argument("--api-key", help="SerpBase API key (or set SERPBASE_API_KEY)")
    parser.add_argument("--num", type=int, default=10, help="Number of results (default: 10)")
    parser.add_argument("--json", action="store_true", help="Emit JSON on stdout")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("SERPBASE_API_KEY", "")
    if not api_key:
        print(json.dumps({"error": NO_KEY_MSG}))
        return 1

    data = fetch_serp(args.query, api_key, num=args.num)

    if "error" in data:
        print(json.dumps(data))
        return 1

    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    print(f"Query: {data['query']} ({data['count']} results)")
    for r in data["organic_results"]:
        pos = r.get("position") or "?"
        print(f"\n{pos}. {r.get('title')}")
        print(f"   {r.get('link')}")
        if r.get("snippet"):
            print(f"   {r['snippet'][:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
