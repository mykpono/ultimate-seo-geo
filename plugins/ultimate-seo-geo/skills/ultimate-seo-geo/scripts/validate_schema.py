#!/usr/bin/env python3
"""Post-edit schema validation helper.

Validates JSON-LD schema after file edits. Returns exit code 2 to block
if critical validation errors found.

Example usage:
  python3 validate_schema.py path/to/file.html
"""

import argparse
import json
import os
import re
import sys
from typing import List

import faq_parity

# Module-level so tests/test_schema_status_parity.py can check these against
# the tables in references/schema-types.md. Docs and code may only drift by
# failing CI.
#
# Truly retired — Google no longer processes these at all. Safe to remove.
RETIRED_TYPES = {
    "SpecialAnnouncement": "retired July 31, 2025 — Google no longer processes this type",
    "CourseInfo": "retired June 2025",
    "EstimatedSalary": "retired June 2025",
    "LearningVideo": "retired June 2025",
    "ClaimReview": "retired June 2025 — fact-check rich results discontinued",
    "VehicleListing": "retired June 2025 — vehicle listing structured data discontinued",
    "EnergyConsumptionDetails": "retired April 24, 2025 — replaced by the Certification type",
}

# Rich results removed, but the schema is still valid structured data. Keep it:
# helps Bing, AI systems and content understanding. Never recommend removal
# (references/procedures/19-quality-gates-hard-rules.md rule 10).
NO_RICH_RESULTS_TYPES = {
    "HowTo": "Google removed HowTo rich results (Sept 2023) but schema is still valid — keep for Bing, AI systems, and content understanding",
    "FAQPage": "Google withdrew FAQ rich results for all sites (May 7, 2026) but schema is still valid — keep as an AI/entity signal; do not remove",
    "Dataset": "Dataset markup is consumed by Dataset Search only, not general Google Search (clarified Nov 5, 2025) — still valid and supported; keep it",
    "Quiz": "Google retired the practice problem rich result (Jan 2026) but schema.org Quiz is still valid — keep for Bing, AI systems, and content understanding",
}


def validate_jsonld(content: str, check_html_parity: bool = False) -> List[str]:
    """Validate JSON-LD blocks in HTML content.

    `check_html_parity` compares FAQ answer text against the rendered HTML.
    Off by default and gated to .html/.htm by main(): on .jsx/.tsx/.vue/
    .svelte/.php the answer text legitimately lives in props, a .map() or a
    CMS fetch, so absence from the file proves nothing.
    """
    errors = []
    page_text = faq_parity.visible_text(content) if check_html_parity else None
    # `type` may sit anywhere in the tag and is rarely the only attribute:
    # Yoast emits class="yoast-schema-graph", Next.js and Shopify commonly add
    # id=. Requiring `type` to be the sole attribute silently extracted nothing
    # on those sites and returned a clean bill of health.
    pattern = (
        r'<script\b[^>]*?\btype\s*=\s*["\']application/ld\+json["\'][^>]*>'
        r'(.*?)</script>'
    )
    blocks = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

    if not blocks:
        return []  # No schema found — not an error

    for i, block in enumerate(blocks, 1):
        block = block.strip()
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            errors.append(f"Block {i}: Invalid JSON — {e}")
            continue

        if page_text is not None:
            errors.extend(_check_faq_parity(data, i, page_text))

        if isinstance(data, list):
            for item in data:
                errors.extend(_validate_schema_object(item, i))
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                # Graph members inherit @context from the wrapper; only the
                # wrapper is required to declare it (JSON-LD 1.1 sec 4.9).
                for item in data["@graph"]:
                    if isinstance(item, dict):
                        errors.extend(
                            _validate_schema_object(item, i, require_context=False)
                        )
                if "@context" not in data:
                    errors.append(f"Block {i}: Missing @context")
            else:
                errors.extend(_validate_schema_object(data, i))

    return errors


def _validate_schema_object(
    obj: dict, block_num: int, require_context: bool = True
) -> List[str]:
    """Validate a single schema object.

    ``require_context`` is False for @graph members, which inherit the
    wrapper's context rather than declaring their own.
    """
    errors = []
    prefix = f"Block {block_num}"

    # Check @context
    if "@context" not in obj:
        if require_context:
            errors.append(f"{prefix}: Missing @context")
    elif obj["@context"] not in ("https://schema.org", "http://schema.org"):
        errors.append(f"{prefix}: @context should be 'https://schema.org'")

    if "@type" not in obj and "@graph" not in obj:
        errors.append(f"{prefix}: Missing @type")

    # Check for placeholder text
    placeholders = [
        "[Business Name]",
        "[City]",
        "[State]",
        "[Phone]",
        "[Address]",
        "[Your",
        "[INSERT",
        # Was the bare string "REPLACE", matched case-insensitively against the
        # whole serialized object, so an article headlined "How to Replace a
        # Faucet" was reported as containing placeholder text — which
        # _is_critical() treats as critical and main() exits 2 on.
        "[REPLACE",
        "REPLACE_ME",
        "REPLACE WITH",
        "[URL]",
        "[Email]",
    ]
    text = json.dumps(obj)
    for p in placeholders:
        if p.lower() in text.lower():
            errors.append(f"{prefix}: Contains placeholder text: {p}")

    schema_type = obj.get("@type", "")

    if schema_type in RETIRED_TYPES:
        errors.append(f"{prefix}: @type '{schema_type}' is {RETIRED_TYPES[schema_type]}")

    if schema_type in NO_RICH_RESULTS_TYPES:
        errors.append(f"[info] {prefix}: {NO_RICH_RESULTS_TYPES[schema_type]}")

    return errors


