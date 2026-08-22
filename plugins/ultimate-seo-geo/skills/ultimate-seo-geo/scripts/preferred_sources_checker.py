#!/usr/bin/env python3
"""
Check whether a page offers Google's "preferred sources" opt-in, and whether the
URL is even eligible to be one.

CONTEXT
-------
Preferred sources let a reader mark a publication as one they want to see more of.
Selected sites get a "preferred" badge and more prominent placement in Top Stories,
and -- since the Top Stories carousel went live inside AI Overviews on July 17, 2026
-- can surface inside AI answers on developing-news queries. Google documented a
custom interactive button for the opt-in on August 20, 2026.

This is the only AI-answer visibility lever the *reader* controls rather than the
ranking system, which is why it is worth auditing on publisher sites.

SCOPE
-----
This is a news/publisher lever, reported at INFO severity. Its absence is a missed
opportunity, never a defect: a site that never appears in Top Stories has nothing to
opt into. Do not raise it as a finding on a site that publishes no dated news-style
content. See references/ai-search-geo.md, "Preferred Sources".

ELIGIBILITY
-----------
Selection is host-level. https://www.example.com/ and https://code.example.com/ can
be chosen; https://www.example.com/blog cannot. A publication living in a
subdirectory is structurally ineligible -- that is a migration decision, not a fix.

Dependency-free: standard library only, matching scripts/faq_parity.py.

Usage:
    python preferred_sources_checker.py https://example.com
    python preferred_sources_checker.py https://example.com/article --json
"""

import argparse
import json
import re
import sys
import urllib.request
from urllib.parse import urlparse

try:
    from url_safety import validate_url
except ImportError:  # pragma: no cover - defensive, mirrors content_brief.py
    validate_url = None

USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO/1.12; +preferred-sources-check)"

PUBLISHER_JS = "news.google.com/swg/js/v1/publisher.js"

# The documented button placeholder. Attribute may appear bare or valued, and
# frameworks routinely reorder or add attributes, so match the attribute itself.
BUTTON_ATTR_RE = re.compile(r"google-add-preferred-source-btn", re.I)

# Deeplink route, for pages that cannot run the script.
DEEPLINK_RE = re.compile(
    r"https?://(?:www\.)?google\.com/preferences/source\?q=([^\"'\s>&]+)", re.I
)

# The advanced route drives the flow programmatically rather than via the div.
ADVANCED_API_RE = re.compile(
    r"\b(?:addPreferredSource|SWG_BASIC|swgBasic)\b"
)


