#!/usr/bin/env python3
"""
Fetch a web page with proper headers and error handling.

Usage:
    python fetch_page.py https://example.com
    python fetch_page.py https://example.com --output page.html
"""

import argparse
import sys
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

from render_page import render_url, should_render
from url_safety import validate_url


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UltimateSEO/1.8; +https://github.com/mykpono/ultimate-seo-geo)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def fetch_page(
    url: str,
    timeout: int = 30,
    follow_redirects: bool = True,
    max_redirects: int = 5,
    render: str = "never",
) -> dict:
    """
    Fetch a web page and return response details.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds
        follow_redirects: Whether to follow redirects
        max_redirects: Maximum number of redirects to follow

    Returns:
        Dictionary with:
            - url: Final URL after redirects
            - status_code: HTTP status code
            - content: Response body
            - headers: Response headers
            - redirect_chain: List of redirect URLs
            - rendered: Whether Playwright rendering supplied the content
            - error: Error message if failed
    """
    result = {
        "url": url,
        "status_code": None,
        "content": None,
        "headers": {},
        "redirect_chain": [],
        "rendered": False,
        "render_mode": render,
        "error": None,
    }

    if render not in {"never", "auto", "always"}:
        result["error"] = f"Invalid render mode: {render}"
        return result

    safe = validate_url(url)
    if not safe.ok:
        result["error"] = f"URL safety check failed: {safe.reason}"
        return result

    current_url = safe.normalized_url

    try:
        session = requests.Session()
        response = None
        for redirect_count in range(max_redirects + 1):
            safe_current = validate_url(current_url)
            if not safe_current.ok:
                result["error"] = f"URL safety check failed: {safe_current.reason}"
                return result

            response = session.get(
                safe_current.normalized_url,
                headers=DEFAULT_HEADERS,
                timeout=timeout,
                allow_redirects=False,
            )

            if not follow_redirects or not response.is_redirect:
                break

            location = response.headers.get("Location")
            if not location:
                break
            result["redirect_chain"].append(response.url)
            current_url = urljoin(response.url, location)
            if redirect_count == max_redirects:
                result["error"] = f"Too many redirects (max {max_redirects})"
                return result

        if response is None:
            result["error"] = "No response returned"
            return result

        result["url"] = response.url
        result["status_code"] = response.status_code
        result["content"] = response.text
        result["headers"] = dict(response.headers)

        if render == "always" or (render == "auto" and should_render(response.text)):
            rendered = render_url(response.url, timeout=timeout)
            if rendered.error:
                result["error"] = rendered.error
                return result
            result["url"] = rendered.final_url
            result["status_code"] = rendered.status_code
            result["content"] = rendered.html
            result["headers"] = rendered.headers
            result["rendered"] = True

    except requests.exceptions.Timeout:
        result["error"] = f"Request timed out after {timeout} seconds"
    except requests.exceptions.TooManyRedirects:
        result["error"] = f"Too many redirects (max {max_redirects})"
    except requests.exceptions.SSLError as e:
        result["error"] = f"SSL error: {e}"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error: {e}"
    except requests.exceptions.RequestException as e:
        result["error"] = f"Request failed: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch a web page for SEO analysis")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--no-redirects", action="store_true", help="Don't follow redirects")
    parser.add_argument(
        "--render",
        choices=["never", "auto", "always"],
        default="never",
        help="Render JavaScript-heavy pages with Playwright (default: never)",
    )

    args = parser.parse_args()

    result = fetch_page(
        args.url,
        timeout=args.timeout,
        follow_redirects=not args.no_redirects,
        render=args.render,
    )

    if result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result["content"])
        print(f"Saved to {args.output}")
    else:
        print(result["content"])

    # Print metadata to stderr
    print(f"\nURL: {result['url']}", file=sys.stderr)
    print(f"Status: {result['status_code']}", file=sys.stderr)
    print(f"Rendered: {result['rendered']}", file=sys.stderr)
    if result["redirect_chain"]:
        print(f"Redirects: {' -> '.join(result['redirect_chain'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
