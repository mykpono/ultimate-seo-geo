#!/usr/bin/env python3
"""
Analyze internal link structure of a website.

Checks link count, anchor text distribution, orphan page detection,
and link depth from homepage.

Usage:
    python internal_links.py https://example.com
    python internal_links.py https://example.com --depth 2 --json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
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
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOSkill/1.0)"}


def extract_internal_links(html: str, page_url: str, domain: str) -> list:
    """Extract internal links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue

        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)

        # Only internal links
        if parsed.netloc != domain:
            continue

        # Normalize: remove fragments, trailing slashes
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if normalized.endswith("/") and len(parsed.path) > 1:
            normalized = normalized.rstrip("/")

        if normalized in seen:
            continue
        seen.add(normalized)

        anchor_text = tag.get_text(strip=True)[:80] or "[no text]"
        nofollow = "nofollow" in (tag.get("rel", []) or [])
        links.append({
            "url": normalized,
            "anchor_text": anchor_text,
            "nofollow": nofollow,
            "source": page_url,
        })

    return links


def crawl_site(start_url: str, max_depth: int = 2, max_pages: int = 50,
               max_workers: int = 5, timeout: int = 10) -> dict:
    """
    Crawl internal links up to max_depth.

    Args:
        start_url: Starting URL (usually homepage)
        max_depth: Maximum crawl depth
        max_pages: Maximum pages to crawl
        max_workers: Concurrent request threads
        timeout: Per-page timeout

    Returns:
        Dictionary with link structure analysis
    """
    parsed = urlparse(start_url)
    domain = parsed.netloc

    result = {
        "start_url": start_url,
        "domain": domain,
        "pages_crawled": 0,
        "total_internal_links": 0,
        "unique_pages_found": 0,
        "max_depth_reached": 0,
        "pages": {},
        "anchor_texts": {},
        "link_distribution": {},
        "orphan_candidates": [],
        "nofollow_links": [],
        "broken_internal_pages": [],
        "soft_404_pages": [],
        "server_error_pages": [],
        "redirected_pages": [],
        "issues": [],
        "recommendations": [],
        "error": None,
    }

    SOFT_404_SIGNALS = [
        "page not found", "404", "not found", "no longer available",
        "does not exist", "page doesn't exist", "page has been removed",
    ]

    # BFS crawl
    visited = set()
    queue = [(start_url, 0)]  # (url, depth)
    all_links = []
    page_link_counts = {}
    pages_linking_to = defaultdict(set)  # url -> set of pages linking to it
    pages_found_at_depth = defaultdict(list)
    broken_pages = {}  # url -> {"status": int, "linked_from": [urls]}
    soft_404_pages = {}
    server_error_pages = {}
    redirected_pages = {}  # url -> {"final_url": str, "linked_from": [urls]}

    def fetch_page(url):
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS, allow_redirects=True)
            status = resp.status_code
            content_type = resp.headers.get("content-type", "")
            was_redirected = resp.url != url and resp.history

            if status == 200 and "text/html" in content_type:
                lower_body = resp.text[:5000].lower()
                import re
                title_match = re.search(r"<title[^>]*>(.*?)</title>", lower_body)
                if title_match:
                    title_text = title_match.group(1)
                    for signal in SOFT_404_SIGNALS:
                        if signal in title_text:
                            return resp.text, resp.url, status, "soft_404", was_redirected
                return resp.text, resp.url, status, "ok", was_redirected
            return None, resp.url, status, "error", was_redirected
        except requests.exceptions.RequestException:
            return None, url, None, "error", False

    while queue and len(visited) < max_pages:
        batch = []
        while queue and len(batch) < max_workers:
            url, depth = queue.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)
            batch.append((url, depth))

        if not batch:
            break

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_page, url): (url, depth) for url, depth in batch}
            for future in as_completed(futures):
                url, depth = futures[future]
                html, final_url, status, page_status, was_redirected = future.result()

                if status and 400 <= status < 500:
                    broken_pages[url] = {"status": status, "linked_from": []}
                    continue
                elif status and status >= 500:
                    server_error_pages[url] = {"status": status, "linked_from": []}
                    continue
                elif page_status == "soft_404":
                    soft_404_pages[url] = {"linked_from": []}

                if was_redirected and url != final_url:
                    redirected_pages[url] = {"final_url": final_url, "linked_from": []}

                if html is None:
                    continue

                links = extract_internal_links(html, final_url, domain)
                page_link_counts[url] = len(links)
                pages_found_at_depth[depth].append(url)
                result["max_depth_reached"] = max(result["max_depth_reached"], depth)

                for link in links:
                    all_links.append(link)
                    pages_linking_to[link["url"]].add(url)

                    if link["url"] in broken_pages:
                        broken_pages[link["url"]]["linked_from"].append(url)
                    if link["url"] in soft_404_pages:
                        soft_404_pages[link["url"]]["linked_from"].append(url)
                    if link["url"] in server_error_pages:
                        server_error_pages[link["url"]]["linked_from"].append(url)

                    if link["nofollow"]:
                        result["nofollow_links"].append(link)

                    if link["url"] not in visited and depth + 1 <= max_depth:
                        queue.append((link["url"], depth + 1))

    for link in all_links:
        target = link["url"]
        source = link["source"]
        if target in broken_pages and source not in broken_pages[target]["linked_from"]:
            broken_pages[target]["linked_from"].append(source)
        if target in soft_404_pages and source not in soft_404_pages[target]["linked_from"]:
            soft_404_pages[target]["linked_from"].append(source)
        if target in server_error_pages and source not in server_error_pages[target]["linked_from"]:
            server_error_pages[target]["linked_from"].append(source)
        if target in redirected_pages and source not in redirected_pages[target]["linked_from"]:
            redirected_pages[target]["linked_from"].append(source)

    result["broken_internal_pages"] = [
        {"url": url, "status": info["status"], "linked_from": info["linked_from"][:5]}
        for url, info in broken_pages.items()
    ]
    result["soft_404_pages"] = [
        {"url": url, "linked_from": info["linked_from"][:5]}
        for url, info in soft_404_pages.items()
    ]
    result["server_error_pages"] = [
        {"url": url, "status": info["status"], "linked_from": info["linked_from"][:5]}
        for url, info in server_error_pages.items()
    ]
    result["redirected_pages"] = [
        {"url": url, "final_url": info["final_url"], "linked_from": info["linked_from"][:5]}
        for url, info in redirected_pages.items()
    ]

    result["pages_crawled"] = len(visited)
    result["total_internal_links"] = len(all_links)
    result["unique_pages_found"] = len(pages_linking_to)

    # Anchor text distribution
    anchor_counter = Counter(link["anchor_text"] for link in all_links if link["anchor_text"] != "[no text]")
    result["anchor_texts"] = dict(anchor_counter.most_common(20))

    # Link distribution (outgoing links per page)
    result["link_distribution"] = {
        "min": min(page_link_counts.values()) if page_link_counts else 0,
        "max": max(page_link_counts.values()) if page_link_counts else 0,
        "avg": round(sum(page_link_counts.values()) / max(1, len(page_link_counts)), 1),
    }

    # Pages info
    for url in visited:
        outgoing = page_link_counts.get(url, 0)
        incoming = len(pages_linking_to.get(url, set()))
        result["pages"][url] = {
            "outgoing_links": outgoing,
            "incoming_links": incoming,
        }

    # Orphan candidates (pages with 0 or 1 incoming links, excluding start)
    for url, sources in pages_linking_to.items():
        if url != start_url and len(sources) <= 1:
            result["orphan_candidates"].append({
                "url": url,
                "incoming_links": len(sources),
            })

    # Issues — broken/error pages first (highest severity)
    if result["broken_internal_pages"]:
        bp = result["broken_internal_pages"]
        urls_preview = ", ".join(p["url"] for p in bp[:3])
        result["issues"].append(
            f"🔴 {len(bp)} internal page(s) return 404/4xx: {urls_preview}"
        )

    if result["server_error_pages"]:
        sp = result["server_error_pages"]
        urls_preview = ", ".join(p["url"] for p in sp[:3])
        result["issues"].append(
            f"🔴 {len(sp)} internal page(s) return 5xx server errors: {urls_preview}"
        )

    if result["soft_404_pages"]:
        sf = result["soft_404_pages"]
        urls_preview = ", ".join(p["url"] for p in sf[:3])
        result["issues"].append(
            f"⚠️ {len(sf)} internal page(s) are soft 404s (return 200 but show "
            f"'not found' content): {urls_preview}"
        )

    if result["redirected_pages"]:
        rp = result["redirected_pages"]
        urls_preview = ", ".join(f"{p['url']} → {p['final_url']}" for p in rp[:2])
        result["issues"].append(
            f"⚠️ {len(rp)} internal link(s) point to redirect URLs: {urls_preview}"
        )

    if result["orphan_candidates"]:
        result["issues"].append(
            f"⚠️ {len(result['orphan_candidates'])} potential orphan page(s) "
            f"(≤1 internal link pointing to them)"
        )

    low_link_pages = [url for url, count in page_link_counts.items() if count < 3]
    if low_link_pages:
        result["issues"].append(
            f"⚠️ {len(low_link_pages)} page(s) have fewer than 3 internal links"
        )

    high_link_pages = [url for url, count in page_link_counts.items() if count > 100]
    if high_link_pages:
        result["issues"].append(
            f"⚠️ {len(high_link_pages)} page(s) have >100 internal links — may dilute link equity"
        )

    if result["nofollow_links"]:
        result["issues"].append(
            f"⚠️ {len(result['nofollow_links'])} internal link(s) have nofollow — "
            f"this wastes link equity"
        )

    no_text_links = sum(1 for l in all_links if l["anchor_text"] == "[no text]")
    if no_text_links:
        result["issues"].append(
            f"⚠️ {no_text_links} link(s) have no anchor text"
        )

    # Recommendations
    if result["broken_internal_pages"]:
        result["recommendations"].append(
            "Fix 404 internal pages: 301 redirect moved content, remove dead links, "
            "or restore deleted pages. Each broken internal link wastes crawl budget "
            "and breaks link equity flow."
        )
    if result["soft_404_pages"]:
        result["recommendations"].append(
            "Fix soft 404s: return a real 404/410 status code instead of 200 "
            "for pages that show 'not found' content."
        )
    if result["redirected_pages"]:
        result["recommendations"].append(
            "Update internal links that point to redirect URLs. Link directly "
            "to the final destination URL. GSC reports these as 'Page with "
            "redirect' — stale links waste crawl budget and dilute link equity."
        )
    if result["orphan_candidates"]:
        result["recommendations"].append(
            "Add internal links pointing to orphan pages from related content"
        )
    if result["link_distribution"]["avg"] < 5:
        result["recommendations"].append(
            "Increase internal linking — aim for 3-5 relevant links per 1000 words"
        )

    return result


