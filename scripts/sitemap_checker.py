#!/usr/bin/env python3
"""
Sitemap discovery, validation, and URL health checking.

Discovers sitemaps from robots.txt, validates format, and samples
sitemap URLs to verify they return HTTP 200 (catches GSC "Not found 404"
and soft 404 issues before they appear in Search Console).

Usage:
  python sitemap_checker.py https://example.com
  python sitemap_checker.py https://example.com --json
  python sitemap_checker.py https://example.com --sample 50
  python sitemap_checker.py https://example.com --check-all
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required: pip install requests"}))
    sys.exit(1)

USER_AGENT = "Mozilla/5.0 (compatible; SEOSkill-Sitemap/1.0)"

SEARCH_URL_PATTERNS = re.compile(
    r"[?&](q|query|search|s|search_term_string|keyword|term)=", re.I
)
FACETED_URL_PATTERNS = re.compile(
    r"[?&](sort|order|filter|page|offset|limit|color|size|brand|category|tag)=", re.I
)
TEMPLATE_PLACEHOLDER = re.compile(r"\{[^}]+\}")


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


def _head_check(url: str, timeout: int = 10) -> dict:
    """HEAD request with GET fallback; returns status info."""
    result = {"url": url, "status": None, "error": None, "redirect": None, "soft_404": False}
    try:
        resp = requests.head(
            url, timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True, verify=False,
        )
        if resp.status_code == 405:
            resp = requests.get(
                url, timeout=timeout,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True, verify=False, stream=True,
            )
        result["status"] = resp.status_code
        if resp.history:
            result["redirect"] = {
                "from": url, "to": resp.url,
                "hops": len(resp.history),
            }
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("text/html"):
            body = ""
            try:
                body = resp.text[:5000] if hasattr(resp, "text") else ""
            except Exception:
                pass
            if body:
                lower = body.lower()
                soft_404_signals = [
                    "page not found", "404", "not found",
                    "no longer available", "does not exist",
                    "page doesn't exist", "page has been removed",
                ]
                for signal in soft_404_signals:
                    if signal in lower:
                        title_match = re.search(r"<title[^>]*>(.*?)</title>", lower)
                        if title_match and signal in title_match.group(1):
                            result["soft_404"] = True
                            break
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection_failed"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)[:100]
    return result


def _analyze_url_patterns(urls: list[str]) -> dict:
    """Detect problematic URL patterns that shouldn't be in sitemaps."""
    findings = {
        "search_urls": [],
        "faceted_urls": [],
        "template_urls": [],
        "parameter_urls": [],
    }
    for url in urls:
        if TEMPLATE_PLACEHOLDER.search(url):
            findings["template_urls"].append(url)
        elif SEARCH_URL_PATTERNS.search(url):
            findings["search_urls"].append(url)
        elif FACETED_URL_PATTERNS.search(url):
            findings["faceted_urls"].append(url)
        elif "?" in url:
            findings["parameter_urls"].append(url)
    return findings


def _resolve_sitemap_index(xml: str, base: str, timeout: int = 12) -> list[str]:
    """If xml is a sitemap index, fetch child sitemaps and collect all <loc> URLs."""
    child_sitemaps = re.findall(r"<sitemap>\s*<loc>\s*([^<\s]+)\s*</loc>", xml, re.I)
    all_locs = []
    for sm_url in child_sitemaps[:20]:
        if sm_url.startswith("/"):
            sm_url = urljoin(base + "/", sm_url.lstrip("/"))
        sc, body = _fetch(sm_url, timeout)
        if sc == 200:
            all_locs.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.I))
    return all_locs


