#!/usr/bin/env python3
"""Fail if the plugin skill bundle is out of sync with repo root or versions diverge."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Copied into the plugin bundle for end users; stays repo-only for CI.
SCRIPT_EXCLUDE = frozenset({"check-plugin-sync.py"})


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _skill_frontmatter_version(path: Path) -> str | None:
    """Extract version from SKILL.md frontmatter, or None if not present."""
    t = _read(path)
    if not t.startswith("---"):
        sys.exit(f"{path}: missing YAML frontmatter")
    try:
        _, fm, _ = t.split("---", 2)
    except ValueError:
        sys.exit(f"{path}: malformed frontmatter")
    for line in fm.splitlines():
        m = re.match(r"^version:\s*(.+?)\s*$", line) or re.match(
            r"^  version:\s*(.+?)\s*$", line
        )
        if m:
            return m.group(1).strip().strip("'\"")
    return None


def main() -> int:
    skill_root = ROOT / "SKILL.md"
    skill_plugin = ROOT / "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md"

    if _read(skill_root) != _read(skill_plugin):
        sys.exit(
            "SKILL.md mismatch: root != plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md\n"
            "Fix: bash setup-plugin.sh"
        )

    ref_root = ROOT / "references"
    ref_plugin = ROOT / "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/references"
    if not ref_root.is_dir() or not ref_plugin.is_dir():
        sys.exit("references/ directories missing at root or under plugin skill path")

    root_names = sorted(f.name for f in ref_root.iterdir() if f.is_file())
    plug_names = sorted(f.name for f in ref_plugin.iterdir() if f.is_file())
    if root_names != plug_names:
        diff = sorted(set(root_names) ^ set(plug_names))
        sys.exit(
            "references/ filename set mismatch vs plugin copy.\n"
            f"  symmetric diff: {diff}\n"
            "Fix: bash setup-plugin.sh"
        )

    for name in root_names:
        if _read(ref_root / name) != _read(ref_plugin / name):
            sys.exit(
                f"references/{name} differs from plugin copy.\nFix: bash setup-plugin.sh"
            )

    # Audit scripts: same .py set as repo scripts/ minus maintainer tooling.
    scr_root = ROOT / "scripts"
    scr_plugin = ROOT / "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/scripts"
    if not scr_plugin.is_dir():
        sys.exit(
            "plugins/.../skills/.../scripts/ missing.\nFix: bash setup-plugin.sh"
        )
    root_py = sorted(
        p.name for p in scr_root.glob("*.py") if p.name not in SCRIPT_EXCLUDE
    )
    plug_py = sorted(p.name for p in scr_plugin.glob("*.py"))
    if root_py != plug_py:
        sys.exit(
            "scripts/*.py list mismatch vs plugin copy (audit scripts only).\n"
            f"  root:   {root_py}\n"
            f"  plugin: {plug_py}\n"
            "Fix: bash setup-plugin.sh"
        )
    for name in root_py:
        if _read(scr_root / name) != _read(scr_plugin / name):
            sys.exit(
                f"scripts/{name} differs from plugin copy.\nFix: bash setup-plugin.sh"
            )

    runner = "run_individual_checks.sh"
    r_root = scr_root / runner
    r_plug = scr_plugin / runner
    if r_root.is_file():
        if not r_plug.is_file() or _read(r_root) != _read(r_plug):
            sys.exit(
                f"scripts/{runner} missing or differs in plugin copy.\nFix: bash setup-plugin.sh"
            )

    ev_root = ROOT / "evals"
    ev_plugin = ROOT / "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/evals"
    if not ev_root.is_dir() or not ev_plugin.is_dir():
        sys.exit("evals/ missing at root or under plugin skill path.\nFix: bash setup-plugin.sh")

    def _eval_rel_paths(base: Path) -> dict[str, Path]:
        m: dict[str, Path] = {}
        for p in sorted(base.rglob("*")):
            if p.is_file():
                m[p.relative_to(base).as_posix()] = p
        return m

    ev_map = _eval_rel_paths(ev_root)
    pl_map = _eval_rel_paths(ev_plugin)
    if set(ev_map) != set(pl_map):
        diff = sorted(set(ev_map) ^ set(pl_map))
        sys.exit(
            "evals/ path set mismatch vs plugin copy (recursive).\n"
            f"  symmetric diff: {diff}\n"
            "Fix: bash setup-plugin.sh"
        )
    for rel in sorted(ev_map):
        if _read(ev_map[rel]) != _read(pl_map[rel]):
            sys.exit(f"evals/{rel} differs from plugin copy.\nFix: bash setup-plugin.sh")

    market_path = ROOT / ".claude-plugin/marketplace.json"
    with open(market_path, encoding="utf-8") as f:
        market = json.load(f)
    listed_v = market["plugins"][0].get("version")

    plugin_json = ROOT / "plugins/ultimate-seo-geo/.claude-plugin/plugin.json"
    with open(plugin_json, encoding="utf-8") as f:
        pjson = json.load(f)
    pj_v = pjson.get("version")

    versions = {}
    if listed_v:
        versions["marketplace.plugins[0].version"] = listed_v
    if pj_v:
        versions["plugin.json version"] = pj_v

    if len(versions) >= 2:
        unique = set(versions.values())
        if len(unique) != 1:
            lines = "\n".join(f"  {k}: {v!r}" for k, v in versions.items())
            sys.exit("Version strings must match everywhere:\n" + lines)

    print("Plugin sync + version alignment OK ✓")
    for k, v in versions.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
