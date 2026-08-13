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


def validate_jsonld(content: str) -> List[str]:
    """Validate JSON-LD blocks in HTML content."""
    errors = []
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

    # Truly retired types — Google no longer processes these at all.
    # Safe to remove (but not urgent).
    retired = {
        "SpecialAnnouncement": "retired July 31, 2025 — Google no longer processes this type",
        "CourseInfo": "retired June 2025",
        "EstimatedSalary": "retired June 2025",
        "LearningVideo": "retired June 2025",
        "ClaimReview": "retired June 2025 — fact-check rich results discontinued",
        "VehicleListing": "retired June 2025 — vehicle listing structured data discontinued",
        "PracticeProblem": "retired late 2025 — rich results discontinued",
        "Dataset": "retired late 2025 — rich results discontinued",
    }
    if schema_type in retired:
        errors.append(f"{prefix}: @type '{schema_type}' is {retired[schema_type]}")

    # Rich-results-removed types — Google no longer shows rich results, but the
    # schema is still valid structured data. Keep it: helps Bing, AI systems,
    # and content understanding. Do NOT recommend removal.
    no_rich_results = {
        "HowTo": "Google removed HowTo rich results (Sept 2023) but schema is still valid — keep for Bing, AI systems, and content understanding",
    }
    if schema_type in no_rich_results:
        errors.append(f"[info] {prefix}: {no_rich_results[schema_type]}")

    # Check for restricted types used incorrectly
    restricted = {"FAQPage": "restricted to government and healthcare sites only (Aug 2023)"}
    if schema_type in restricted:
        errors.append(f"{prefix}: @type '{schema_type}' is {restricted[schema_type]} — verify site qualifies")

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

    errors = validate_jsonld(content)
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
