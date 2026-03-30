#!/usr/bin/env python3
"""
Check for broken links on a web page (or across an entire site).

Crawls all links (internal + external) on a page, checks HTTP status.
Reports broken (4xx/5xx), redirected (3xx), soft 404s, and timeout links.

Usage:
    python broken_links.py https://example.com
    python broken_links.py https://example.com --json
    python broken_links.py https://example.com --internal-only
    python broken_links.py https://example.com --crawl --depth 2
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 library required. Install with: pip install beautifulsoup4")
    sys.exit(1)


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOSkill/1.0)"}

SOFT_404_TITLE_SIGNALS = [
    "page not found", "404", "not found", "no longer available",
    "does not exist", "doesn't exist", "has been removed",
    "page has moved", "no results found",
]


def extract_links(html: str, base_url: str) -> list:
    """Extract all links from HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()

        # Skip anchors, javascript, mailto, tel
        if href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue

        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)

        anchor_text = tag.get_text(strip=True)[:80] or "[no text]"
        links.append({
            "url": absolute,
            "anchor_text": anchor_text,
            "is_internal": urlparse(absolute).netloc == urlparse(base_url).netloc,
        })

    return links


def check_link(link: dict, timeout: int = 10, detect_soft_404: bool = True) -> dict:
    """Check a single link's HTTP status, including soft 404 detection."""
    url = link["url"]
    result = {
        **link, "status": None, "error": None, "redirect": None,
        "response_time_ms": None, "soft_404": False,
    }

    try:
        use_get = detect_soft_404 and link.get("is_internal", False)
        if use_get:
            resp = requests.get(url, timeout=timeout, headers=HEADERS,
                                allow_redirects=True, verify=False, stream=True)
        else:
            resp = requests.head(url, timeout=timeout, headers=HEADERS,
                                 allow_redirects=True, verify=False)
            if resp.status_code == 405:
                resp = requests.get(url, timeout=timeout, headers=HEADERS,
                                    allow_redirects=True, verify=False, stream=True)

        result["status"] = resp.status_code
        result["response_time_ms"] = round(resp.elapsed.total_seconds() * 1000)

        if resp.history:
            result["redirect"] = {
                "from": url,
                "to": resp.url,
                "hops": len(resp.history),
                "codes": [r.status_code for r in resp.history],
            }

        if (
            detect_soft_404
            and resp.status_code == 200
            and "text/html" in resp.headers.get("content-type", "")
        ):
            try:
                body_lower = resp.text[:5000].lower() if hasattr(resp, "text") else ""
                title_match = re.search(r"<title[^>]*>(.*?)</title>", body_lower)
                if title_match:
                    title_text = title_match.group(1)
                    for signal in SOFT_404_TITLE_SIGNALS:
                        if signal in title_text:
                            result["soft_404"] = True
                            break
            except Exception:
                pass

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection_failed"
    except requests.exceptions.TooManyRedirects:
        result["error"] = "too_many_redirects"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)[:100]

    return result


def check_broken_links(url: str, internal_only: bool = False,
                       max_workers: int = 10, timeout: int = 10) -> dict:
    """
    Check all links on a page for broken links.

    Args:
        url: Page URL to check
        internal_only: Only check internal links
        max_workers: Concurrent request threads
        timeout: Per-request timeout in seconds

    Returns:
        Dictionary with all link check results
    """
    result = {
        "page_url": url,
        "total_links": 0,
        "checked": 0,
        "broken": [],
        "redirected": [],
        "timeout": [],
        "soft_404s": [],
        "healthy": 0,
        "summary": {},
        "issues": [],
        "error": None,
    }

    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            result["error"] = f"Failed to fetch page: HTTP {resp.status_code}"
            return result
        html = resp.text
    except requests.exceptions.RequestException as e:
        result["error"] = f"Failed to fetch page: {e}"
        return result

    links = extract_links(html, url)
    if internal_only:
        links = [l for l in links if l["is_internal"]]

    result["total_links"] = len(links)

    if not links:
        result["issues"].append("⚠️ No links found on page")
        return result

    checked = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_link, link, timeout): link for link in links}
        for future in as_completed(futures):
            checked.append(future.result())

    result["checked"] = len(checked)

    for link in checked:
        status = link["status"]

        if link["error"]:
            if link["error"] == "timeout":
                result["timeout"].append(link)
            else:
                result["broken"].append(link)
        elif link.get("soft_404"):
            result["soft_404s"].append(link)
        elif status and status >= 400:
            result["broken"].append(link)
        elif link["redirect"]:
            result["redirected"].append(link)
        else:
            result["healthy"] += 1

    result["summary"] = {
        "total": result["total_links"],
        "healthy": result["healthy"],
        "broken": len(result["broken"]),
        "redirected": len(result["redirected"]),
        "timeout": len(result["timeout"]),
        "soft_404s": len(result["soft_404s"]),
    }

    if result["broken"]:
        result["issues"].append(
            f"🔴 {len(result['broken'])} broken link(s) found"
        )
    if result["soft_404s"]:
        result["issues"].append(
            f"⚠️ {len(result['soft_404s'])} soft 404(s) found (page returns 200 but shows 'not found')"
        )
    if result["timeout"]:
        result["issues"].append(
            f"⚠️ {len(result['timeout'])} link(s) timed out"
        )
    if result["redirected"]:
        chains = [l for l in result["redirected"]
                  if l.get("redirect", {}).get("hops", 0) > 1]
        if chains:
            result["issues"].append(
                f"⚠️ {len(chains)} redirect chain(s) detected (>1 hop)"
            )

    return result


