#!/usr/bin/env python3
"""Render JavaScript-heavy pages for SEO checks when raw HTML is incomplete."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field

from url_safety import validate_url


SPA_MARKERS = (
    "__NEXT_DATA__",
    'id="__next"',
    "window.__NUXT__",
    'id="root"',
    'id="app"',
    "data-reactroot",
    "ng-version",
    "astro-island",
    "svelte",
)


@dataclass
class RenderResult:
    url: str
    final_url: str = ""
    html: str = ""
    status_code: int | None = None
    headers: dict = field(default_factory=dict)
    rendered: bool = False
    error: str | None = None


def should_render(html: str) -> bool:
    """Return True when raw HTML looks like a client-rendered shell."""
    if not html:
        return True
    lower = html.lower()
    marker_hit = any(marker.lower() in lower for marker in SPA_MARKERS)
    body_text = lower.split("<body", 1)[-1]
    visible_textish = " ".join(body_text.replace("<", " <").split())
    has_sparse_body = len(visible_textish) < 1200 and lower.count("<script") >= 2
    return marker_hit or has_sparse_body


def render_url(url: str, timeout: int = 30) -> RenderResult:
    """Render a URL with Playwright Chromium and return final DOM HTML."""
    safe = validate_url(url)
    result = RenderResult(url=url, final_url=safe.normalized_url or url)
    if not safe.ok:
        result.error = f"URL safety check failed: {safe.reason}"
        return result

    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        result.error = "Playwright not installed. Install with: pip install playwright && playwright install chromium"
        return result

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (compatible; UltimateSEO/1.8; +https://github.com/mykpono/ultimate-seo-geo)"
            )
            page = context.new_page()

            def _guard_route(route):
                request_url = route.request.url
                request_safe = validate_url(request_url)
                if request_safe.ok:
                    route.continue_()
                else:
                    route.abort()

            page.route("**/*", _guard_route)
            response = page.goto(safe.normalized_url, timeout=timeout * 1000, wait_until="networkidle")
            if response:
                result.status_code = response.status
                result.headers = response.all_headers()
            result.final_url = page.url
            final_safe = validate_url(result.final_url)
            if not final_safe.ok:
                result.error = f"Rendered page redirected to unsafe URL: {final_safe.reason}"
            else:
                result.html = page.content()
                result.rendered = True
            browser.close()
    except Exception as exc:
        result.error = f"Render failed: {exc}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a page with Playwright for SEO analysis")
    parser.add_argument("url", help="URL to render")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON metadata")
    args = parser.parse_args()

    result = render_url(args.url, timeout=args.timeout)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    elif result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1
    else:
        print(result.html)
        print(f"\nURL: {result.final_url}", file=sys.stderr)
        print(f"Status: {result.status_code}", file=sys.stderr)
    return 1 if result.error else 0


if __name__ == "__main__":
    raise SystemExit(main())