def _fetch(url: str, timeout: int = 15) -> tuple[str, str, int]:
    """Return (final_url, html, status). Empty html on any failure."""
    target = url
    if validate_url is not None:
        safe = validate_url(url)
        if not safe.ok:
            return url, "", 0
        target = safe.normalized_url or url
    try:
        req = urllib.request.Request(target, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.url, resp.read().decode("utf-8", errors="ignore"), resp.status
    except Exception:
        return url, "", 0


def check_eligibility(url: str) -> dict:
    """Host-level eligibility. Subdirectories cannot be preferred sources."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc
    path = parsed.path or "/"
    # Trailing-slash-only paths are the host itself.
    is_host_level = path in ("", "/")
    canonical = f"{parsed.scheme or 'https'}://{host}/"
    return {
        "host": host,
        "path": path,
        "url_is_host_level": is_host_level,
        "eligible_entity": canonical,
        "note": (
            f"Eligible as a preferred source: {canonical}"
            if is_host_level
            else (
                f"The URL points at a subdirectory ({path}). Preferred sources are selected at "
                f"host level only, so readers would be choosing {canonical}, not this section. "
                "A publication that needs to be chosen independently must live on its own "
                "subdomain -- a migration decision, not a quick fix."
            )
        ),
    }


def check_preferred_sources(url: str, timeout: int = 15) -> dict:
    """Detect all three documented integration routes on a page."""
    final_url, html, status = _fetch(url, timeout)

    result = {
        "url": url,
        "final_url": final_url,
        "status": status,
        "severity": "info",
        "eligibility": check_eligibility(url),
        "integration": {
            "publisher_js": False,
            "button_element": False,
            "deeplink": False,
            "advanced_api": False,
        },
        "deeplink_targets": [],
        "implemented": False,
        "error": "",
    }

    if not html:
        result["error"] = (
            f"Could not fetch {url}" + (f" (HTTP {status})" if status else "")
        )
        return result

    result["integration"]["publisher_js"] = PUBLISHER_JS in html
    result["integration"]["button_element"] = bool(BUTTON_ATTR_RE.search(html))
    deeplinks = DEEPLINK_RE.findall(html)
    result["integration"]["deeplink"] = bool(deeplinks)
    result["deeplink_targets"] = sorted(set(deeplinks))
    result["integration"]["advanced_api"] = bool(ADVANCED_API_RE.search(html))

    result["implemented"] = any(result["integration"].values())
    return result


def build_findings(result: dict) -> list[dict]:
    """Info-severity findings only. Absence is an opportunity, not a defect."""
    findings = []
    integ = result["integration"]

    if result["error"]:
        return findings

    if not result["implemented"]:
        findings.append({
            "severity": "info",
            "finding": "No preferred sources opt-in found on the page",
            "impact": (
                "Readers have no in-page way to mark this publication as a preferred source. "
                "Preferred sources drive the 'preferred' badge and more prominent Top Stories "
                "placement, and since July 17, 2026 can surface inside AI Overviews on "
                "developing-news queries."
            ),
            "fix": (
                "Add the documented two-line button near existing reader intent (article footer "
                "or newsletter module):\n"
                '<script async src="https://news.google.com/swg/js/v1/publisher.js"></script>\n'
                "<div google-add-preferred-source-btn></div>"
            ),
            "applies_to": "News and publisher sites only — skip if the site publishes no dated news content.",
        })
    elif integ["button_element"] and not integ["publisher_js"]:
        findings.append({
            "severity": "warning",
            "finding": "Preferred sources button element present but publisher.js is not loaded",
            "impact": (
                "The <div google-add-preferred-source-btn> placeholder renders nothing without "
                "the Google publisher script. The opt-in is silently broken."
            ),
            "fix": (
                'Add <script async src="https://news.google.com/swg/js/v1/publisher.js"></script> '
                "before the button element."
            ),
            "applies_to": "Any page carrying the button element.",
        })

    if not result["eligibility"]["url_is_host_level"]:
        findings.append({
            "severity": "info",
            "finding": "Audited URL is not host-level — preferred sources apply to the whole host",
            "impact": result["eligibility"]["note"],
            "fix": (
                f"Verify the opt-in against the host itself: {result['eligibility']['eligible_entity']}"
            ),
            "applies_to": "Informational — clarifies what a reader would actually be selecting.",
        })

    return findings


def print_human(result: dict) -> None:
    print(f"Preferred Sources Check — {result['url']}")
    print("=" * 62)

    if result["error"]:
        print(f"Error: {result['error']}")
        sys.exit(1)

    elig = result["eligibility"]
    mark = "✅" if elig["url_is_host_level"] else "➖"
    print(f"Eligibility: {mark} {elig['note']}")
    print()

    integ = result["integration"]
    print("Integration routes detected:")
    for label, key in (
        ("publisher.js loaded", "publisher_js"),
        ("button element", "button_element"),
        ("deeplink", "deeplink"),
        ("advanced JS API", "advanced_api"),
    ):
        print(f"  {'✅' if integ[key] else '➖'} {label}")

    if result["deeplink_targets"]:
        print("\nDeeplink targets:")
        for target in result["deeplink_targets"]:
            print(f"  {target}")

    findings = build_findings(result)
    if findings:
        print("\nFindings:")
        for f in findings:
            print(f"  [{f['severity']}] {f['finding']}")
            print(f"      {f['applies_to']}")

    print(
        "\nNote: preferred sources is a news/publisher lever, reported at INFO severity."
        "\nAbsence is a missed opportunity, not a defect. Do not raise it on a site that"
        "\npublishes no dated news-style content."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Check for Google preferred sources opt-in and host-level eligibility"
    )
    parser.add_argument("url", help="Page URL to check")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--timeout", type=int, default=15, help="Fetch timeout in seconds")

    args = parser.parse_args()
    result = check_preferred_sources(args.url, args.timeout)

    if args.json:
        result["findings"] = build_findings(result)
        print(json.dumps(result, indent=2))
        sys.exit(1 if result["error"] else 0)

    print_human(result)


if __name__ == "__main__":
    main()