def crawl_broken_links(start_url: str, max_depth: int = 2, max_pages: int = 50,
                       internal_only: bool = True, max_workers: int = 8,
                       timeout: int = 10) -> dict:
    """
    Multi-page broken link scan: BFS-crawl the site and check all
    discovered links across multiple pages.
    """
    parsed = urlparse(start_url)
    domain = parsed.netloc

    result = {
        "start_url": start_url,
        "domain": domain,
        "pages_crawled": 0,
        "total_links_checked": 0,
        "broken": [],
        "soft_404s": [],
        "redirected_chains": [],
        "timeout": [],
        "summary": {},
        "issues": [],
        "error": None,
    }

    visited_pages = set()
    checked_links = set()
    queue = [(start_url, 0)]
    all_broken = []
    all_soft_404s = []
    all_chains = []
    all_timeouts = []
    links_checked_count = 0
    healthy_count = 0
    broken_by_target = defaultdict(list)

    while queue and len(visited_pages) < max_pages:
        page_url, depth = queue.pop(0)
        if page_url in visited_pages or depth > max_depth:
            continue
        visited_pages.add(page_url)

        try:
            resp = requests.get(page_url, timeout=15, headers=HEADERS, allow_redirects=True)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                continue
            html = resp.text
        except requests.exceptions.RequestException:
            continue

        links = extract_links(html, resp.url)
        if internal_only:
            links = [l for l in links if l["is_internal"]]

        new_links = [l for l in links if l["url"] not in checked_links]
        for l in new_links:
            checked_links.add(l["url"])

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(check_link, link, timeout): link for link in new_links}
            for future in as_completed(futures):
                link_result = future.result()
                links_checked_count += 1
                status = link_result["status"]

                link_result["found_on"] = page_url

                if link_result["error"]:
                    if link_result["error"] == "timeout":
                        all_timeouts.append(link_result)
                    else:
                        all_broken.append(link_result)
                        broken_by_target[link_result["url"]].append(page_url)
                elif link_result.get("soft_404"):
                    all_soft_404s.append(link_result)
                elif status and status >= 400:
                    all_broken.append(link_result)
                    broken_by_target[link_result["url"]].append(page_url)
                elif link_result.get("redirect", {}).get("hops", 0) > 1:
                    all_chains.append(link_result)
                else:
                    healthy_count += 1

        for link in links:
            if (
                link["is_internal"]
                and link["url"] not in visited_pages
                and depth + 1 <= max_depth
            ):
                queue.append((link["url"], depth + 1))

    # Deduplicate broken by target URL
    seen_broken = set()
    unique_broken = []
    for b in all_broken:
        if b["url"] not in seen_broken:
            seen_broken.add(b["url"])
            b["linked_from"] = broken_by_target.get(b["url"], [b.get("found_on", "")])[:5]
            unique_broken.append(b)

    result["pages_crawled"] = len(visited_pages)
    result["total_links_checked"] = links_checked_count
    result["broken"] = unique_broken
    result["soft_404s"] = all_soft_404s
    result["redirected_chains"] = all_chains
    result["timeout"] = all_timeouts
    result["summary"] = {
        "pages_crawled": len(visited_pages),
        "total_checked": links_checked_count,
        "healthy": healthy_count,
        "broken": len(unique_broken),
        "soft_404s": len(all_soft_404s),
        "redirect_chains": len(all_chains),
        "timeout": len(all_timeouts),
    }

    if unique_broken:
        result["issues"].append(
            f"🔴 {len(unique_broken)} unique broken link target(s) found across {len(visited_pages)} pages"
        )
    if all_soft_404s:
        result["issues"].append(
            f"⚠️ {len(all_soft_404s)} soft 404(s) — pages return 200 but show 'not found' content"
        )
    if all_chains:
        result["issues"].append(
            f"⚠️ {len(all_chains)} redirect chain(s) with >1 hop"
        )
    if all_timeouts:
        result["issues"].append(
            f"⚠️ {len(all_timeouts)} link(s) timed out"
        )

    return result


