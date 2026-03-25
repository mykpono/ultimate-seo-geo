#!/usr/bin/env python3
"""
Image SEO quick check: alt coverage on a saved HTML file or fetched URL.

Usage:
  python image_checker.py /path/to/page.html --base-url https://example.com
  python image_checker.py --url https://example.com/page
  python image_checker.py page.html --base-url https://example.com --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(json.dumps({"error": "beautifulsoup4 required"}))
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None


def analyze_html(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml" if "lxml" in sys.modules else "html.parser")
    imgs = soup.find_all("img")
    total = len(imgs)
    missing = 0
    decorative_ok = 0
    issues = []
    for img in imgs:
        alt = img.get("alt")
        if alt is None:
            missing += 1
        elif str(alt).strip() == "":
            # empty alt can be OK for decorative if role or context — flag as info
            decorative_ok += 1
        elif len(str(alt).strip()) < 3:
            issues.append(
                {
                    "severity": "info",
                    "finding": f"Very short alt text: {alt!r}",
                    "fix": "Use descriptive alt for meaningful images.",
                }
            )

    pct_missing = round(100 * missing / total, 1) if total else 0.0
    score = 100
    if total == 0:
        score = 70
        issues.append(
            {
                "severity": "info",
                "finding": "No <img> elements on page.",
                "fix": "If this is a visual page, add images with descriptive alt text.",
            }
        )
    else:
        score = max(0, 100 - int(missing * (100 / max(total, 1))))
        if missing > 0:
            issues.append(
                {
                    "severity": "high" if pct_missing > 25 else "warning",
                    "finding": f"{missing}/{total} images missing alt attribute ({pct_missing}%).",
                    "fix": "Add descriptive alt for content images; use alt=\"\" only for decorative images.",
                }
            )

    recs = []
    if pct_missing > 10:
        recs.append("See references/image-seo.md for alt text and format guidance.")

    return {
        "base_url": base_url,
        "total_images": total,
        "missing_alt": missing,
        "empty_alt": decorative_ok,
        "missing_alt_pct": pct_missing,
        "score": min(100, score),
        "issues": issues[:15],
        "recommendations": recs,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Image SEO quick audit")
    p.add_argument("path", nargs="?", help="Path to local HTML file")
    p.add_argument("--url", help="Fetch this URL instead of reading a file")
    p.add_argument("--base-url", default="", help="Canonical base URL for context")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    html = ""
    base = args.base_url or ""

    if args.url:
        if not requests:
            print(json.dumps({"error": "requests required for --url"}))
            sys.exit(1)
        try:
            r = requests.get(
                args.url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SEOSkill-Image/1.0)"},
            )
            html = r.text
            base = base or args.url
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
    elif args.path:
        fp = Path(args.path)
        if not fp.is_file():
            print(json.dumps({"error": f"not a file: {args.path}"}))
            sys.exit(1)
        html = fp.read_text(encoding="utf-8", errors="ignore")
        base = base or "https://example.com"
    else:
        print(json.dumps({"error": "Provide path or --url"}))
        sys.exit(1)

    data = analyze_html(html, base)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
