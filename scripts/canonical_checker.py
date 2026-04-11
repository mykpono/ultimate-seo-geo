#!/usr/bin/env python3
"""
Canonical tag validator for SEO audits.

Validates canonical tags across a site: checks self-referencing, resolves
canonical targets, detects www/non-www and HTTP/HTTPS conflicts, trailing
slash inconsistencies, noindex+canonical conflicts, multiple tags, HTTP
header vs HTML canonical mismatches, and cross-page canonical chains.

Catches "Duplicate, Google chose different canonical than user" issues
before they appear in Google Search Console.

Usage:
    python canonical_checker.py https://example.com
    python canonical_checker.py https://example.com --json
    python canonical_checker.py https://example.com --crawl --depth 2
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UltimateSEO-Canonical/1.8)"}


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison (lowercase scheme/host, strip fragment, normalize trailing slash)."""
    parsed = urlparse(url)
    path = parsed.path
    if path in ("", "/"):
        path = "/"
    elif path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        "",  # strip fragment
    ))


def _urls_equivalent(url1: str, url2: str) -> bool:
    """Check if two URLs are equivalent ignoring fragment and case."""
    return _normalize_url(url1) == _normalize_url(url2)


def _extract_canonical_data(html: str, url: str, response_headers: dict) -> dict:
    """Extract all canonical-related signals from a page."""
    soup = BeautifulSoup(html, "html.parser")

    canonical_tags = []
    for link in soup.find_all("link", rel="canonical"):
        href = link.get("href", "").strip()
        if href:
            canonical_tags.append(href)

    meta_robots = ""
    for meta in soup.find_all("meta"):
        if meta.get("name", "").lower() == "robots":
            meta_robots = meta.get("content", "").lower()

    http_canonical = None
    link_header = response_headers.get("Link", "")
    if link_header:
        match = re.search(r'<([^>]+)>;\s*rel="canonical"', link_header, re.I)
        if match:
            http_canonical = match.group(1).strip()

    return {
        "canonical_tags": canonical_tags,
        "meta_robots": meta_robots,
        "http_canonical": http_canonical,
    }


