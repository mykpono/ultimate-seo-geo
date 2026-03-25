#!/usr/bin/env python3
"""Title and meta description length checks (on-page SEO signals).

Usage:
  python scripts/meta_lengths_checker.py page.html --base-url https://example.com --json
  python scripts/meta_lengths_checker.py --url https://example.com --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(
        json.dumps(
            {
                "error": "beautifulsoup4 required",
                "hint": "pip install -r requirements.txt  "
                "or: python3 scripts/requirements-check.py",
            }
        )
    )
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None


def analyze_html(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml" if "lxml" in sys.modules else "html.parser")

    title_el = soup.find("title")
    title = (title_el.get_text() if title_el else "") or ""
    title = " ".join(title.split())

    meta_desc = ""
    for m in soup.find_all("meta", attrs={"name": re.compile("^description$", re.I)}):
        meta_desc = m.get("content") or ""
        break
    if not meta_desc:
        for m in soup.find_all("meta", attrs={"property": re.compile("og:description", re.I)}):
            meta_desc = m.get("content") or ""
            break
    meta_desc = " ".join(str(meta_desc).split())

    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h1_count = len(h1s)
    h1_first = h1s[0] if h1s else ""

    tl = len(title)
    ml = len(meta_desc)

    issues = []
    if not title.strip():
        issues.append({"severity": "critical", "finding": "Missing <title>", "fix": "Add a unique title."})
    elif tl < 30:
        issues.append(
            {
                "severity": "warning",
                "finding": f"Title short ({tl} chars); may under-explain the page in SERPs.",
                "fix": "Expand toward ~30–60 chars with primary keyword + brand.",
            }
        )
    elif tl > 60:
        issues.append(
            {
                "severity": "warning",
                "finding": f"Title long ({tl} chars); may truncate in Google.",
                "fix": "Tighten to ~60 chars; keep primary keyword in the first 50.",
            }
        )

    if not meta_desc.strip():
        issues.append(
            {
                "severity": "high",
                "finding": "Missing meta description (and no og:description).",
                "fix": "Add a unique meta description ~150–160 chars with benefit-led copy.",
            }
        )
    elif ml < 120:
        issues.append(
            {
                "severity": "info",
                "finding": f"Meta description short ({ml} chars).",
                "fix": "Aim ~150–160 chars for fuller SERP snippet control.",
            }
        )
    elif ml > 160:
        issues.append(
            {
                "severity": "warning",
                "finding": f"Meta description long ({ml} chars); may truncate.",
                "fix": "Trim to ~155–160 chars; front-load the value prop.",
            }
        )

    if h1_count == 0:
        issues.append({"severity": "high", "finding": "No H1 on page.", "fix": "Add one H1 matching main intent."})
    elif h1_count > 1:
        issues.append(
            {
                "severity": "warning",
                "finding": f"Multiple H1s ({h1_count}).",
                "fix": "Use one H1; demote others to H2 unless template requires exception.",
            }
        )

    worst = 100
    for i in issues:
        worst = min(
            worst,
            {"critical": 40, "high": 60, "warning": 80, "info": 90}[i["severity"]],
        )

    return {
        "url": page_url,
        "title": title[:200],
        "title_length": tl,
        "meta_description": meta_desc[:300],
        "meta_description_length": ml,
        "h1_count": h1_count,
        "h1_first": h1_first[:200],
        "score": worst,
        "issues": issues,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Title / meta description length checker")
    p.add_argument("path", nargs="?", help="Local HTML file")
    p.add_argument("--url", help="Fetch URL instead of file")
    p.add_argument("--base-url", default="", help="Label URL in output when using local file")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    html = ""
    page_url = args.base_url or ""

    if args.url:
        if not requests:
            err = {"error": "requests required for --url"}
            print(json.dumps(err))
            sys.exit(1)
        try:
            r = requests.get(
                args.url,
                timeout=25,
                headers={"User-Agent": "ultimate-seo-geo-meta-checker/1.0"},
            )
            r.raise_for_status()
            html = r.text
            page_url = args.url
        except Exception as e:
            print(json.dumps({"error": str(e), "url": args.url}))
            sys.exit(1)
    elif args.path:
        fp = Path(args.path)
        if not fp.is_file():
            print(json.dumps({"error": "not_found", "path": str(fp)}))
            sys.exit(1)
        html = fp.read_text(encoding="utf-8", errors="replace")
        page_url = page_url or fp.as_uri()
    else:
        p.error("Provide path to HTML or --url")

    out = analyze_html(html, page_url)
    if args.json:
        print(json.dumps(out))
    else:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
