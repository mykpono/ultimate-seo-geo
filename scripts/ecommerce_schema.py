#!/usr/bin/env python3
"""
Validate e-commerce schema markup on product and category pages.

Checks Product + Offer schema completeness, MerchantReturnPolicy,
OfferShippingDetails, and page-type classification.

Usage:
    python ecommerce_schema.py https://example.com/product-page
    python ecommerce_schema.py https://example.com/category-page --json
"""

import argparse
import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

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

from fetch_page import fetch_page
from url_safety import validate_url


ECOMMERCE_PATH_SIGNALS = [
    "/products/", "/product/", "/shop/", "/store/",
    "/item/", "/p/", "/dp/", "/catalog/", "/buy/",
]

CART_SIGNALS = ["/cart", "/checkout", "/basket", "/bag"]

ADD_TO_CART_PATTERNS = [
    r"add[\s_-]?to[\s_-]?cart",
    r"buy[\s_-]?now",
    r"add[\s_-]?to[\s_-]?bag",
    r"add[\s_-]?to[\s_-]?basket",
    r"purchase",
]

AVAILABILITY_VALUES = {
    "https://schema.org/InStock",
    "https://schema.org/OutOfStock",
    "https://schema.org/PreOrder",
    "https://schema.org/BackOrder",
    "https://schema.org/Discontinued",
    "https://schema.org/LimitedAvailability",
    "https://schema.org/InStoreOnly",
    "https://schema.org/OnlineOnly",
    "https://schema.org/SoldOut",
    "http://schema.org/InStock",
    "http://schema.org/OutOfStock",
    "http://schema.org/PreOrder",
    "http://schema.org/BackOrder",
    "http://schema.org/Discontinued",
    "http://schema.org/LimitedAvailability",
    "http://schema.org/InStoreOnly",
    "http://schema.org/OnlineOnly",
    "http://schema.org/SoldOut",
}