def check_canonical(url: str, timeout: int = 12) -> dict:
    """
    Validate canonical tag for a single URL.

    Checks:
    - Canonical tag presence
    - Absolute vs relative URL
    - Self-referencing canonical
    - HTTPS enforcement
    - www/non-www consistency
    - Trailing slash consistency
    - Multiple canonical tags
    - noindex + canonical conflict
    - HTTP header vs HTML canonical conflict
    - Canonical target resolves to 200
    - Canonical target's own canonical (chain detection)
    """
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    result = {
        "url": url,
        "canonical": None,
        "is_self_referencing": None,
        "canonical_status": None,
        "canonical_target_canonical": None,
        "issues": [],
        "warnings": [],
        "error": None,
    }

    try:
        resp = requests.get(url, timeout=timeout, headers=HEADERS,
                            allow_redirects=True, verify=False)
    except requests.exceptions.RequestException as e:
        result["error"] = f"Failed to fetch page: {str(e)[:100]}"
        return result

    if resp.status_code != 200:
        result["error"] = f"Page returned HTTP {resp.status_code}"
        return result

    final_url = resp.url
    if final_url != url:
        result["warnings"].append({
            "type": "page_redirected",
            "detail": f"Page redirected: {url} → {final_url}",
        })

    data = _extract_canonical_data(resp.text, final_url, dict(resp.headers))

    # --- Multiple canonical tags ---
    if len(data["canonical_tags"]) > 1:
        result["issues"].append({
            "severity": "critical",
            "finding": f"Multiple canonical tags found ({len(data['canonical_tags'])}): "
                       + ", ".join(data["canonical_tags"][:3]),
            "fix": "Remove duplicate canonical tags. Only one <link rel=\"canonical\"> "
                   "should exist per page.",
        })

    tags = data["canonical_tags"]
    http_c = (data.get("http_canonical") or "").strip()

    raw_canonical = None
    if tags:
        raw_canonical = tags[0]
    elif http_c:
        raw_canonical = http_c
        result["warnings"].append({
            "type": "canonical_header_only",
            "detail": (
                "Canonical is declared only via HTTP Link header (no HTML <link rel=\"canonical\">). "
                "Add a matching tag in <head> for consistency with crawlers and auditing tools."
            ),
        })

    if raw_canonical is None:
        result["issues"].append({
            "severity": "high",
            "finding": "No canonical URL in HTML or HTTP Link header.",
            "fix": "Add <link rel=\"canonical\" href=\"[absolute-self-url]\"> to <head> or send an equivalent Link rel=canonical header.",
        })
        result["canonical"] = None
    else:
        # --- Relative URL check ---
        canon_parsed = urlparse(raw_canonical)
        if not canon_parsed.scheme or not canon_parsed.netloc:
            absolute_canonical = urljoin(final_url, raw_canonical)
            result["issues"].append({
                "severity": "high",
                "finding": f"Canonical tag uses relative URL: {raw_canonical}",
                "fix": f"Use absolute URL: {absolute_canonical}",
            })
            raw_canonical = absolute_canonical
            canon_parsed = urlparse(raw_canonical)

        # --- HTTPS check ---
        if canon_parsed.scheme == "http" and parsed.scheme == "https":
            result["issues"].append({
                "severity": "high",
                "finding": f"Canonical uses HTTP ({raw_canonical}) but page is HTTPS.",
                "fix": "Update canonical to use HTTPS.",
            })

        # --- www vs non-www consistency ---
        page_has_www = parsed.netloc.startswith("www.")
        canon_has_www = canon_parsed.netloc.startswith("www.")
        if page_has_www != canon_has_www:
            page_domain = parsed.netloc
            canon_domain = canon_parsed.netloc
            result["issues"].append({
                "severity": "high",
                "finding": f"www mismatch: page is on {page_domain} but canonical "
                           f"points to {canon_domain}. Google may choose a different "
                           f"canonical than intended.",
                "fix": f"Ensure canonical domain matches the page domain, or 301 "
                       f"redirect one version to the other and use the redirected "
                       f"version consistently.",
            })

        # --- Self-referencing check ---
        is_self = _urls_equivalent(raw_canonical, final_url)
        result["is_self_referencing"] = is_self

        if not is_self:
            result["warnings"].append({
                "type": "not_self_referencing",
                "detail": f"Canonical points to a different URL: {raw_canonical} "
                          f"(page URL: {final_url}). This is intentional only if "
                          f"this page is a duplicate of the canonical target.",
            })

        # --- Trailing slash consistency ---
        page_path = urlparse(final_url).path
        canon_path = canon_parsed.path
        page_has_slash = page_path.endswith("/") and len(page_path) > 1
        canon_has_slash = canon_path.endswith("/") and len(canon_path) > 1
        if is_self and page_has_slash != canon_has_slash:
            result["issues"].append({
                "severity": "warning",
                "finding": f"Trailing slash mismatch between page ({final_url}) and "
                           f"canonical ({raw_canonical}).",
                "fix": "Ensure page URL and canonical tag use the same trailing slash "
                       "convention. Pick one and 301 redirect the other.",
            })

        # --- noindex + canonical conflict ---
        if "noindex" in data["meta_robots"]:
            if not is_self:
                result["issues"].append({
                    "severity": "critical",
                    "finding": "Page has both noindex AND a canonical pointing to a "
                               f"different URL ({raw_canonical}). Google may ignore both.",
                    "fix": "Remove noindex if you want the canonical target indexed. "
                           "Or remove the canonical if you want this page excluded entirely.",
                })
            else:
                result["warnings"].append({
                    "type": "noindex_self_canonical",
                    "detail": "Page has noindex with a self-referencing canonical. "
                              "Google will honor noindex but the canonical is redundant.",
                })

        # --- HTTP header vs HTML canonical conflict ---
        if data["http_canonical"]:
            if not _urls_equivalent(data["http_canonical"], raw_canonical):
                result["issues"].append({
                    "severity": "critical",
                    "finding": f"HTTP Link header canonical ({data['http_canonical']}) "
                               f"conflicts with HTML canonical ({raw_canonical}). "
                               f"Google may use either one unpredictably.",
                    "fix": "Make HTTP header and HTML <link> canonical consistent.",
                })

        # --- Validate canonical target ---
        try:
            target_resp = requests.head(
                raw_canonical, timeout=timeout, headers=HEADERS,
                allow_redirects=True, verify=False,
            )
            result["canonical_status"] = target_resp.status_code

            if target_resp.status_code == 404:
                result["issues"].append({
                    "severity": "critical",
                    "finding": f"Canonical URL returns 404: {raw_canonical}",
                    "fix": "Fix the canonical URL or update the canonical tag to "
                           "point to a valid, indexable page.",
                })
            elif target_resp.status_code >= 400:
                result["issues"].append({
                    "severity": "critical",
                    "finding": f"Canonical URL returns HTTP {target_resp.status_code}: "
                               f"{raw_canonical}",
                    "fix": "Canonical must point to a URL that returns 200.",
                })
            elif target_resp.history:
                final_canonical = target_resp.url
                result["issues"].append({
                    "severity": "high",
                    "finding": f"Canonical URL redirects: {raw_canonical} → "
                               f"{final_canonical} ({len(target_resp.history)} hop(s)).",
                    "fix": f"Update canonical to point to the final destination: "
                           f"{final_canonical}",
                })

            if (
                not is_self
                and target_resp.status_code == 200
                and "text/html" in target_resp.headers.get("content-type", "")
            ):
                try:
                    target_get = requests.get(
                        raw_canonical, timeout=timeout, headers=HEADERS,
                        allow_redirects=True, verify=False,
                    )
                    target_data = _extract_canonical_data(
                        target_get.text, target_get.url, dict(target_get.headers),
                    )
                    if target_data["canonical_tags"]:
                        target_canon = target_data["canonical_tags"][0]
                        target_canon_parsed = urlparse(target_canon)
                        if not target_canon_parsed.scheme:
                            target_canon = urljoin(target_get.url, target_canon)
                        result["canonical_target_canonical"] = target_canon

                        if not _urls_equivalent(target_canon, raw_canonical):
                            result["issues"].append({
                                "severity": "critical",
                                "finding": f"Canonical chain: this page's canonical "
                                           f"({raw_canonical}) has its own canonical "
                                           f"pointing elsewhere ({target_canon}). Google "
                                           f"will likely override your canonical choice.",
                                "fix": f"Ensure the canonical target ({raw_canonical}) "
                                       f"has a self-referencing canonical, or update "
                                       f"this page's canonical to {target_canon}.",
                            })
                except requests.exceptions.RequestException:
                    pass

        except requests.exceptions.RequestException:
            result["warnings"].append({
                "type": "canonical_unreachable",
                "detail": f"Could not reach canonical URL: {raw_canonical}",
            })

        result["canonical"] = raw_canonical

    # --- Score ---
    score = 100
    for issue in result["issues"]:
        sev = issue.get("severity", "info")
        if sev == "critical":
            score -= 30
        elif sev == "high":
            score -= 20
        elif sev == "warning":
            score -= 10
    result["score"] = max(0, score)

    return result