def main():
    parser = argparse.ArgumentParser(description="Check for broken links on a page or site")
    parser.add_argument("url", help="Page URL to check")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--internal-only", "-i", action="store_true",
                        help="Only check internal links")
    parser.add_argument("--crawl", action="store_true",
                        help="Multi-page crawl mode: BFS-crawl the site checking all links")
    parser.add_argument("--depth", "-d", type=int, default=2,
                        help="Max crawl depth for --crawl mode (default: 2)")
    parser.add_argument("--max-pages", "-m", type=int, default=50,
                        help="Max pages to crawl in --crawl mode (default: 50)")
    parser.add_argument("--workers", "-w", type=int, default=10,
                        help="Concurrent workers (default: 10)")
    parser.add_argument("--timeout", "-t", type=int, default=10,
                        help="Per-link timeout in seconds (default: 10)")

    args = parser.parse_args()

    if args.crawl:
        result = crawl_broken_links(
            args.url, max_depth=args.depth, max_pages=args.max_pages,
            internal_only=args.internal_only, max_workers=args.workers,
            timeout=args.timeout,
        )
    else:
        result = check_broken_links(args.url, internal_only=args.internal_only,
                                    max_workers=args.workers, timeout=args.timeout)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    if args.crawl:
        print(f"Site-Wide Broken Link Scan — {result['domain']}")
        print("=" * 50)
        s = result["summary"]
        print(f"Pages crawled: {s['pages_crawled']} | Links checked: {s['total_checked']}")
        print(f"✅ Healthy: {s['healthy']} | 🔴 Broken: {s['broken']} | "
              f"⚠️ Soft 404s: {s['soft_404s']} | ⏱️ Timeout: {s['timeout']}")
    else:
        print(f"Broken Link Check — {result['page_url']}")
        print("=" * 50)
        s = result["summary"]
        print(f"Total: {s['total']} | ✅ Healthy: {s['healthy']} | "
              f"🔴 Broken: {s['broken']} | ↪️ Redirected: {s['redirected']} | "
              f"⚠️ Soft 404s: {s.get('soft_404s', 0)} | ⏱️ Timeout: {s['timeout']}")

    if result["broken"]:
        print(f"\n🔴 Broken Links:")
        for link in result["broken"]:
            status = link.get("status") or link.get("error")
            loc = "internal" if link.get("is_internal") else "external"
            print(f"  [{status}] ({loc}) {link['url']}")
            if link.get("anchor_text"):
                print(f"         anchor: \"{link['anchor_text']}\"")
            if link.get("linked_from"):
                for src in link["linked_from"][:3]:
                    print(f"         ← linked from {src}")

    if result.get("soft_404s"):
        print(f"\n⚠️ Soft 404s:")
        for link in result["soft_404s"]:
            print(f"  {link['url']}")

    redirected = result.get("redirected", result.get("redirected_chains", []))
    if redirected:
        chains = [l for l in redirected
                  if l.get("redirect", {}).get("hops", 0) > 1]
        if chains:
            print(f"\n⚠️ Redirect Chains (>1 hop):")
            for link in chains:
                r = link["redirect"]
                print(f"  {link['url']}")
                print(f"    → {r['to']} ({r['hops']} hops: {r.get('codes', [])})")

    if result.get("timeout"):
        print(f"\n⏱️ Timed Out:")
        for link in result["timeout"]:
            print(f"  {link['url']}")

    if result.get("issues"):
        print(f"\nIssues:")
        for issue in result["issues"]:
            print(f"  {issue}")


if __name__ == "__main__":
    main()
