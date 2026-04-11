#!/usr/bin/env python3
"""
Parse HTML and extract SEO-relevant elements.

Usage:
    python parse_html.py page.html
    python parse_html.py --url https://example.com
"""

import argparse
import json
import os
import re
import sys
from typing import Optional
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)


def _link_rel_has_canonical(rel) -> bool:
    if rel is None:
        return False
    if isinstance(rel, list):
        rel_s = " ".join(rel).lower()
    else:
        rel_s = str(rel).lower()
    return "canonical" in rel_s.split()


def _canonical_hrefs(soup: BeautifulSoup) -> list:
    hrefs = []
    for link in soup.find_all("link"):
        if not _link_rel_has_canonical(link.get("rel")):
            continue
        h = (link.get("href") or "").strip()
        if h:
            hrefs.append(h)
    return hrefs


def parse_html(html: str, base_url: Optional[str] = None) -> dict:
    """
    Parse HTML and extract SEO-relevant elements.

    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative links

    Returns:
        Dictionary with extracted SEO data
    """
    soup = BeautifulSoup(html, "lxml" if "lxml" in sys.modules else "html.parser")

    result = {
        "title": None,
        "meta_description": None,
        "meta_description_source": None,
        "meta_robots": None,
        "canonical": None,
        "h1": [],
        "h2": [],
        "h3": [],
        "images": [],
        "links": {
            "internal": [],
            "external": [],
        },
        "schema": [],
        "open_graph": {},
        "twitter_card": {},
        "word_count": 0,
        "hreflang": [],
        "issues": [],
    }

    # Title
    title_tags = soup.find_all("title")
    if title_tags:
        result["title"] = title_tags[0].get_text(strip=True)
    if len(title_tags) > 1:
        result["issues"].append({
            "severity": "critical",
            "finding": f"Multiple <title> tags in HTML ({len(title_tags)}).",
            "fix": "Keep a single <title> per document; remove duplicates from templates or injected fragments.",
        })

    # Meta tags
    meta_desc_count = 0
    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        property_attr = meta.get("property", "").lower()
        content = meta.get("content", "")

        if name == "description":
            meta_desc_count += 1
            if str(content).strip() and (
                result["meta_description"] is None or not str(result["meta_description"]).strip()
            ):
                result["meta_description"] = content
        elif name == "robots":
            result["meta_robots"] = content

        # Open Graph
        if property_attr.startswith("og:"):
            result["open_graph"][property_attr] = content

        # Twitter Card
        if name.startswith("twitter:"):
            result["twitter_card"][name] = content

    if meta_desc_count > 1:
        result["issues"].append({
            "severity": "critical",
            "finding": f"Multiple meta name=\"description\" tags ({meta_desc_count}).",
            "fix": "Use exactly one meta description; search engines may pick unpredictably among duplicates.",
        })

    if result["meta_description"] is not None and str(result["meta_description"]).strip():
        result["meta_description_source"] = "name"
    else:
        og_desc = (result["open_graph"].get("og:description") or "").strip()
        if og_desc:
            result["meta_description"] = og_desc
            result["meta_description_source"] = "og_fallback"
            result["issues"].append({
                "severity": "info",
                "finding": "No meta name=\"description\"; using og:description as fallback for audit display.",
                "fix": "Add a dedicated meta name=\"description\" for SERP control; og:description is primarily for social previews.",
            })

    # Canonical
    canon_hrefs = _canonical_hrefs(soup)
    if len(canon_hrefs) > 1:
        result["issues"].append({
            "severity": "critical",
            "finding": f"Multiple rel=canonical link tags ({len(canon_hrefs)}).",
            "fix": "Keep exactly one canonical URL per page.",
        })
    if canon_hrefs:
        result["canonical"] = canon_hrefs[0]

    # Hreflang
    for link in soup.find_all("link", rel="alternate"):
        hreflang = link.get("hreflang")
        if hreflang:
            result["hreflang"].append({
                "lang": hreflang,
                "href": link.get("href"),
            })

    # Headings
    for tag in ["h1", "h2", "h3"]:
        for heading in soup.find_all(tag):
            text = heading.get_text(strip=True)
            if text:
                result[tag].append(text)

    if len(result["h1"]) > 1:
        result["issues"].append({
            "severity": "info",
            "finding": f"Multiple H1 elements in raw HTML ({len(result['h1'])}).",
            "fix": "Confirm the live rendered page has one primary H1 (DevTools); demote extras to H2 if needed.",
        })

    # Images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if base_url and src:
            src = urljoin(base_url, src)

        result["images"].append({
            "src": src,
            "alt": img.get("alt"),
            "width": img.get("width"),
            "height": img.get("height"),
            "loading": img.get("loading"),
        })

    # Links
    if base_url:
        base_domain = urlparse(base_url).netloc

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            link_data = {
                "href": full_url,
                "text": a.get_text(strip=True)[:100],
                "rel": a.get("rel", []),
            }

            if parsed.netloc == base_domain:
                result["links"]["internal"].append(link_data)
            else:
                result["links"]["external"].append(link_data)

    # Schema (JSON-LD) — enhanced with type validation
    DEPRECATED_SCHEMA = {
        "HowTo", "SpecialAnnouncement", "CourseInfo", "EstimatedSalary",
        "LearningVideo", "ClaimReview", "VehicleListing", "PracticeProblems",
    }
    RESTRICTED_SCHEMA = {"FAQPage"}  # government/healthcare only

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            schema_data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            result["schema"].append({
                "error": "invalid_json",
                "raw_snippet": (script.string or "")[:120],
            })
            continue

        schema_type = schema_data.get("@type", "Unknown")
        status = "active"
        note = ""

        if schema_type in DEPRECATED_SCHEMA:
            status = "deprecated"
            note = f"{schema_type} was deprecated/removed from rich results. Remove or replace."
        elif schema_type in RESTRICTED_SCHEMA:
            status = "restricted"
            note = f"{schema_type} is restricted to government/healthcare authority sites only."

        result["schema"].append({
            "@type": schema_type,
            "@context": schema_data.get("@context", ""),
            "status": status,
            "note": note,
            "has_context": bool(schema_data.get("@context")),
            "has_type": bool(schema_data.get("@type")),
            "raw": schema_data,
        })

    # Word count (visible text only)
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()

    text = soup.get_text(separator=" ", strip=True)
    words = re.findall(r"\b\w+\b", text)
    result["word_count"] = len(words)

    return result


def main():
    parser = argparse.ArgumentParser(description="Parse HTML for SEO analysis")
    parser.add_argument("file", nargs="?", help="HTML file to parse")
    parser.add_argument("--url", "-u", help="Base URL for resolving links")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.file:
        real_path = os.path.realpath(args.file)
        if not os.path.isfile(real_path):
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(real_path, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        html = sys.stdin.read()

    result = parse_html(html, args.url)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Title: {result['title']}")
        print(f"Meta Description: {result['meta_description']}")
        print(f"Canonical: {result['canonical']}")
        print(f"H1 Tags: {len(result['h1'])}")
        print(f"H2 Tags: {len(result['h2'])}")
        print(f"Images: {len(result['images'])}")
        print(f"Internal Links: {len(result['links']['internal'])}")
        print(f"External Links: {len(result['links']['external'])}")
        print(f"Schema Blocks: {len(result['schema'])}")
        print(f"Word Count: {result['word_count']}")


if __name__ == "__main__":
    main()