def crawl_canonicals(start_url: str, max_depth: int = 2, max_pages: int = 30,
                     max_workers: int = 5, timeout: int = 12) -> dict:
    """
    Multi-page canonical audit: BFS-crawl the site, validate every
    canonical tag, detect cross-page conflicts.
    """
    parsed = urlparse(start_url)
    if not parsed.scheme:
        start_url = f"https://{start_url}"
        parsed = urlparse(start_url)
    domain = parsed.netloc

    result = {
        "start_url": start_url,
        "domain": domain,
        "pages_checked": 0,
        "pages": [],
        "cross_page_issues": [],
        "summary": {},
        "issues": [],
        "recommendations": [],
        "error": None,
    }

    visited = set()
    queue = [(start_url, 0)]
    page_results = []
    canonical_map = {}  # canonical_url -> [pages pointing to it]
    all_urls_found = set()

    while queue and len(visited) < max_pages:
        page_url, depth = queue.pop(0)
        if page_url in visited or depth > max_depth:
            continue
        visited.add(page_url)

        try:
            resp = requests.get(page_url, timeout=timeout, headers=HEADERS,
                                allow_redirects=True, verify=False)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                continue
        except requests.exceptions.RequestException:
            continue

        final_url = resp.url
        data = _extract_canonical_data(resp.text, final_url, dict(resp.headers))

        page_info = {
            "url": final_url,
            "canonical": data["canonical_tags"][0] if data["canonical_tags"] else None,
            "canonical_count": len(data["canonical_tags"]),
            "meta_robots": data["meta_robots"],
            "http_canonical": data["http_canonical"],
            "issues": [],
        }

        canon = page_info["canonical"]
        if canon:
            canon_parsed = urlparse(canon)
            if not canon_parsed.scheme:
                canon = urljoin(final_url, canon)
                page_info["canonical"] = canon

            canonical_map.setdefault(_normalize_url(canon), []).append(final_url)

            if page_info["canonical_count"] > 1:
                page_info["issues"].append({
                    "severity": "critical",
                    "finding": f"Multiple canonical tags on {final_url}",
                    "fix": "Keep only one canonical tag per page.",
                })

            if not _urls_equivalent(canon, final_url):
                page_info["issues"].append({
                    "severity": "info",
                    "finding": f"Non-self-referencing canonical on {final_url} → {canon}",
                    "fix": "Verify this is intentional (page is a true duplicate).",
                })

            if "noindex" in data["meta_robots"] and not _urls_equivalent(canon, final_url):
                page_info["issues"].append({
                    "severity": "critical",
                    "finding": f"noindex + non-self canonical on {final_url}",
                    "fix": "Remove noindex or remove the cross-page canonical.",
                })

            page_has_www = urlparse(final_url).netloc.startswith("www.")
            canon_has_www = urlparse(canon).netloc.startswith("www.")
            if page_has_www != canon_has_www:
                page_info["issues"].append({
                    "severity": "high",
                    "finding": f"www/non-www mismatch on {final_url}: canonical → {canon}",
                    "fix": "Align canonical domain with the page domain.",
                })

            if urlparse(canon).scheme == "http" and urlparse(final_url).scheme == "https":
                page_info["issues"].append({
                    "severity": "high",
                    "finding": f"HTTP canonical on HTTPS page: {final_url}",
                    "fix": "Update canonical to HTTPS.",
                })
        else:
            page_info["issues"].append({
                "severity": "high",
                "finding": f"Missing canonical tag on {final_url}",
                "fix": "Add self-referencing canonical.",
            })

        page_results.append(page_info)

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            abs_url = urljoin(final_url, href)
            abs_parsed = urlparse(abs_url)
            if abs_parsed.netloc == domain:
                normalized = f"{abs_parsed.scheme}://{abs_parsed.netloc}{abs_parsed.path}"
                all_urls_found.add(normalized)
                if normalized not in visited and depth + 1 <= max_depth:
                    queue.append((normalized, depth + 1))

    # --- Cross-page analysis ---
    # Detect multiple pages with same canonical (expected for duplicates, but flag for review)
    for canon_url, pages in canonical_map.items():
        if len(pages) > 1:
            non_self = [p for p in pages if not _urls_equivalent(p, canon_url)]
            if non_self:
                result["cross_page_issues"].append({
                    "severity": "warning",
                    "finding": f"{len(pages)} pages point canonical to {canon_url}: "
                               + ", ".join(pages[:5]),
                    "fix": "Verify these are true duplicates. If not, each page should "
                           "have a self-referencing canonical with unique content.",
                })

    # Detect www/non-www variant pairs
    www_urls = set()
    nonwww_urls = set()
    for pr in page_results:
        url = pr["url"]
        p = urlparse(url)
        if p.netloc.startswith("www."):
            www_urls.add(p.path)
        else:
            nonwww_urls.add(p.path)
    overlap = www_urls & nonwww_urls
    if overlap:
        result["cross_page_issues"].append({
            "severity": "critical",
            "finding": f"Both www and non-www versions are accessible for "
                       f"{len(overlap)} path(s): {', '.join(list(overlap)[:3])}",
            "fix": "301 redirect one variant to the other (www → non-www or vice "
                   "versa) across the entire site. This is the #1 cause of 'Google "
                   "chose different canonical'.",
        })

    result["pages_checked"] = len(page_results)
    result["pages"] = page_results

    # Aggregate issues
    total_issues = sum(len(p["issues"]) for p in page_results)
    missing_canonical = sum(1 for p in page_results if not p["canonical"])
    multi_canonical = sum(1 for p in page_results if p["canonical_count"] > 1)
    noindex_conflict = sum(
        1 for p in page_results
        if "noindex" in p["meta_robots"] and p["canonical"]
        and not _urls_equivalent(p["canonical"], p["url"])
    )
    www_mismatch = sum(
        1 for p in page_results
        if p["canonical"] and (
            urlparse(p["url"]).netloc.startswith("www.") !=
            urlparse(p["canonical"]).netloc.startswith("www.")
        )
    )

    # Alternate page detection: non-self-referencing canonicals
    alternate_pages = [
        p for p in page_results
        if p["canonical"] and not _urls_equivalent(p["canonical"], p["url"])
    ]
    self_referencing = [
        p for p in page_results
        if p["canonical"] and _urls_equivalent(p["canonical"], p["url"])
    ]

    result["alternate_pages"] = [
        {"url": p["url"], "canonical_target": p["canonical"]}
        for p in alternate_pages
    ]

    result["summary"] = {
        "pages_checked": len(page_results),
        "total_issues": total_issues + len(result["cross_page_issues"]),
        "missing_canonical": missing_canonical,
        "self_referencing": len(self_referencing),
        "alternate_pages": len(alternate_pages),
        "multiple_canonical_tags": multi_canonical,
        "noindex_canonical_conflicts": noindex_conflict,
        "www_mismatches": www_mismatch,
        "cross_page_issues": len(result["cross_page_issues"]),
    }

    if missing_canonical:
        result["issues"].append(
            f"🔴 {missing_canonical} page(s) missing canonical tag"
        )
    if multi_canonical:
        result["issues"].append(
            f"🔴 {multi_canonical} page(s) have multiple canonical tags"
        )
    if noindex_conflict:
        result["issues"].append(
            f"🔴 {noindex_conflict} page(s) have noindex + non-self canonical conflict"
        )
    if www_mismatch:
        result["issues"].append(
            f"⚠️ {www_mismatch} page(s) have www/non-www canonical mismatch"
        )

    if alternate_pages:
        alt_pct = len(alternate_pages) / max(1, len(page_results)) * 100
        severity = "🔴" if alt_pct > 50 or len(alternate_pages) > 15 else "⚠️"
        result["issues"].append(
            f"{severity} {len(alternate_pages)} page(s) ({alt_pct:.0f}%) are "
            f"alternate pages (canonical points to a different URL). "
            f"GSC reports these as 'Alternate page with proper canonical tag' — "
            f"they won't be indexed."
        )
        targets = set(p["canonical"] for p in alternate_pages)
        if len(targets) <= 3:
            result["issues"].append(
                f"   All alternate pages canonicalize to: "
                + ", ".join(list(targets)[:3])
            )

    if missing_canonical or www_mismatch:
        result["recommendations"].append(
            "Ensure every indexable page has a self-referencing canonical with "
            "the correct protocol (HTTPS) and domain (consistent www/non-www)."
        )
    if alternate_pages:
        result["recommendations"].append(
            "Review alternate pages. If these pages have unique, valuable content "
            "that should be indexed, change their canonical to self-referencing. "
            "If they are true duplicates, consider 301 redirecting to the canonical "
            "target instead (stronger signal than canonical tag). If content is "
            "similar but distinct, differentiate it significantly."
        )
    if result["cross_page_issues"]:
        result["recommendations"].append(
            "Review cross-page canonical conflicts. If Google ignores your canonical, "
            "the most common causes are: www/non-www both accessible, trailing slash "
            "variants serving the same content, or content similarity with another page."
        )

    # Score
    score = 100
    score -= missing_canonical * 15
    score -= multi_canonical * 20
    score -= noindex_conflict * 25
    score -= www_mismatch * 15
    score -= len(result["cross_page_issues"]) * 10
    result["score"] = max(0, min(100, score))

    return result