def extract_jsonld(html: str) -> list[dict]:
    """Extract all JSON-LD blocks from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string
        if not text:
            continue
        try:
            data = json.loads(text.strip())
            blocks.append(data)
        except json.JSONDecodeError:
            continue
    return blocks


def flatten_schema_objects(blocks: list[dict]) -> list[dict]:
    """Flatten JSON-LD blocks into individual schema objects."""
    objects = []
    for block in blocks:
        if isinstance(block, list):
            objects.extend(block)
        elif isinstance(block, dict):
            if "@graph" in block and isinstance(block["@graph"], list):
                objects.extend(
                    item for item in block["@graph"] if isinstance(item, dict)
                )
            else:
                objects.append(block)
    return objects


def classify_page_type(url: str, html: str, schema_objects: list[dict]) -> str:
    """Classify page as product, category, cart, or other."""
    path = urlparse(url).path.lower()

    for signal in CART_SIGNALS:
        if signal in path:
            return "cart"

    schema_types: set[str] = set()
    for obj in schema_objects:
        t = obj.get("@type", "")
        if isinstance(t, list):
            schema_types.update(t)
        else:
            schema_types.add(t)

    if "Product" in schema_types:
        return "product"
    if "CollectionPage" in schema_types or "ItemList" in schema_types:
        return "category"

    for signal in ECOMMERCE_PATH_SIGNALS:
        if signal in path:
            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text().lower()
            for pattern in ADD_TO_CART_PATTERNS:
                if re.search(pattern, text_content, re.IGNORECASE):
                    return "product"
            return "category"

    soup = BeautifulSoup(html, "html.parser")
    text_content = soup.get_text().lower()
    for pattern in ADD_TO_CART_PATTERNS:
        if re.search(pattern, text_content, re.IGNORECASE):
            return "product"

    if path in ("/", "/index.html", ""):
        return "homepage"

    return "other"


def _get_type(obj: dict) -> set[str]:
    """Get @type as a set (handles string or list)."""
    t = obj.get("@type", "")
    if isinstance(t, list):
        return set(t)
    return {t}


def validate_product_schema(obj: dict) -> list[dict]:
    """Validate a Product schema object."""
    findings = []

    required = ["name", "description", "image", "offers"]
    for field in required:
        if field not in obj:
            findings.append({
                "finding": f"Product schema missing required field: {field}",
                "severity": "critical",
                "fix": f"Add '{field}' to Product schema. See references/procedures/24-ecommerce-seo.md",
            })

    if "brand" not in obj:
        findings.append({
            "finding": "Product schema missing 'brand'",
            "severity": "warning",
            "fix": "Add 'brand' with brand name or Organization reference",
        })

    has_identifier = any(k in obj for k in ("sku", "gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn"))
    if not has_identifier:
        findings.append({
            "finding": "Product schema missing product identifier (sku/gtin/mpn)",
            "severity": "critical",
            "fix": "Add at least one of: sku, gtin, or mpn. Required for Google Merchant features.",
        })

    # Added to the merchant listing documentation on 2026-07-07. Accepts either a
    # Text path or a CategoryCode; both are valid, so only absence is reportable.
    if "category" not in obj:
        findings.append({
            "finding": "Product schema missing 'category'",
            "severity": "info",
            "fix": (
                "Add 'category' to Product schema (documented 2026-07-07). Accepts Text "
                "(e.g. 'Apparel > Shoes > Running') or a CategoryCode. Match the value the "
                "Merchant Center feed sends — a feed and markup that disagree is a defect."
            ),
        })

    offers = obj.get("offers")
    if offers:
        if isinstance(offers, dict):
            findings.extend(validate_offer_schema(offers))
        elif isinstance(offers, list):
            for offer in offers:
                if isinstance(offer, dict):
                    findings.extend(validate_offer_schema(offer))

    return findings


def _validate_sale_duration(obj: dict) -> list[dict]:
    """Check sale-price effective dates.

    Google documented a "Sale duration" section on 2026-07-07: a sale price is
    expressed with a nested priceSpecification carrying validFrom/validThrough.
    An open-ended sale price cannot be shown as a time-bound sale.

    Only fires when the markup actually claims a sale. A plain price needs no
    date range, so absence of priceSpecification is not itself a finding.
    """
    findings = []
    spec = obj.get("priceSpecification")
    specs = [spec] if isinstance(spec, dict) else [s for s in (spec or []) if isinstance(s, dict)]

    for s in specs:
        price_type = str(s.get("priceType", ""))
        if "SalePrice" not in price_type:
            continue
        missing = [f for f in ("validFrom", "validThrough") if f not in s]
        if missing:
            findings.append({
                "finding": (
                    f"Sale priceSpecification missing {' and '.join(missing)}"
                ),
                "severity": "warning",
                "fix": (
                    "Add 'validFrom' and 'validThrough' (ISO 8601) to the SalePrice "
                    "priceSpecification. Documented 2026-07-07 — without an effective range "
                    "the sale price cannot be presented as time-bound."
                ),
            })

    return findings


def validate_offer_schema(obj: dict) -> list[dict]:
    """Validate an Offer or AggregateOffer schema object."""
    findings = []
    types = _get_type(obj)

    if not types.intersection({"Offer", "AggregateOffer"}):
        findings.append({
            "finding": "Offer object missing @type (should be 'Offer' or 'AggregateOffer')",
            "severity": "warning",
            "fix": "Add '@type': 'Offer' to the offers object",
        })

    if "AggregateOffer" in types:
        for field in ("lowPrice", "highPrice", "priceCurrency"):
            if field not in obj:
                findings.append({
                    "finding": f"AggregateOffer missing '{field}'",
                    "severity": "warning",
                    "fix": f"Add '{field}' to AggregateOffer schema",
                })
    else:
        if "price" not in obj:
            findings.append({
                "finding": "Offer schema missing 'price'",
                "severity": "critical",
                "fix": "Add 'price' with numeric value to Offer schema",
            })

        if "priceCurrency" not in obj:
            findings.append({
                "finding": "Offer schema missing 'priceCurrency'",
                "severity": "critical",
                "fix": "Add 'priceCurrency' (ISO 4217 code, e.g. 'USD') to Offer schema",
            })

    findings.extend(_validate_sale_duration(obj))

    if "availability" not in obj:
        findings.append({
            "finding": "Offer schema missing 'availability'",
            "severity": "warning",
            "fix": "Add 'availability' using schema.org ItemAvailability value (e.g. https://schema.org/InStock)",
        })
    else:
        avail = obj["availability"]
        if avail not in AVAILABILITY_VALUES:
            findings.append({
                "finding": f"Offer 'availability' uses non-standard value: {avail}",
                "severity": "warning",
                "fix": "Use a valid schema.org availability value (InStock, OutOfStock, PreOrder, BackOrder, Discontinued)",
            })

    if "url" not in obj:
        findings.append({
            "finding": "Offer schema missing 'url'",
            "severity": "info",
            "fix": "Add 'url' pointing to the canonical product page",
        })

    return findings


def validate_merchant_return_policy(obj: dict) -> list[dict]:
    """Validate MerchantReturnPolicy schema."""
    findings = []

    if "returnPolicyCountry" not in obj:
        findings.append({
            "finding": "MerchantReturnPolicy missing 'returnPolicyCountry' (required since March 2025)",
            "severity": "critical",
            "fix": "Add 'returnPolicyCountry' with ISO 3166-1 alpha-2 country code",
        })

    if "returnPolicyCategory" not in obj:
        findings.append({
            "finding": "MerchantReturnPolicy missing 'returnPolicyCategory'",
            "severity": "warning",
            "fix": "Add 'returnPolicyCategory' (e.g. MerchantReturnFiniteReturnWindow, MerchantReturnNotPermitted)",
        })

    category = obj.get("returnPolicyCategory", "")
    if "FiniteReturnWindow" in str(category) and "merchantReturnDays" not in obj:
        findings.append({
            "finding": "MerchantReturnPolicy with finite window missing 'merchantReturnDays'",
            "severity": "warning",
            "fix": "Add 'merchantReturnDays' specifying the return period in days",
        })

    return findings


def validate_shipping_details(obj: dict) -> list[dict]:
    """Validate OfferShippingDetails schema."""
    findings = []

    if "shippingRate" not in obj:
        findings.append({
            "finding": "OfferShippingDetails missing 'shippingRate'",
            "severity": "warning",
            "fix": "Add 'shippingRate' as MonetaryAmount with value and currency",
        })

    if "deliveryTime" not in obj:
        findings.append({
            "finding": "OfferShippingDetails missing 'deliveryTime'",
            "severity": "warning",
            "fix": "Add 'deliveryTime' with ShippingDeliveryTime (handlingTime, transitTime)",
        })

    if "shippingDestination" not in obj:
        findings.append({
            "finding": "OfferShippingDetails missing 'shippingDestination'",
            "severity": "warning",
            "fix": "Add 'shippingDestination' as DefinedRegion with addressCountry",
        })

    return findings


def validate_aggregate_rating(obj: dict) -> list[dict]:
    """Validate AggregateRating schema."""
    findings = []

    if "ratingValue" not in obj:
        findings.append({
            "finding": "AggregateRating missing 'ratingValue'",
            "severity": "critical",
            "fix": "Add 'ratingValue' — required for review stars in search results",
        })

    if "reviewCount" not in obj and "ratingCount" not in obj:
        findings.append({
            "finding": "AggregateRating missing 'reviewCount' or 'ratingCount'",
            "severity": "warning",
            "fix": "Add 'reviewCount' (number of reviews) or 'ratingCount' (number of ratings)",
        })

    # Google added a review snippet guideline on 2026-07-24 barring fake and
    # undisclosed incentivized reviews, globally rather than only under EU UCP.
    # No script can tell from markup whether a review was incentivized or whether
    # the page discloses it, so this is a manual verification prompt, not a
    # detected defect -- reporting it as a defect would violate the evidence rule
    # in references/procedures/19-quality-gates-hard-rules.md (rule 1).
    findings.append({
        "finding": "Review policy requires manual verification (not detectable from markup)",
        "severity": "info",
        "requires_manual_check": True,
        "fix": (
            "Confirm with the site owner: (1) every marked-up review reflects genuine "
            "experience of the product; (2) any review given in exchange for money, "
            "discounts, vouchers or free products is disclosed clearly and prominently on "
            "the page, not only in the markup. Guideline added 2026-07-24, global. "
            "Disclosed incentivized reviews are permitted -- the defect is missing "
            "disclosure, so do not recommend deleting a compliant programme."
        ),
    })

    return findings


def validate_breadcrumb(obj: dict) -> list[dict]:
    """Validate BreadcrumbList schema."""
    findings = []

    items = obj.get("itemListElement", [])
    if not items:
        findings.append({
            "finding": "BreadcrumbList has no itemListElement entries",
            "severity": "warning",
            "fix": "Add itemListElement array with ListItem objects for each breadcrumb level",
        })
        return findings

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if "position" not in item:
            findings.append({
                "finding": f"BreadcrumbList item {i+1} missing 'position'",
                "severity": "warning",
                "fix": "Add 'position' (integer) to each ListItem in BreadcrumbList",
            })
        if "name" not in item and "item" not in item:
            findings.append({
                "finding": f"BreadcrumbList item {i+1} missing 'name' or 'item'",
                "severity": "warning",
                "fix": "Add 'name' and/or 'item' (URL) to each ListItem",
            })

    return findings


def validate_category_page(schema_objects: list[dict]) -> list[dict]:
    """Validate schema for category pages."""
    findings = []

    has_collection = any(
        "CollectionPage" in _get_type(obj) or "ItemList" in _get_type(obj)
        for obj in schema_objects
    )
    has_product = any("Product" in _get_type(obj) for obj in schema_objects)

    if has_product:
        findings.append({
            "finding": "Category page has Product schema (should use CollectionPage or ItemList)",
            "severity": "warning",
            "fix": "Replace Product schema with CollectionPage or ItemList on category pages. "
                   "Product schema should only appear on individual product detail pages.",
        })

    if not has_collection:
        findings.append({
            "finding": "Category page missing CollectionPage or ItemList schema",
            "severity": "info",
            "fix": "Add CollectionPage or ItemList schema with product references",
        })

    return findings


def run_audit(url: str) -> dict:
    """Run full e-commerce schema audit on a URL."""
    safe = validate_url(url)
    if not safe.ok:
        return {
            "url": url,
            "error": f"URL safety check failed: {safe.reason}",
            "page_type": "unknown",
            "findings": [],
            "schema_objects_found": 0,
            "score": 0,
        }

    result = fetch_page(safe.normalized_url, timeout=30)
    if result.get("error"):
        return {
            "url": url,
            "error": result["error"],
            "page_type": "unknown",
            "findings": [],
            "schema_objects_found": 0,
            "score": 0,
        }

    html = result.get("content", "")
    if not html:
        return {
            "url": url,
            "error": "Empty response body",
            "page_type": "unknown",
            "findings": [],
            "schema_objects_found": 0,
            "score": 0,
        }

    jsonld_blocks = extract_jsonld(html)
    schema_objects = flatten_schema_objects(jsonld_blocks)
    page_type = classify_page_type(url, html, schema_objects)

    findings: list[dict] = []

    has_breadcrumb = False
    has_product = False
    has_return_policy = False
    has_shipping = False
    has_aggregate_rating = False

    for obj in schema_objects:
        types = _get_type(obj)

        if "Product" in types:
            has_product = True
            findings.extend(validate_product_schema(obj))

        if "Offer" in types or "AggregateOffer" in types:
            findings.extend(validate_offer_schema(obj))

        if "MerchantReturnPolicy" in types:
            has_return_policy = True
            findings.extend(validate_merchant_return_policy(obj))

        if "OfferShippingDetails" in types:
            has_shipping = True
            findings.extend(validate_shipping_details(obj))

        if "AggregateRating" in types:
            has_aggregate_rating = True
            findings.extend(validate_aggregate_rating(obj))

        if "BreadcrumbList" in types:
            has_breadcrumb = True
            findings.extend(validate_breadcrumb(obj))

    if page_type == "product":
        if not has_product:
            findings.append({
                "finding": "Product page detected but no Product schema found",
                "severity": "critical",
                "fix": "Add Product + Offer JSON-LD schema. See references/procedures/24-ecommerce-seo.md",
            })

        if not has_breadcrumb:
            findings.append({
                "finding": "Product page missing BreadcrumbList schema",
                "severity": "warning",
                "fix": "Add BreadcrumbList schema showing category hierarchy",
            })

        if not has_return_policy:
            findings.append({
                "finding": "No MerchantReturnPolicy schema found (required for merchant listing features since March 2025)",
                "severity": "warning",
                "fix": "Add MerchantReturnPolicy with returnPolicyCountry and returnPolicyCategory",
            })

        if not has_shipping:
            findings.append({
                "finding": "No OfferShippingDetails schema found",
                "severity": "info",
                "fix": "Add OfferShippingDetails for shipping info display in search results",
            })

    elif page_type == "category":
        findings.extend(validate_category_page(schema_objects))
        if not has_breadcrumb:
            findings.append({
                "finding": "Category page missing BreadcrumbList schema",
                "severity": "warning",
                "fix": "Add BreadcrumbList schema showing category hierarchy",
            })

    critical_count = sum(1 for f in findings if f["severity"] == "critical")
    warning_count = sum(1 for f in findings if f["severity"] == "warning")

    score = 100
    score -= critical_count * 15
    score -= warning_count * 5
    score = max(0, min(100, score))

    return {
        "url": safe.normalized_url,
        "page_type": page_type,
        "schema_objects_found": len(schema_objects),
        "jsonld_blocks": len(jsonld_blocks),
        "has_product_schema": has_product,
        "has_breadcrumb": has_breadcrumb,
        "has_return_policy": has_return_policy,
        "has_shipping_details": has_shipping,
        "has_aggregate_rating": has_aggregate_rating,
        "findings": findings,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "info_count": sum(1 for f in findings if f["severity"] == "info"),
        "score": score,
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate e-commerce schema markup (Product, Offer, MerchantReturnPolicy, shipping)",
        epilog="Examples:\n"
               "  python ecommerce_schema.py https://example.com/products/widget\n"
               "  python ecommerce_schema.py https://example.com/category/shoes --json\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="URL to check for e-commerce schema")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    result = run_audit(args.url)

    if args.json:
        print(json.dumps(result, indent=2))
        sys.exit(0)

    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        sys.exit(1)

    print(f"🛒 E-commerce Schema Audit: {result['url']}")
    print(f"   Page type: {result['page_type']}")
    print(f"   JSON-LD blocks: {result['jsonld_blocks']}")
    print(f"   Schema objects: {result['schema_objects_found']}")
    print(f"   Score: {result['score']}/100")
    print()

    if result["page_type"] == "product":
        checks = [
            ("Product schema", result["has_product_schema"]),
            ("BreadcrumbList", result["has_breadcrumb"]),
            ("MerchantReturnPolicy", result["has_return_policy"]),
            ("OfferShippingDetails", result["has_shipping_details"]),
            ("AggregateRating", result["has_aggregate_rating"]),
        ]
        print("   Schema presence:")
        for name, present in checks:
            icon = "✅" if present else "❌"
            print(f"     {icon} {name}")
        print()

    findings = result["findings"]
    if not findings:
        print("   ✅ No issues found")
        sys.exit(0)

    critical = [f for f in findings if f["severity"] == "critical"]
    warnings = [f for f in findings if f["severity"] == "warning"]
    info = [f for f in findings if f["severity"] == "info"]

    if critical:
        print(f"   🔴 Critical ({len(critical)}):")
        for f in critical:
            print(f"     • {f['finding']}")
            print(f"       Fix: {f['fix']}")
        print()

    if warnings:
        print(f"   🟠 Warnings ({len(warnings)}):")
        for f in warnings:
            print(f"     • {f['finding']}")
            print(f"       Fix: {f['fix']}")
        print()

    if info:
        print(f"   🔵 Info ({len(info)}):")
        for f in info:
            print(f"     • {f['finding']}")
            print(f"       Fix: {f['fix']}")

    sys.exit(2 if critical else 1 if warnings else 0)


if __name__ == "__main__":
    main()
