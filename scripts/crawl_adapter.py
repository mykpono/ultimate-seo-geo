#!/usr/bin/env python3
"""
Unified crawl interface with pluggable backends.

Abstraction layer that other scripts use for fetching pages.
Supports requests (stdlib), firecrawl, and playwright backends.

Usage:
    python crawl_adapter.py https://example.com
    python crawl_adapter.py https://example.com --backend playwright
    python crawl_adapter.py https://example.com --json --timeout 20
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Optional
from urllib.parse import urljoin

import requests

from render_page import render_url
from url_safety import validate_url


USER_AGENT = (
    "Mozilla/5.0 (compatible; UltimateSEO/1.8; "
    "+https://github.com/mykpono/ultimate-seo-geo)"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

_BACKENDS = ("requests", "firecrawl", "playwright")


@dataclass
class CrawlResult:
    url: str
    final_url: str = ""
    html: str = ""
    status_code: Optional[int] = None
    headers: dict = field(default_factory=dict)
    rendered: bool = False
    error: Optional[str] = None


def _detect_backend() -> str:
    if os.environ.get("FIRECRAWL_API_KEY"):
        return "firecrawl"
    return "requests"


def _fetch_requests(url: str, timeout: int = 15) -> CrawlResult:
    result = CrawlResult(url=url)
    safe = validate_url(url)
    if not safe.ok:
        result.error = f"URL safety check failed: {safe.reason}"
        return result

    current_url = safe.normalized_url
    try:
        session = requests.Session()
        response = None
        for redirect_count in range(6):
            safe_current = validate_url(current_url)
            if not safe_current.ok:
                result.error = f"URL safety check failed: {safe_current.reason}"
                return result
            response = session.get(
                safe_current.normalized_url,
                timeout=timeout,
                headers=DEFAULT_HEADERS,
                allow_redirects=False,
            )
            if not response.is_redirect:
                break
            location = response.headers.get("Location")
            if not location:
                break
            current_url = urljoin(response.url, location)
            if redirect_count == 5:
                result.error = "Too many redirects (max 5)"
                return result

        if response is None:
            result.error = "No response returned"
            return result
        result.status_code = response.status_code
        result.final_url = response.url
        result.headers = dict(response.headers)
        result.html = response.text
    except requests.exceptions.Timeout:
        result.error = f"Request timed out after {timeout}s"
    except requests.exceptions.RequestException as e:
        result.error = f"Fetch failed: {e}"
    return result


def _fetch_firecrawl(url: str, timeout: int = 15) -> CrawlResult:
    safe = validate_url(url)
    if not safe.ok:
        return CrawlResult(url=url, error=f"URL safety check failed: {safe.reason}")

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        print(
            "Firecrawl backend selected but FIRECRAWL_API_KEY not set. "
            "Falling back to requests backend.",
            file=sys.stderr,
        )
        return _fetch_requests(url, timeout)

    try:
        from firecrawl import FirecrawlApp  # type: ignore
        app = FirecrawlApp(api_key=api_key)
        response = app.scrape_url(safe.normalized_url)
        final_url = response.get("metadata", {}).get("url", safe.normalized_url)
        final_safe = validate_url(final_url)
        if not final_safe.ok:
            return CrawlResult(url=url, error=f"Firecrawl returned unsafe URL: {final_safe.reason}")
        return CrawlResult(
            url=url,
            final_url=final_url,
            html=response.get("html", response.get("content", "")),
            status_code=response.get("metadata", {}).get("statusCode", 200),
            headers=response.get("metadata", {}).get("headers", {}),
        )
    except ImportError:
        print(
            "Firecrawl SDK not installed. Install with: pip install firecrawl-py\n"
            "Or use the Firecrawl MCP server. Falling back to requests backend.",
            file=sys.stderr,
        )
        return _fetch_requests(url, timeout)
    except Exception as e:
        print(f"Firecrawl error: {e}. Falling back to requests backend.", file=sys.stderr)
        return _fetch_requests(url, timeout)


def _fetch_playwright(url: str, timeout: int = 15) -> CrawlResult:
    rendered = render_url(url, timeout=timeout)
    if rendered.error and "Playwright not installed" in rendered.error:
        print(
            "Playwright not installed. Install with: pip install playwright && "
            "playwright install chromium\nFalling back to requests backend.",
            file=sys.stderr,
        )
        return _fetch_requests(url, timeout)
    return CrawlResult(
        url=url,
        final_url=rendered.final_url,
        html=rendered.html,
        status_code=rendered.status_code,
        headers=rendered.headers,
        rendered=rendered.rendered,
        error=rendered.error,
    )


_BACKEND_MAP = {
    "requests": _fetch_requests,
    "firecrawl": _fetch_firecrawl,
    "playwright": _fetch_playwright,
}


class CrawlAdapter:
    """Unified crawl interface with pluggable backends."""

    def __init__(self, backend: str = "requests"):
        if backend == "auto":
            backend = _detect_backend()
        if backend not in _BACKENDS:
            raise ValueError(f"Unknown backend '{backend}'. Choose from: {_BACKENDS}")
        self.backend = backend
        self._fetch_fn = _BACKEND_MAP[backend]

    def fetch(self, url: str, timeout: int = 15) -> CrawlResult:
        return self._fetch_fn(url, timeout)

    def fetch_many(
        self, urls: list[str], max_workers: int = 5, timeout: int = 15
    ) -> list[CrawlResult]:
        results: list[CrawlResult] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._fetch_fn, url, timeout): url for url in urls
            }
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def __repr__(self) -> str:
        return f"CrawlAdapter(backend={self.backend!r})"


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a page using the unified crawl adapter"
    )
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument(
        "--backend", "-b",
        choices=["auto", *_BACKENDS],
        default="auto",
        help="Crawl backend (default: auto-detect)",
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--timeout", "-t", type=int, default=15, help="Timeout in seconds (default: 15)"
    )
    args = parser.parse_args()

    adapter = CrawlAdapter(backend=args.backend)
    result = adapter.fetch(args.url, timeout=args.timeout)

    if args.json:
        print(json.dumps(asdict(result), indent=2, default=str))
        return

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(result.html)
    print(f"\nBackend: {adapter.backend}", file=sys.stderr)
    print(f"URL: {result.final_url}", file=sys.stderr)
    print(f"Status: {result.status_code}", file=sys.stderr)
    print(f"Size: {len(result.html)} bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
