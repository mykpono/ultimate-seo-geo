#!/usr/bin/env python3
"""
Fast URL discovery via sitemap parsing and internal link crawl.

Discovers all URLs on a site by checking robots.txt sitemaps,
standard sitemap paths, and BFS-crawling internal links.

Usage:
    python site_mapper.py https://example.com
    python site_mapper.py https://example.com --max-pages 200 --depth 3
    python site_mapper.py https://example.com --json
    python site_mapper.py https://example.com --include-status --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

from url_safety import is_crawlable_href

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)

try:
    from crawl_adapter import CrawlAdapter, CrawlResult
except ImportError:
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
    try:
        from crawl_adapter import CrawlAdapter, CrawlResult
    except ImportError:
        print("Error: crawl_adapter.py not found. Place it in the same directory.")
        sys.exit(1)


USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-SiteMapper/1.8)"

SITEMAP_GUESSES = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/sitemap1.xml",
]


def _normalize_url(url: str, domain: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != domain:
        return None
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return None
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if normalized.endswith("/") and len(parsed.path) > 1:
        normalized = normalized.rstrip("/")
    return normalized


def discover_sitemaps_from_robots(adapter: CrawlAdapter, base_url: str) -> list[str]:
    robots_url = f"{base_url}/robots.txt"
    result = adapter.fetch(robots_url, timeout=10)
    sitemap_urls = []
    if result.status_code == 200 and result.html:
        for line in result.html.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("sitemap:"):
                sm = stripped.split(":", 1)[1].strip()
                if sm:
                    sitemap_urls.append(sm)
    return sitemap_urls


def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page_urls, child_sitemap_urls) from a sitemap XML string."""
    page_urls: list[str] = []
    child_sitemaps: list[str] = []

    is_index = "<sitemapindex" in xml_text[:500].lower()

    if is_index:
        child_sitemaps = re.findall(
            r"<sitemap>\s*<loc>\s*([^<\s]+)\s*</loc>", xml_text, re.I
        )
    else:
        page_urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text, re.I)

    return page_urls, child_sitemaps


def collect_sitemap_urls(
    adapter: CrawlAdapter, base_url: str, max_sitemaps: int = 30
) -> list[str]:
    all_urls: list[str] = []
    seen_sitemaps: set[str] = set()
    queue: deque[str] = deque()

    robots_sitemaps = discover_sitemaps_from_robots(adapter, base_url)
    for sm in robots_sitemaps:
        queue.append(sm)

    for guess in SITEMAP_GUESSES:
        candidate = f"{base_url}{guess}"
        if candidate not in seen_sitemaps and candidate not in set(robots_sitemaps):
            queue.append(candidate)

    while queue and len(seen_sitemaps) < max_sitemaps:
        sm_url = queue.popleft()
        if sm_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sm_url)

        result = adapter.fetch(sm_url, timeout=12)
        if result.status_code != 200 or not result.html:
            continue

        if "<" not in result.html[:200]:
            continue

        page_urls, child_sitemaps = parse_sitemap(result.html)
        all_urls.extend(page_urls)

        for child in child_sitemaps:
            if child not in seen_sitemaps:
                queue.append(child)

    return all_urls


def extract_internal_links(html: str, page_url: str, domain: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not is_crawlable_href(href):
            continue
        absolute = urljoin(page_url, href)
        normalized = _normalize_url(absolute, domain)
        if normalized:
            links.add(normalized)

    return links


def crawl_internal_links(
    adapter: CrawlAdapter,
    start_url: str,
    domain: str,
    max_pages: int = 100,
    max_depth: int = 2,
    known_urls: set[str] | None = None,
) -> list[str]:
    visited: set[str] = set()
    discovered: set[str] = set(known_urls or set())
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        result = adapter.fetch(url, timeout=12)
        if result.error or not result.html:
            continue
        if result.status_code and result.status_code >= 400:
            continue
        content_type = result.headers.get("Content-Type", result.headers.get("content-type", ""))
        if content_type and "text/html" not in content_type:
            continue

        final_url = result.final_url or url
        links = extract_internal_links(result.html, final_url, domain)
        new_links = links - discovered
        discovered.update(new_links)

        if depth < max_depth:
            for link in new_links:
                if link not in visited:
                    queue.append((link, depth + 1))

    return sorted(discovered)


def check_url_status(
    adapter: CrawlAdapter, urls: list[str], max_workers: int = 8
) -> dict[str, int | None]:
    status_map: dict[str, int | None] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(adapter.fetch, url, 10): url for url in urls}
        for future in as_completed(futures):
            result: CrawlResult = future.result()
            status_map[result.url] = result.status_code

    return status_map


