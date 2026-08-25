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

import jsonld

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required"}))
    sys.exit(1)

USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-Local/1.8)"


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

    lb = jsonld.declares_type(html, "LocalBusiness")
    org = jsonld.declares_type(html, "Organization")
    website = jsonld.declares_type(html, "WebSite")
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

    has_local_indicators = bool(tel or street or maps)
    likely_local = has_local_indicators or lb

    score = 40
    if lb:
        score += 35
        recs.append("LocalBusiness JSON-LD detected — validate NAP consistency in references/local-seo.md.")
    elif has_local_indicators:
        issues.append(
            {
                "severity": "high",
                "finding": "Local signals detected (phone, address, map) but no LocalBusiness JSON-LD.",
                "fix": "Add LocalBusiness schema with name, address, telephone, openingHours, areaServed.",
            }
        )
    else:
        recs.append(
            "No local business signals detected. This site appears to be a "
            "publisher, SaaS, or non-local business — LocalBusiness schema "
            "is not applicable. No action needed."
        )
    if org and not lb:
        score += 10
    if tel > 0:
        score += 10
    else:
        if has_local_indicators:
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

    if not lb and has_local_indicators:
        recs.append("Strong partial local signals — add LocalBusiness schema to match.")

    if not likely_local:
        score = None

    return {
        "url": url,
        "http_status": status,
        "likely_local_business": likely_local,
        "localbusiness_jsonld": lb,
        "organization_jsonld": org,
        "has_local_indicators": has_local_indicators,
        "tel_links": tel,
        "mailto_links": mail,
        "structured_address_signals": street,
        "map_embed_or_link": maps,
        "score": min(100, score) if score is not None else None,
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
