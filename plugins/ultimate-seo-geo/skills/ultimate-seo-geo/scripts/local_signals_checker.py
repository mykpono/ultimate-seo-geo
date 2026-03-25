#!/usr/bin/env python3
"""
Local SEO surface signals: LocalBusiness JSON-LD, tel/mailto links, address keywords.

Usage:
  python local_signals_checker.py https://example.com
  python local_signals_checker.py https://example.com --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required"}))
    sys.exit(1)

USER_AGENT = "Mozilla/5.0 (compatible; SEOSkill-Local/1.0)"


def check_local_signals(url: str) -> dict:
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
    issues = []
    recs = []

    try:
        r = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        html = r.text or ""
        status = r.status_code
    except Exception as e:
        return {"error": str(e), "url": url}

    lb = bool(re.search(r'"@type"\s*:\s*"LocalBusiness"', html, re.I))
    org = bool(re.search(r'"@type"\s*:\s*"Organization"', html, re.I))
    tel = len(re.findall(r'href=["\']tel:', html, re.I))
    mail = len(re.findall(r'href=["\']mailto:', html, re.I))
    street = bool(
        re.search(
            r'\b(streetAddress|postalCode|addressLocality|Address")\b',
            html,
            re.I,
        )
    )
    maps = "google.com/maps" in html.lower() or "maps.app.goo.gl" in html.lower()

    score = 40
    if lb:
        score += 35
        recs.append("LocalBusiness JSON-LD detected — validate NAP consistency in references/local-seo.md.")
    else:
        issues.append(
            {
                "severity": "high",
                "finding": "No LocalBusiness JSON-LD detected on this page.",
                "fix": "Add LocalBusiness schema with name, address, telephone, openingHours, areaServed.",
            }
        )
    if org and not lb:
        score += 10
    if tel > 0:
        score += 10
    else:
        issues.append(
            {
                "severity": "medium",
                "finding": "No tel: links found.",
                "fix": "Add clickable phone (tel:) in header/footer.",
            }
        )
    if street:
        score += 5
    if maps:
        score += 5

    if not lb and (tel or street):
        recs.append("Strong partial local signals — add LocalBusiness schema to match.")

    return {
        "url": url,
        "http_status": status,
        "localbusiness_jsonld": lb,
        "organization_jsonld": org,
        "tel_links": tel,
        "mailto_links": mail,
        "structured_address_signals": street,
        "map_embed_or_link": maps,
        "score": min(100, score),
        "issues": issues[:12],
        "recommendations": recs,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Local SEO quick signals")
    p.add_argument("url", help="Page URL (often homepage or location page)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = check_local_signals(args.url)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
