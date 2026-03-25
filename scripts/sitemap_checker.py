#!/usr/bin/env python3
"""
Sitemap discovery from robots.txt and basic validation of the first sitemap.

Usage:
  python sitemap_checker.py https://example.com
  python sitemap_checker.py https://example.com --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required: pip install requests"}))
    sys.exit(1)

USER_AGENT = "Mozilla/5.0 (compatible; SEOSkill-Sitemap/1.0)"


def _fetch(url: str, timeout: int = 12) -> tuple[int | None, str]:
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        return r.status_code, r.text or ""
    except Exception as e:
        return None, str(e)


def check_sitemaps(site_url: str) -> dict:
    parsed = urlparse(site_url)
    if not parsed.scheme:
        site_url = f"https://{site_url}"
        parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"

    out: dict = {
        "url": site_url,
        "robots_url": robots_url,
        "sitemap_urls": [],
        "primary_sitemap_url": None,
        "primary_status": None,
        "url_count_estimate": 0,
        "issues": [],
        "recommendations": [],
    }

    robots_code, body = _fetch(robots_url)
    if robots_code != 200:
        out["issues"].append(
            {
                "severity": "warning",
                "finding": f"robots.txt not reachable (HTTP {robots_code}).",
                "fix": "Publish robots.txt with Sitemap: directives.",
            }
        )
        # try default sitemap.xml
        guess = f"{base}/sitemap.xml"
        guess_code, _ = _fetch(guess)
        if guess_code == 200:
            out["sitemap_urls"].append(guess)
    else:
        for line in body.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sm = line.split(":", 1)[1].strip()
                if sm:
                    out["sitemap_urls"].append(sm)

    if not out["sitemap_urls"]:
        out["issues"].append(
            {
                "severity": "high",
                "finding": "No Sitemap: lines in robots.txt and no fallback sitemap.xml.",
                "fix": "Add `Sitemap: https://example.com/sitemap.xml` to robots.txt.",
            }
        )
        out["recommendations"].append("Submit XML sitemaps in Google Search Console.")
        return out

    primary = out["sitemap_urls"][0]
    out["primary_sitemap_url"] = primary
    # resolve relative
    if primary.startswith("/"):
        primary = urljoin(base + "/", primary.lstrip("/"))

    sc, xml = _fetch(primary)
    out["primary_status"] = sc
    if sc != 200:
        out["issues"].append(
            {
                "severity": "critical",
                "finding": f"Primary sitemap returned HTTP {sc}: {primary}",
                "fix": "Fix sitemap URL or server response.",
            }
        )
        return out

    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml, re.I)
    out["url_count_estimate"] = len(locs)
    if len(locs) == 0 and "<url>" not in xml.lower() and "<sitemap>" not in xml.lower():
        out["issues"].append(
            {
                "severity": "warning",
                "finding": "Sitemap response does not look like XML sitemap (no <loc> entries).",
                "fix": "Validate sitemap format (XML sitemap index or urlset).",
            }
        )
    if out["url_count_estimate"] > 0:
        out["recommendations"].append(
            f"Primary sitemap lists ~{out['url_count_estimate']} URLs — monitor Coverage in GSC."
        )

    # score
    score = 30
    if robots_code == 200 and out["sitemap_urls"]:
        score += 30
    if sc == 200:
        score += 25
    if out["url_count_estimate"] > 0:
        score += 15
    out["score"] = min(100, score)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Sitemap discovery and basic validation")
    p.add_argument("url", help="Site URL")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = check_sitemaps(args.url)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