def _check_faq_parity(data, block_index: int, page_text: str) -> List[str]:
    """Flag FAQ answers present in JSON-LD but absent from the rendered HTML.

    Emitted with the [info] prefix so _is_critical() returns False and this
    check can never block an edit. This script has no High/Medium vocabulary;
    High severity for the same finding lives in parse_html.py/article_seo.py,
    which run against fetched pages where absence is a real signal.
    """
    candidates = []
    if isinstance(data, dict):
        candidates = data.get("@graph") if isinstance(data.get("@graph"), list) else [data]
    elif isinstance(data, list):
        candidates = data

    errors = []
    for obj in candidates:
        for question in faq_parity.missing_answers(obj, page_text):
            errors.append(
                f"[info] Block {block_index}: FAQ answer for {question!r} is in the "
                f"JSON-LD but not in the rendered HTML — invisible to users and AI "
                f"crawlers. Render the answer text on the page (see procedures/03 step 4)."
            )
    return errors


def _is_critical(msg: str) -> bool:
    if msg.startswith("[info]"):
        return False
    low = msg.lower()
    return any(k in low for k in ("placeholder", "retired"))


def main():
    parser = argparse.ArgumentParser(description="Validate JSON-LD in HTML")
    parser.add_argument("path", nargs="?", help="Path to HTML (or HTML-like) file")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON on stdout (exit 0)",
    )
    args = parser.parse_args()

    if not args.path:
        if args.json:
            print(json.dumps({"error": "no_path", "schema_errors": [], "jsonld_blocks": 0}))
        sys.exit(0)

    filepath = args.path
    valid_extensions = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".ejs")
    if not os.path.isfile(filepath):
        if args.json:
            print(json.dumps({"error": "not_found", "path": filepath, "schema_errors": []}))
        sys.exit(0)

    if not filepath.endswith(valid_extensions):
        if args.json:
            print(
                json.dumps(
                    {
                        "error": "unsupported_extension",
                        "path": filepath,
                        "schema_errors": [],
                    }
                )
            )
        sys.exit(0)

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except (OSError, IOError):
        if args.json:
            print(json.dumps({"error": "read_failed", "path": filepath, "schema_errors": []}))
        sys.exit(0)

    # Parity only on real HTML — framework templates legitimately hold answer
    # text outside the file (props, .map(), CMS fetch).
    errors = validate_jsonld(
        content, check_html_parity=filepath.lower().endswith((".html", ".htm"))
    )
    block_count = len(
        re.findall(
            r'<script\s+type=["\']application/ld\+json["\']',
            content,
            re.IGNORECASE,
        )
    )

    if args.json:
        critical_ct = sum(1 for e in errors if _is_critical(e))
        issues = []
        for e in errors[:40]:
            issues.append(
                {
                    "finding": e,
                    "severity": "critical" if _is_critical(e) else "warning",
                    "fix": "Fix JSON-LD per references/schema-types.md",
                }
            )
        score = 100
        if block_count == 0:
            score = 55  # informational — not all pages need schema
        score = max(0, score - len(errors) * 8 - critical_ct * 12)
        payload = {
            "path": filepath,
            "jsonld_blocks": block_count,
            "schema_errors": errors,
            "error_count": len(errors),
            "critical_count": critical_ct,
            "score": min(100, score),
            "issues": issues,
            "recommendations": (
                ["No JSON-LD blocks found — add relevant schema where applicable."]
                if block_count == 0
                else []
            ),
        }
        print(json.dumps(payload))
        sys.exit(0)

    if not errors:
        sys.exit(0)

    critical = [e for e in errors if _is_critical(e)]
    warnings = [e for e in errors if e not in critical]

    if warnings:
        print("⚠️  Schema validation warnings:")
        for w in warnings:
            print(f"  - {w}")

    if critical:
        print("🛑 Schema validation ERRORS (blocking):")
        for e in critical:
            print(f"  - {e}")
        sys.exit(2)

    sys.exit(1)


if __name__ == "__main__":
    main()