def check_sitemaps(
    site_url: str,
    sample_size: int = 30,
    check_all: bool = False,
    max_workers: int = 8,
) -> dict:
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
        "url_health": {
            "checked": 0,
            "healthy": 0,
            "not_found_404": [],
            "server_errors_5xx": [],
            "redirected": [],
            "soft_404s": [],
            "timeouts": [],
            "errors": [],
        },
        "url_patterns": {
            "search_urls": [],
            "faceted_urls": [],
            "template_urls": [],
            "parameter_urls": [],
        },
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

    is_index = "<sitemap>" in xml.lower() and "<sitemapindex" in xml.lower()
    if is_index:
        child_locs = _resolve_sitemap_index(xml, base)
        locs = child_locs if child_locs else locs

    out["url_count_estimate"] = len(locs)

    if len(locs) == 0 and "<url>" not in xml.lower() and "<sitemap>" not in xml.lower():
        out["issues"].append(
            {
                "severity": "warning",
                "finding": "Sitemap response does not look like XML sitemap (no <loc> entries).",
                "fix": "Validate sitemap format (XML sitemap index or urlset).",
            }
        )

    # --- URL pattern analysis ---
    if locs:
        out["url_patterns"] = _analyze_url_patterns(locs)
        patterns = out["url_patterns"]

        if patterns["template_urls"]:
            out["issues"].append({
                "severity": "critical",
                "finding": (
                    f"{len(patterns['template_urls'])} URL(s) in sitemap contain template "
                    f"placeholders (e.g. {{search_term_string}}): "
                    f"{', '.join(patterns['template_urls'][:3])}"
                ),
                "fix": (
                    "Remove template/placeholder URLs from sitemap immediately. "
                    "These are not real pages and waste crawl budget."
                ),
            })

        if patterns["search_urls"]:
            out["issues"].append({
                "severity": "high",
                "finding": (
                    f"{len(patterns['search_urls'])} search result URL(s) found in sitemap: "
                    f"{', '.join(patterns['search_urls'][:3])}"
                ),
                "fix": (
                    "Remove search result pages from sitemap. Add <meta name=\"robots\" "
                    "content=\"noindex\"> to search result pages to prevent indexation. "
                    "Block via robots.txt: Disallow: /search"
                ),
            })

        if patterns["faceted_urls"]:
            faceted_count = len(patterns["faceted_urls"])
            if faceted_count > 5:
                out["issues"].append({
                    "severity": "warning",
                    "finding": f"{faceted_count} faceted/filtered URLs in sitemap (sort, filter, page params).",
                    "fix": (
                        "Remove faceted URLs from sitemap. Use canonical tags pointing "
                        "to the master category page. Consider noindex on filtered views."
                    ),
                })

    # --- Sample URL health checks ---
    if locs and (sample_size > 0 or check_all):
        urls_to_check = list(locs)
        if not check_all and len(urls_to_check) > sample_size:
            urls_to_check = random.sample(urls_to_check, sample_size)

        health = out["url_health"]
        health["checked"] = len(urls_to_check)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_head_check, url): url for url in urls_to_check}
            for future in as_completed(futures):
                r = future.result()
                status = r["status"]
                if r["error"]:
                    if r["error"] == "timeout":
                        health["timeouts"].append(r["url"])
                    else:
                        health["errors"].append({"url": r["url"], "error": r["error"]})
                elif status and 400 <= status < 500:
                    health["not_found_404"].append({"url": r["url"], "status": status})
                elif status and status >= 500:
                    health["server_errors_5xx"].append({"url": r["url"], "status": status})
                elif r.get("soft_404"):
                    health["soft_404s"].append(r["url"])
                elif r.get("redirect"):
                    health["redirected"].append({
                        "url": r["url"],
                        "redirect_to": r["redirect"]["to"],
                        "hops": r["redirect"]["hops"],
                    })
                else:
                    health["healthy"] += 1

        n404 = len(health["not_found_404"])
        n5xx = len(health["server_errors_5xx"])
        nsoft = len(health["soft_404s"])
        nred = len(health["redirected"])

        if n404:
            out["issues"].append({
                "severity": "critical",
                "finding": (
                    f"{n404} sitemap URL(s) return 404 Not Found "
                    f"(checked {health['checked']}/{out['url_count_estimate']}): "
                    + ", ".join(e["url"] for e in health["not_found_404"][:5])
                ),
                "fix": (
                    "For each 404 URL: (1) If content was moved, add a 301 redirect to "
                    "the new URL. (2) If content was deleted, remove the URL from the "
                    "sitemap and let the 404 stand (or 410 for permanent removal). "
                    "(3) Fix any internal links still pointing to these URLs."
                ),
            })

        if n5xx:
            out["issues"].append({
                "severity": "critical",
                "finding": (
                    f"{n5xx} sitemap URL(s) return 5xx server errors: "
                    + ", ".join(e["url"] for e in health["server_errors_5xx"][:5])
                ),
                "fix": "Investigate server errors. Fix application bugs or resource limits causing 5xx responses.",
            })

        if nsoft:
            out["issues"].append({
                "severity": "high",
                "finding": (
                    f"{nsoft} sitemap URL(s) are soft 404s (return 200 but show 'not found' content): "
                    + ", ".join(health["soft_404s"][:5])
                ),
                "fix": (
                    "Return a real 404/410 status code instead of 200 for pages that don't "
                    "exist. Soft 404s waste crawl budget and confuse search engines."
                ),
            })

        if nred > 3:
            out["issues"].append({
                "severity": "warning",
                "finding": f"{nred} sitemap URLs redirect to different URLs.",
                "fix": (
                    "Update sitemap to use final destination URLs. Sitemaps should only "
                    "contain canonical, non-redirecting URLs."
                ),
            })

    if out["url_count_estimate"] > 0:
        out["recommendations"].append(
            f"Primary sitemap lists ~{out['url_count_estimate']} URLs — monitor Coverage in GSC."
        )

    # --- Score ---
    score = 30
    if robots_code == 200 and out["sitemap_urls"]:
        score += 20
    if sc == 200:
        score += 15
    if out["url_count_estimate"] > 0:
        score += 10

    health = out["url_health"]
    if health["checked"] > 0:
        healthy_pct = health["healthy"] / health["checked"]
        if healthy_pct >= 0.95:
            score += 25
        elif healthy_pct >= 0.80:
            score += 15
        elif healthy_pct >= 0.60:
            score += 5
        else:
            score -= 10

    n_pattern_issues = (
        len(out["url_patterns"]["template_urls"])
        + len(out["url_patterns"]["search_urls"])
    )
    if n_pattern_issues > 0:
        score -= min(20, n_pattern_issues * 10)

    out["score"] = max(0, min(100, score))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Sitemap discovery, validation, and URL health checking")
    p.add_argument("url", help="Site URL")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--sample", type=int, default=30,
        help="Number of sitemap URLs to sample-check (default: 30; 0 to skip)",
    )
    p.add_argument(
        "--check-all", action="store_true",
        help="Check ALL sitemap URLs instead of sampling (slow for large sitemaps)",
    )
    p.add_argument(
        "--workers", "-w", type=int, default=8,
        help="Concurrent workers for URL checks (default: 8)",
    )
    args = p.parse_args()
    data = check_sitemaps(
        args.url,
        sample_size=args.sample,
        check_all=args.check_all,
        max_workers=args.workers,
    )
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