def main():
    parser = argparse.ArgumentParser(description="Canonical tag validator")
    parser.add_argument("url", help="URL to check")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--crawl", action="store_true",
                        help="Multi-page crawl mode: check canonicals across the site")
    parser.add_argument("--depth", "-d", type=int, default=2,
                        help="Max crawl depth for --crawl mode (default: 2)")
    parser.add_argument("--max-pages", "-m", type=int, default=30,
                        help="Max pages in --crawl mode (default: 30)")
    parser.add_argument("--workers", "-w", type=int, default=5,
                        help="Concurrent workers (default: 5)")
    parser.add_argument("--timeout", "-t", type=int, default=12,
                        help="Request timeout in seconds (default: 12)")

    args = parser.parse_args()

    if args.crawl:
        result = crawl_canonicals(
            args.url, max_depth=args.depth, max_pages=args.max_pages,
            max_workers=args.workers, timeout=args.timeout,
        )
    else:
        result = check_canonical(args.url, timeout=args.timeout)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    if args.crawl:
        print(f"Canonical Audit — {result['domain']}")
        print("=" * 60)
        s = result["summary"]
        print(f"Pages checked: {s['pages_checked']}")
        print(f"Missing canonical: {s['missing_canonical']}")
        print(f"Multiple tags: {s['multiple_canonical_tags']}")
        print(f"noindex conflicts: {s['noindex_canonical_conflicts']}")
        print(f"www mismatches: {s['www_mismatches']}")

        for page in result["pages"]:
            if page["issues"]:
                print(f"\n  {page['url']}")
                print(f"    canonical: {page['canonical'] or '(none)'}")
                for issue in page["issues"]:
                    icon = "🔴" if issue["severity"] in ("critical", "high") else "⚠️"
                    print(f"    {icon} {issue['finding']}")

        if result["cross_page_issues"]:
            print(f"\nCross-Page Issues:")
            for issue in result["cross_page_issues"]:
                icon = "🔴" if issue["severity"] == "critical" else "⚠️"
                print(f"  {icon} {issue['finding']}")
                print(f"     Fix: {issue['fix']}")
    else:
        print(f"Canonical Check — {result['url']}")
        print("=" * 60)
        print(f"Canonical: {result['canonical'] or '(none)'}")
        print(f"Self-referencing: {result['is_self_referencing']}")
        print(f"Canonical status: {result['canonical_status']}")
        print(f"Score: {result['score']}/100")

        if result["issues"]:
            print(f"\nIssues:")
            for issue in result["issues"]:
                icon = "🔴" if issue["severity"] in ("critical", "high") else "⚠️"
                print(f"  {icon} [{issue['severity'].upper()}] {issue['finding']}")
                print(f"     Fix: {issue['fix']}")

        if result["warnings"]:
            print(f"\nWarnings:")
            for w in result["warnings"]:
                print(f"  ⚠️ {w['detail']}")

    if result.get("recommendations"):
        print(f"\nRecommendations:")
        for rec in result["recommendations"]:
            print(f"  💡 {rec}")


if __name__ == "__main__":
    main()
