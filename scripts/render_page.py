#!/usr/bin/env python3
"""Render JavaScript-heavy pages for SEO checks when raw HTML is incomplete."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit, urlunsplit

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
    network: list = field(default_factory=list)


AUTH_HEADERS = ("authorization", "x-api-key", "api-key", "x-auth-token", "x-access-token")
CORS_HEADERS = ("access-control-allow-origin", "access-control-allow-credentials", "access-control-allow-methods")


def strip_query(url: str) -> str:
    """The URL without query string or fragment: tracker hits carry emails and ids in them."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def network_entry(request, response) -> dict:
    """One request as recorded: no query string, no header values except CORS and content type."""
    headers = {k.lower(): v for k, v in (request.headers or {}).items()}
    entry = {
        "url": strip_query(request.url),
        "method": request.method,
        "resource_type": request.resource_type,
        "has_auth_header": any(h in headers for h in AUTH_HEADERS),
        "request_content_type": headers.get("content-type"),
        "status": None,
        "cors": {},
        "content_type": None,
    }
    if response is not None:
        entry["status"] = response.status
        rh = {k.lower(): v for k, v in (response.headers or {}).items()}
        entry["cors"] = {h: rh[h] for h in CORS_HEADERS if h in rh}
        entry["content_type"] = rh.get("content-type")
    return entry


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


def render_url(url: str, timeout: int = 30, capture_network: bool = False) -> RenderResult:
    """Render a URL with Playwright Chromium and return final DOM HTML.

    With capture_network, result.network lists every request the page made (see network_entry).
    """
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
            if capture_network:
                def _record(req):
                    try:
                        resp = req.response()
                    except Exception:  # the request failed or was aborted: record it without a response
                        resp = None
                    result.network.append(network_entry(req, resp))

                page.on("requestfinished", _record)
                def _failed(req):
                    entry = network_entry(req, None)
                    entry["failure"] = req.failure  # e.g. net::ERR_ABORTED for beacons cut off at navigation end
                    result.network.append(entry)

                page.on("requestfailed", _failed)
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
    parser.add_argument("--network", action="store_true", help="Also record the requests the page makes (JSON output)")
    args = parser.parse_args()

    result = render_url(args.url, timeout=args.timeout, capture_network=args.network)
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

