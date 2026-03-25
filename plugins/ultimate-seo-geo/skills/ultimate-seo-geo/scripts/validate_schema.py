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
    pattern = r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>'
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
            errors.extend(_validate_schema_object(data, i))

    return errors


def _validate_schema_object(obj: dict, block_num: int) -> List[str]:
    """Validate a single schema object."""
    errors = []
    prefix = f"Block {block_num}"

    # Check @context
    if "@context" not in obj:
        errors.append(f"{prefix}: Missing @context")
    elif obj["@context"] not in ("https://schema.org", "http://schema.org"):
        errors.append(f"{prefix}: @context should be 'https://schema.org'")

    # Check @type
    if "@type" not in obj:
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
        "REPLACE",
        "[URL]",
        "[Email]",
    ]
    text = json.dumps(obj)
    for p in placeholders:
        if p.lower() in text.lower():
            errors.append(f"{prefix}: Contains placeholder text: {p}")

    # Check for deprecated types
    schema_type = obj.get("@type", "")
    deprecated = {
        "HowTo": "deprecated September 2023",
        "SpecialAnnouncement": "deprecated July 31, 2025",
        "CourseInfo": "retired June 2025",
        "EstimatedSalary": "retired June 2025",
        "LearningVideo": "retired June 2025",
        "ClaimReview": "retired June 2025 — fact-check rich results discontinued",
        "VehicleListing": "retired June 2025 — vehicle listing structured data discontinued",
        "PracticeProblem": "retired late 2025 — rich results discontinued",
        "Dataset": "retired late 2025 — rich results discontinued",
    }
    if schema_type in deprecated:
        errors.append(f"{prefix}: @type '{schema_type}' is {deprecated[schema_type]}")

    # Check for restricted types used incorrectly
    restricted = {"FAQPage": "restricted to government and healthcare sites only (Aug 2023)"}
    if schema_type in restricted:
        errors.append(f"{prefix}: @type '{schema_type}' is {restricted[schema_type]} — verify site qualifies")

    return errors


def _is_critical(msg: str) -> bool:
    low = msg.lower()
    return any(k in low for k in ("placeholder", "deprecated", "retired"))


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
