#!/usr/bin/env python3
"""Verify that the version string is identical in every file that declares it.

Run from the repository root:
    python3 scripts/check_version_sync.py

Exit 0 = all versions match.  Exit 1 = mismatch found.
"""

import json
import re
import sys
from pathlib import Path

SKILL_MD = Path("SKILL.md")
MARKETPLACE_JSON = Path(".claude-plugin/marketplace.json")
PLUGIN_JSON = Path("plugins/ultimate-seo-geo/.claude-plugin/plugin.json")
PLUGIN_SKILL = Path("plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md")
AGENTS_MD = Path("AGENTS.md")
PLUGIN_AGENTS = Path("plugins/ultimate-seo-geo/skills/ultimate-seo-geo/AGENTS.md")

versions: dict[str, str] = {}


def extract_frontmatter_version(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def extract_table_version(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"\*\*Version\*\*\s*\|\s*(.+?)(?:\s*\||\s*$)", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def extract_json_version(path: Path, *keys: str) -> str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for k in keys:
            if isinstance(data, list):
                data = data[int(k)]
            else:
                data = data[k]
        return str(data).strip()
    except (KeyError, IndexError, json.JSONDecodeError):
        return None


# Collect versions from all sources
v = extract_frontmatter_version(SKILL_MD)
if v:
    versions["SKILL.md frontmatter"] = v

v = extract_table_version(SKILL_MD)
if v:
    versions["SKILL.md table"] = v

v = extract_frontmatter_version(PLUGIN_SKILL)
if v:
    versions["plugin SKILL.md frontmatter"] = v

v = extract_table_version(PLUGIN_SKILL)
if v:
    versions["plugin SKILL.md table"] = v

# AGENTS.md carries the same "Skill at a glance" table as SKILL.md. It was the
# one declaration the v1.15.0 bump missed (check_tag_matches_version.py caught it
# after the tag was pushed), so it is checked here, before the tag exists.
v = extract_table_version(AGENTS_MD)
if v:
    versions["AGENTS.md table"] = v

v = extract_table_version(PLUGIN_AGENTS)
if v:
    versions["plugin AGENTS.md table"] = v

v = extract_json_version(MARKETPLACE_JSON, "metadata", "version")
if v:
    versions["marketplace.json metadata.version"] = v

v = extract_json_version(MARKETPLACE_JSON, "plugins", "0", "version")
if v:
    versions["marketplace.json plugins[0].version"] = v

v = extract_json_version(PLUGIN_JSON, "version")
if v:
    versions["plugin.json version"] = v

# Check
if not versions:
    print("✗ No version strings found in any file")
    sys.exit(1)

unique = set(versions.values())
if len(unique) == 1:
    ver = unique.pop()
    print(f"✓ All {len(versions)} version references match: {ver}")
    for label in sorted(versions):
        print(f"  {label} = {versions[label]}")
    sys.exit(0)
else:
    print(f"✗ Version mismatch — {len(unique)} different values found:\n")
    for label in sorted(versions):
        print(f"  {versions[label]:10s}  ← {label}")
    print(f"\nFix: update all files to use the same version. See RELEASE.md § 1.")
    sys.exit(1)