def main():
    parser = argparse.ArgumentParser(description="Analyze internal link structure")
    parser.add_argument("url", help="Website URL (usually homepage)")
    parser.add_argument("--depth", "-d", type=int, default=2,
                        help="Max crawl depth (default: 2)")
    parser.add_argument("--max-pages", "-m", type=int, default=50,
                        help="Max pages to crawl (default: 50)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    result = crawl_site(args.url, max_depth=args.depth, max_pages=args.max_pages)

    if args.json:
        # Trim for readability
        output = {k: v for k, v in result.items()}
        # Convert sets to lists for JSON
        for url, info in output.get("pages", {}).items():
            if isinstance(info, set):
                output["pages"][url] = list(info)
        print(json.dumps(output, indent=2, default=str))
        return

    if result["error"]:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Internal Link Analysis — {result['domain']}")
    print("=" * 50)
    print(f"Pages crawled: {result['pages_crawled']}")
    print(f"Unique pages found: {result['unique_pages_found']}")
    print(f"Total internal links: {result['total_internal_links']}")
    print(f"Max depth reached: {result['max_depth_reached']}")

    dist = result["link_distribution"]
    print(f"\nLinks per page: min={dist['min']}, max={dist['max']}, avg={dist['avg']}")

    if result["broken_internal_pages"]:
        print(f"\n🔴 Broken Internal Pages ({len(result['broken_internal_pages'])}):")
        for bp in result["broken_internal_pages"][:10]:
            print(f"  • [{bp['status']}] {bp['url']}")
            for src in bp["linked_from"][:3]:
                print(f"        ← linked from {src}")

    if result["soft_404_pages"]:
        print(f"\n⚠️ Soft 404 Pages ({len(result['soft_404_pages'])}):")
        for sp in result["soft_404_pages"][:10]:
            print(f"  • {sp['url']}")

    if result["server_error_pages"]:
        print(f"\n🔴 Server Error Pages ({len(result['server_error_pages'])}):")
        for ep in result["server_error_pages"][:10]:
            print(f"  • [{ep['status']}] {ep['url']}")

    if result["redirected_pages"]:
        print(f"\n⚠️ Pages With Redirect ({len(result['redirected_pages'])}):")
        for rp in result["redirected_pages"][:10]:
            print(f"  • {rp['url']} → {rp['final_url']}")
            for src in rp["linked_from"][:3]:
                print(f"        ← linked from {src}")

    if result["orphan_candidates"]:
        print(f"\n⚠️ Potential Orphan Pages ({len(result['orphan_candidates'])}):")
        for orphan in result["orphan_candidates"][:10]:
            print(f"  • {orphan['url']} ({orphan['incoming_links']} incoming)")

    if result["anchor_texts"]:
        print(f"\nTop Anchor Texts:")
        for text, count in list(result["anchor_texts"].items())[:10]:
            print(f"  [{count}x] \"{text}\"")

    if result["nofollow_links"]:
        print(f"\n⚠️ Nofollow Internal Links ({len(result['nofollow_links'])}):")
        for link in result["nofollow_links"][:5]:
            print(f"  • {link['url']} (from {link['source']})")

    if result["issues"]:
        print(f"\nIssues:")
        for issue in result["issues"]:
            print(f"  {issue}")

    if result["recommendations"]:
        print(f"\nRecommendations:")
        for rec in result["recommendations"]:
            print(f"  💡 {rec}")


if __name__ == "__main__":
    main()
