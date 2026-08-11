#!/usr/bin/env python3
"""
Google Search Console — OAuth connection, URL Inspection export, CSV merge.

Important limitation (2025): Google does **not** expose the full "Page indexing"
table through the Search Console API the way the UI does. The API provides:
  • Site list, sitemaps, and Search Analytics (performance) — see Search Console API.
  • URL Inspection (`index:inspect`) — per-URL verdict & coverage state (daily quota).

This script connects with OAuth, lists verified properties, and either:
  (A) Inspects URLs you provide (`--urls`, `--url-file`, or `--sitemap-url`); or
  (B) Merges a CSV you exported from GSC ("Page indexing" → Export) with fresh
      URL Inspection results for those URLs.

Setup (one-time):
  1) Google Cloud Console → APIs & Services → Enable "Google Search Console API".
  2) OAuth consent screen (External or Internal) + add scope:
     https://www.googleapis.com/auth/webmasters
  3) Credentials → OAuth 2.0 Client ID → Desktop app → Download JSON.
  4) Save as `gsc-client-secrets.json` in this repo root (gitignored) or pass
     `--client-secrets /path/to/client_secret.json`

Install optional deps:
  pip install -r requirements-gsc.txt

Examples:
  python scripts/gsc_export.py --auth
  python scripts/gsc_export.py --list-properties
  python scripts/gsc_export.py --property https://www.example.com/ \\
      --urls https://www.example.com/a https://www.example.com/b --output gsc.json
  python scripts/gsc_export.py --property sc-domain:example.com \\
      --sitemap-url https://www.example.com/sitemap.xml --max-urls 50 --output out.csv
  python scripts/gsc_export.py --property https://www.example.com/ \\
      --import-gsc-csv ~/Downloads/Page-indexing-report.csv --output merged.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required: pip install requests"}))
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_CLIENT = os.path.join(REPO_ROOT, "gsc-client-secrets.json")
DEFAULT_TOKEN = os.path.join(REPO_ROOT, "gsc-oauth-token.json")

SCOPES = ["https://www.googleapis.com/auth/webmasters"]
SITES_BASE = "https://www.googleapis.com/webmasters/v3/sites"
INSPECT_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"

USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-GSC/1.0)"


def _json_print(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _load_oauth_modules():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise SystemExit(
            "Missing Google auth libraries. Install: pip install -r requirements-gsc.txt\n"
            f"Detail: {e}"
        )
    return Request, Credentials, InstalledAppFlow


def get_credentials(
    client_secrets: str,
    token_path: str,
    no_browser: bool,
) -> Any:
    """Return valid google.oauth2.credentials.Credentials."""
    Request, Credentials, InstalledAppFlow = _load_oauth_modules()

    creds = None
    if os.path.isfile(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not os.path.isfile(client_secrets):
            raise SystemExit(
                f"OAuth client secrets not found at {client_secrets}\n"
                "Download a Desktop OAuth client JSON from Google Cloud Console and save it there, "
                "or pass --client-secrets."
            )
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
        if no_browser:
            creds = flow.run_console()
        else:
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds


def authorized_session(creds: Any):
    from google.auth.transport.requests import AuthorizedSession

    return AuthorizedSession(creds)


def list_properties(session) -> dict[str, Any]:
    r = session.get(SITES_BASE, timeout=30)
    r.raise_for_status()
    data = r.json()
    sites = data.get("siteEntry") or []
    return {
        "count": len(sites),
        "properties": [
            {
                "siteUrl": s.get("siteUrl"),
                "permissionLevel": s.get("permissionLevel"),
            }
            for s in sites
        ],
    }


def inspect_url(session, site_url: str, inspection_url: str) -> dict[str, Any]:
    body = {"inspectionUrl": inspection_url, "siteUrl": site_url}
    r = session.post(INSPECT_URL, json=body, timeout=60)
    if r.status_code == 429:
        return {"error": "quota_exceeded", "status_code": 429, "body": r.text[:500]}
    if not r.ok:
        return {
            "error": "inspect_failed",
            "status_code": r.status_code,
            "body": r.text[:1000],
        }
    return r.json()


_LOC_RE = re.compile(r"<loc[^>]*>\s*([^<]+?)\s*</loc>", re.I)


def urls_from_sitemap(sitemap_url: str, max_urls: int, timeout: int = 30) -> list[str]:
    """Fetch a sitemap or sitemap index and return up to max_urls page URLs."""
    out: list[str] = []
    seen_page: set[str] = set()
    seen_fetch: set[str] = set()

    def fetch_one(url: str) -> str:
        resp = requests.get(
            url, timeout=timeout, headers={"User-Agent": USER_AGENT}
        )
        resp.raise_for_status()
        return resp.text

    def all_locs(body: str) -> list[str]:
        return [(m.group(1) or "").strip() for m in _LOC_RE.finditer(body)]

    def is_sitemap_index(body: str) -> bool:
        b = body.lstrip()[:4000].lower()
        return "<sitemapindex" in b

    def walk(url: str) -> None:
        nonlocal out
        if url in seen_fetch or len(out) >= max_urls:
            return
        seen_fetch.add(url)
        try:
            body = fetch_one(url)
        except Exception:
            return
        if is_sitemap_index(body):
            for child in all_locs(body):
                if len(out) >= max_urls:
                    return
                walk(child)
            return
        for loc in all_locs(body):
            if len(out) >= max_urls:
                return
            if loc not in seen_page:
                seen_page.add(loc)
                out.append(loc)

    try:
        walk(sitemap_url)
    except Exception as e:
        raise SystemExit(f"Failed to read sitemap {sitemap_url}: {e}") from e
    return out[:max_urls]


def _pick_url_column(fieldnames: list[str] | None) -> str | None:
    if not fieldnames:
        return None
    lower = {f.lower().strip(): f for f in fieldnames}
    for key in ("url", "address", "page", "page url"):
        if key in lower:
            return lower[key]
    for f in fieldnames:
        if "url" in f.lower():
            return f
    return None


def load_gsc_csv(path: str) -> tuple[list[dict[str, str]], str | None]:
    """Read GSC-exported CSV; return rows and detected URL column name."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        url_col = _pick_url_column(reader.fieldnames)
        rows = []
        for row in reader:
            rows.append({k: (v or "").strip() for k, v in row.items()})
        return rows, url_col


