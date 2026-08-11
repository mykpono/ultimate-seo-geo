#!/usr/bin/env python3
"""
Advanced local SEO / Maps intelligence: deep LocalBusiness schema audit,
NAP extraction, Google Maps embed detection, and GBP completeness scoring.

Extends local_signals_checker.py with richer analysis aligned to
references/procedures/25-maps-intelligence.md.

Usage:
    python maps_checker.py https://example.com
    python maps_checker.py https://example.com --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required — pip install requests"}))
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(json.dumps({"error": "beautifulsoup4 required — pip install beautifulsoup4"}))
    sys.exit(1)

try:
    from fetch_page import fetch_page
except ImportError:
    fetch_page = None

USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-Maps/1.10)"

PHONE_RE = re.compile(
    r"""
    (?:\+?1[-.\s]?)?          # optional country code
    (?:\(?\d{3}\)?[-.\s]?)    # area code
    \d{3}[-.\s]?\d{4}         # subscriber
    """,
    re.VERBOSE,
)

ADDRESS_RE = re.compile(
    r"\d{1,6}\s+"
    r"(?:[A-Z][a-z]+\s?){1,4}"
    r"(?:St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Dr(?:ive)?|Rd|Road|Ln|Lane|Way|Ct|Court|Pl(?:ace)?|Cir(?:cle)?)"
    r"\.?",
    re.IGNORECASE,
)

GBP_SCHEMA_FIELDS = {
    "critical": ["name", "@type", "address"],
    "high": ["telephone", "openingHoursSpecification", "geo", "url"],
    "medium": ["image", "priceRange", "areaServed", "sameAs", "description"],
    "low": ["review", "aggregateRating", "hasMap", "menu", "acceptsReservations"],
}


def _fetch(url: str) -> dict:
    """Fetch the URL, preferring the project's fetch_page when available."""
    if fetch_page is not None:
        result = fetch_page(url, timeout=20)
        if result.get("error"):
            return {"error": result["error"], "html": "", "status": None}
        return {"html": result.get("content", ""), "status": result.get("status_code"), "error": None}

    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
        return {"html": r.text or "", "status": r.status_code, "error": None}
    except Exception as exc:
        return {"error": str(exc), "html": "", "status": None}