def map_site(
    url: str,
    max_pages: int = 100,
    max_depth: int = 2,
    include_status: bool = False,
    backend: str = "auto",
) -> dict:
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    domain = parsed.netloc

    adapter = CrawlAdapter(backend=backend)

    output: dict = {
        "url": url,
        "domain": domain,
        "urls_found": 0,
        "sources": {
            "sitemap": [],
            "crawl": [],
        },
        "all_urls": [],
        "status": {},
        "error": None,
    }

    sitemap_urls = collect_sitemap_urls(adapter, base_url)
    normalized_sitemap: list[str] = []
    seen: set[str] = set()
    for su in sitemap_urls:
        norm = _normalize_url(su, domain)
        if norm and norm not in seen:
            seen.add(norm)
            normalized_sitemap.append(norm)
    output["sources"]["sitemap"] = normalized_sitemap

    crawled_urls = crawl_internal_links(
        adapter,
        start_url=url,
        domain=domain,
        max_pages=max_pages,
        max_depth=max_depth,
        known_urls=seen,
    )

    crawl_only = sorted(set(crawled_urls) - seen)
    output["sources"]["crawl"] = crawl_only

    all_urls = sorted(seen | set(crawled_urls))
    output["all_urls"] = all_urls
    output["urls_found"] = len(all_urls)

    if include_status and all_urls:
        output["status"] = check_url_status(adapter, all_urls)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Discover all URLs on a site via sitemap + internal link crawl"
    )
    parser.add_argument("url", help="Site URL to map")
    parser.add_argument(
        "--max-pages", "-m", type=int, default=100,
        help="Maximum pages to crawl (default: 100)",
    )
    parser.add_argument(
        "--depth", "-d", type=int, default=2,
        help="BFS crawl depth (default: 2)",
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--include-status", action="store_true",
        help="Check HTTP status of each discovered URL",
    )
    parser.add_argument(
        "--backend", "-b", default="auto",
        help="Crawl backend: auto, requests, firecrawl, playwright (default: auto)",
    )
    args = parser.parse_args()

    result = map_site(
        args.url,
        max_pages=args.max_pages,
        max_depth=args.depth,
        include_status=args.include_status,
        backend=args.backend,
    )

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Site Map — {result['domain']}")
    print("=" * 50)
    print(f"Total URLs found: {result['urls_found']}")
    print(f"  From sitemaps: {len(result['sources']['sitemap'])}")
    print(f"  From crawl:    {len(result['sources']['crawl'])}")

    status_map = result.get("status", {})
    for label, key in [("Sitemap URLs", "sitemap"), ("Crawl-discovered URLs", "crawl")]:
        urls = result["sources"][key]
        if not urls:
            continue
        print(f"\n{label} ({len(urls)}):")
        for u in urls[:20]:
            suffix = f" [{status_map[u]}]" if u in status_map else ""
            print(f"  {u}{suffix}")
        if len(urls) > 20:
            print(f"  ... and {len(urls) - 20} more")

    errors = {u: s for u, s in status_map.items() if s and s >= 400}
    if errors:
        print(f"\n⚠️ URLs with errors ({len(errors)}):")
        for u, s in sorted(errors.items()):
            print(f"  [{s}] {u}")


if __name__ == "__main__":
    main()