def simplify_inspection(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten URL Inspection response for CSV/JSON export."""
    if "error" in raw:
        return {"error": raw}

    ins = raw.get("inspectionResult") or {}
    idx = ins.get("indexStatusResult") or {}
    amp = ins.get("ampResult") or {}
    mob = ins.get("mobileUsabilityResult") or {}
    rr = ins.get("richResultsResult") or {}

    return {
        "verdict": idx.get("verdict"),
        "coverage_state": idx.get("coverageState"),
        "robots_txt_state": idx.get("robotsTxtState"),
        "indexing_state": idx.get("indexingState"),
        "page_fetch_state": idx.get("pageFetchState"),
        "google_canonical": idx.get("googleCanonical"),
        "user_canonical": idx.get("userCanonical"),
        "last_crawl_time": idx.get("lastCrawlTime"),
        "crawled_as": idx.get("crawledAs"),
        "mobile_usability_verdict": mob.get("verdict"),
        "rich_results_verdict": rr.get("verdict"),
        "amp_verdict_result": amp.get("verdict"),
    }


def run_inspections(
    session,
    site_url: str,
    urls: list[str],
    pause_sec: float,
) -> list[dict[str, Any]]:
    results = []
    for i, u in enumerate(urls):
        raw = inspect_url(session, site_url, u)
        flat = simplify_inspection(raw)
        row = {"inspection_url": u, **flat}
        if "error" in flat:
            row["raw_inspection_error"] = flat["error"]
        results.append(row)
        if i < len(urls) - 1 and pause_sec > 0:
            time.sleep(pause_sec)
    return results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Google Search Console OAuth helper + URL Inspection export / CSV merge."
    )
    p.add_argument(
        "--client-secrets",
        default=DEFAULT_CLIENT,
        help=f"OAuth client JSON (default: {DEFAULT_CLIENT})",
    )
    p.add_argument(
        "--token",
        default=DEFAULT_TOKEN,
        help=f"Saved OAuth token path (default: {DEFAULT_TOKEN})",
    )
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="OAuth without local browser (print URL for --auth only).",
    )
    p.add_argument(
        "--auth",
        action="store_true",
        help="Run OAuth flow and save token; no API calls.",
    )
    p.add_argument(
        "--list-properties",
        action="store_true",
        help="List Search Console properties the account can access.",
    )
    p.add_argument(
        "--property",
        metavar="SITE_URL",
        help='Search Console property id, e.g. "https://www.example.com/" or "sc-domain:example.com"',
    )
    p.add_argument(
        "--urls",
        nargs="*",
        metavar="URL",
        help="URLs to inspect (must belong to --property).",
    )
    p.add_argument(
        "--url-file",
        metavar="PATH",
        help="Text file: one URL per line.",
    )
    p.add_argument(
        "--sitemap-url",
        metavar="URL",
        help="Fetch URLs from this sitemap or sitemap index (capped by --max-urls).",
    )
    p.add_argument(
        "--max-urls",
        type=int,
        default=100,
        help="Max URLs from sitemap mode (default: 100).",
    )
    p.add_argument(
        "--pause",
        type=float,
        default=0.35,
        help="Seconds between URL Inspection API calls (default: 0.35).",
    )
    p.add_argument(
        "--import-gsc-csv",
        metavar="PATH",
        help="CSV exported from GSC Page indexing report; adds inspection fields per URL.",
    )
    p.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help="Write JSON or CSV (format from extension .json or .csv).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print JSON to stdout (default when no --output).",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.auth:
        get_credentials(args.client_secrets, args.token, args.no_browser)
        _json_print(
            {
                "ok": True,
                "token_saved": args.token,
                "next": "Run: python scripts/gsc_export.py --list-properties",
            }
        )
        return

    creds = get_credentials(args.client_secrets, args.token, args.no_browser)
    session = authorized_session(creds)

    if args.list_properties:
        out = list_properties(session)
        if args.output:
            ext = os.path.splitext(args.output)[1].lower()
            if ext == ".json":
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(out, f, indent=2, ensure_ascii=False)
            else:
                raise SystemExit("--list-properties with --output supports .json only")
        elif args.json or not args.output:
            _json_print(out)
        return

    if not args.property:
        raise SystemExit(
            "Specify --property for inspection, or use --list-properties / --auth.\n"
            'Example: --property "https://www.example.com/" --urls https://...'
        )

    site_url = args.property.rstrip()
    if not site_url.endswith("/") and not site_url.startswith("sc-domain:"):
        # GSC often uses trailing slash for URL-prefix properties
        if site_url.startswith("http"):
            site_url = site_url + "/"

    urls: list[str] = []
    if args.urls:
        urls.extend(args.urls)
    if args.url_file:
        with open(args.url_file, encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if u and not u.startswith("#"):
                    urls.append(u)
    if args.sitemap_url:
        urls.extend(urls_from_sitemap(args.sitemap_url, args.max_urls))

    gsc_rows: list[dict[str, str]] = []
    url_col: str | None = None
    if args.import_gsc_csv:
        gsc_rows, url_col = load_gsc_csv(args.import_gsc_csv)
        if not url_col:
            raise SystemExit(
                "Could not detect a URL column in CSV. Expected a column named URL (or similar)."
            )
        for row in gsc_rows:
            u = row.get(url_col, "").strip()
            if u and u not in urls:
                urls.append(u)

    if not urls:
        raise SystemExit(
            "No URLs to inspect. Use --urls, --url-file, --sitemap-url, and/or --import-gsc-csv."
        )

    inspections = run_inspections(session, site_url, urls, args.pause)

    merged: list[dict[str, Any]] = []
    if gsc_rows and url_col:
        insp_by_url = {row["inspection_url"]: row for row in inspections}
        for row in gsc_rows:
            u = row.get(url_col, "").strip()
            combo = dict(row)
            combo["url_inspection"] = insp_by_url.get(u, {"error": "not_inspected"})
            merged.append(combo)
    else:
        merged = inspections

    out_payload: dict[str, Any] = {
        "property": site_url,
        "url_count": len(urls),
        "api_note": (
            "URL Inspection has a daily per-property quota (typically ~2,000). "
            "The full Page indexing table is not available via API; use GSC CSV export + this script."
        ),
        "rows": merged,
    }

    if args.output:
        ext = os.path.splitext(args.output)[1].lower()
        if ext == ".json":
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(out_payload, f, indent=2, ensure_ascii=False)
        elif ext == ".csv":
            all_keys: set[str] = set()
            flat_rows: list[dict[str, Any]] = []
            for item in merged:
                if isinstance(item, dict) and "url_inspection" in item:
                    flat = dict(item)
                    ui = flat.pop("url_inspection", {})
                    if isinstance(ui, dict):
                        for k, v in ui.items():
                            flat[f"inspection_{k}"] = v
                    flat_rows.append(flat)
                else:
                    flat_rows.append(item)
            for r in flat_rows:
                all_keys.update(r.keys())
            fieldnames = sorted(all_keys)
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                w.writeheader()
                for r in flat_rows:
                    w.writerow({k: r.get(k, "") for k in fieldnames})
        else:
            raise SystemExit("--output must end with .json or .csv")
    elif args.json or not args.output:
        _json_print(out_payload)


if __name__ == "__main__":
    main()