def _extract_jsonld_blocks(soup: BeautifulSoup) -> list[dict]:
    """Extract all JSON-LD blocks from the page."""
    blocks: list[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            if isinstance(data, list):
                blocks.extend(data)
            elif isinstance(data, dict):
                if data.get("@graph"):
                    blocks.extend(data["@graph"])
                else:
                    blocks.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    return blocks


def _find_local_schemas(blocks: list[dict]) -> list[dict]:
    """Return JSON-LD objects whose @type is LocalBusiness or a subtype."""
    lb_types = {
        "localbusiness", "restaurant", "dentist", "attorney", "autobody",
        "autorepair", "bakery", "barorsalon", "beautysalon", "cafe",
        "dentist", "drycleaningorlaundry", "electrician", "florist",
        "gym", "hairsalon", "healthclub", "hotel", "insuranceagency",
        "legalservice", "library", "locksmith", "medicalclinic", "motel",
        "movingcompany", "notary", "optician", "petstore", "pharmacy",
        "physician", "plumber", "realestateagent", "recyclingcenter",
        "selfstorge", "shoppingcenter", "sportsclub", "store", "travelagency",
        "veterinarycare",
    }
    results = []
    for block in blocks:
        block_type = block.get("@type", "")
        if isinstance(block_type, list):
            types = [t.lower() for t in block_type]
        else:
            types = [block_type.lower()]
        if any(t in lb_types for t in types):
            results.append(block)
    return results


def _audit_schema_completeness(schema: dict) -> list[dict]:
    """Audit a LocalBusiness JSON-LD block against the GBP checklist."""
    issues: list[dict] = []

    def _has(key: str) -> bool:
        val = schema.get(key)
        if val is None:
            return False
        if isinstance(val, str) and not val.strip():
            return False
        return True

    for severity, fields in GBP_SCHEMA_FIELDS.items():
        for field in fields:
            if field == "@type":
                continue
            if not _has(field):
                issues.append({
                    "severity": severity,
                    "finding": f"LocalBusiness schema missing '{field}'.",
                    "fix": f"Add '{field}' to the LocalBusiness JSON-LD block.",
                })

    addr = schema.get("address", {})
    if isinstance(addr, dict):
        for part in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"):
            if not addr.get(part):
                issues.append({
                    "severity": "high",
                    "finding": f"Address missing '{part}'.",
                    "fix": f"Add '{part}' to the PostalAddress inside LocalBusiness.",
                })

    geo = schema.get("geo", {})
    if isinstance(geo, dict):
        if not geo.get("latitude") or not geo.get("longitude"):
            issues.append({
                "severity": "medium",
                "finding": "Geo coordinates incomplete (missing latitude or longitude).",
                "fix": "Add latitude and longitude to the GeoCoordinates block.",
            })

    ohs = schema.get("openingHoursSpecification")
    if isinstance(ohs, list) and len(ohs) < 5:
        issues.append({
            "severity": "medium",
            "finding": f"Only {len(ohs)} openingHoursSpecification entries — likely missing some days.",
            "fix": "Include openingHoursSpecification for all 7 days of the week.",
        })

    return issues


def _extract_nap_from_html(soup: BeautifulSoup) -> dict[str, list[str]]:
    """Extract Name/Address/Phone candidates from visible page text."""
    text = soup.get_text(separator="\n")
    phones = list(set(PHONE_RE.findall(text)))[:10]
    addresses = list(set(ADDRESS_RE.findall(text)))[:10]
    return {"phones": phones, "addresses": addresses}


def _check_nap_format_issues(nap: dict[str, list[str]]) -> list[dict]:
    """Flag common NAP format inconsistencies."""
    issues: list[dict] = []
    formats_seen: set[str] = set()
    for phone in nap["phones"]:
        stripped = re.sub(r"[^\d]", "", phone)
        if "(" in phone:
            fmt = "parens"
        elif "-" in phone:
            fmt = "dashes"
        elif "." in phone:
            fmt = "dots"
        else:
            fmt = "plain"
        formats_seen.add(fmt)

    if len(formats_seen) > 1:
        issues.append({
            "severity": "medium",
            "finding": f"Multiple phone number formats detected on page: {', '.join(sorted(formats_seen))}.",
            "fix": "Standardize all phone numbers to a single format (e.g., (555) 123-4567).",
        })

    for addr in nap["addresses"]:
        if re.search(r"\bSte\b", addr) and re.search(r"\bSuite\b", addr):
            issues.append({
                "severity": "low",
                "finding": "Mixed 'Suite' / 'Ste' abbreviations in addresses.",
                "fix": "Use one consistent abbreviation across all address mentions.",
            })
            break

    return issues


def _detect_maps_embeds(soup: BeautifulSoup) -> dict[str, Any]:
    """Detect Google Maps embeds and links."""
    iframes = soup.find_all("iframe")
    maps_iframes = [
        iframe.get("src", "")
        for iframe in iframes
        if "google.com/maps" in (iframe.get("src", "") or "").lower()
    ]

    maps_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "google.com/maps" in href.lower() or "maps.app.goo.gl" in href.lower():
            maps_links.append(href)

    return {
        "maps_embed_count": len(maps_iframes),
        "maps_link_count": len(maps_links),
        "has_maps_presence": bool(maps_iframes or maps_links),
    }


def _detect_service_area(soup: BeautifulSoup) -> dict[str, Any]:
    """Check for service area indicators."""
    text_lower = soup.get_text(separator=" ").lower()
    indicators = []
    for phrase in ("service area", "serving", "we serve", "areas we serve", "coverage area", "locations served"):
        if phrase in text_lower:
            indicators.append(phrase)
    return {
        "service_area_indicators": indicators[:5],
        "has_service_area_signals": bool(indicators),
    }


def check_maps(url: str) -> dict:
    """Run the full maps / local intelligence check."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"

    fetched = _fetch(url)
    if fetched["error"]:
        return {"error": fetched["error"], "url": url}

    html = fetched["html"]
    status = fetched["status"]
    soup = BeautifulSoup(html, "html.parser")

    jsonld = _extract_jsonld_blocks(soup)
    local_schemas = _find_local_schemas(jsonld)

    schema_issues: list[dict] = []
    schema_fields_summary: list[dict] = []
    for idx, schema in enumerate(local_schemas):
        audit = _audit_schema_completeness(schema)
        schema_issues.extend(audit)
        schema_fields_summary.append({
            "index": idx,
            "type": schema.get("@type"),
            "name": schema.get("name", "[not set]"),
            "fields_present": [k for k in schema if k != "@context"],
        })

    nap = _extract_nap_from_html(soup)
    nap_issues = _check_nap_format_issues(nap)
    maps = _detect_maps_embeds(soup)
    service_area = _detect_service_area(soup)

    all_issues = schema_issues + nap_issues
    if not local_schemas:
        has_local_signals = bool(nap["phones"] or nap["addresses"] or maps["has_maps_presence"])
        if has_local_signals:
            all_issues.insert(0, {
                "severity": "critical",
                "finding": "Local business signals detected but no LocalBusiness JSON-LD schema found.",
                "fix": "Add LocalBusiness (or specific subtype) JSON-LD with full NAP, geo, hours, and images.",
            })

    if not maps["has_maps_presence"] and local_schemas:
        all_issues.append({
            "severity": "low",
            "finding": "LocalBusiness schema present but no Google Maps embed or link on page.",
            "fix": "Consider embedding a Google Maps iframe or linking to your Google Maps listing.",
        })

    tel_links = len(soup.find_all("a", href=re.compile(r"^tel:", re.I)))
    if local_schemas and tel_links == 0:
        all_issues.append({
            "severity": "medium",
            "finding": "LocalBusiness schema present but no clickable tel: links on page.",
            "fix": "Add tel: links in the header/footer for mobile users.",
        })

    critical = sum(1 for i in all_issues if i["severity"] == "critical")
    high = sum(1 for i in all_issues if i["severity"] == "high")
    medium = sum(1 for i in all_issues if i["severity"] == "medium")

    score: int | None = 100
    score -= critical * 20
    score -= high * 8
    score -= medium * 3
    score = max(0, score)

    if not local_schemas and not nap["phones"] and not nap["addresses"] and not maps["has_maps_presence"]:
        score = None

    return {
        "url": url,
        "http_status": status,
        "local_business_schemas": schema_fields_summary,
        "local_schema_count": len(local_schemas),
        "nap": {
            "phones_found": nap["phones"][:5],
            "addresses_found": nap["addresses"][:5],
            "phone_count": len(nap["phones"]),
            "address_count": len(nap["addresses"]),
        },
        "maps": maps,
        "service_area": service_area,
        "tel_links": tel_links,
        "score": score,
        "issues": all_issues[:30],
        "issue_summary": {"critical": critical, "high": high, "medium": medium},
    }


def _format_text(data: dict) -> str:
    """Human-readable text output."""
    lines = [
        f"Maps Intelligence Report — {data['url']}",
        f"HTTP Status: {data.get('http_status', 'N/A')}",
        "",
    ]

    if data.get("error"):
        lines.append(f"Error: {data['error']}")
        return "\n".join(lines)

    score = data.get("score")
    lines.append(f"Local SEO Score: {score}/100" if score is not None else "Local SEO Score: N/A (not a local business)")
    lines.append(f"LocalBusiness schemas found: {data['local_schema_count']}")
    lines.append(f"Phones detected: {data['nap']['phone_count']}")
    lines.append(f"Addresses detected: {data['nap']['address_count']}")
    lines.append(f"Maps presence: {'Yes' if data['maps']['has_maps_presence'] else 'No'}")
    lines.append(f"Service area signals: {'Yes' if data['service_area']['has_service_area_signals'] else 'No'}")
    lines.append("")

    if data["local_business_schemas"]:
        lines.append("--- LocalBusiness Schema Details ---")
        for s in data["local_business_schemas"]:
            lines.append(f"  [{s['index']}] {s['type']} — {s['name']}")
            lines.append(f"      Fields: {', '.join(s['fields_present'])}")
        lines.append("")

    if data["issues"]:
        lines.append("--- Issues ---")
        for issue in data["issues"]:
            sev = issue["severity"].upper()
            lines.append(f"  [{sev}] {issue['finding']}")
            lines.append(f"         Fix: {issue['fix']}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Maps intelligence & advanced local SEO checker"
    )
    parser.add_argument("url", help="URL to analyze (typically homepage or location page)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    data = check_maps(args.url)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(_format_text(data))


if __name__ == "__main__":
    main()
